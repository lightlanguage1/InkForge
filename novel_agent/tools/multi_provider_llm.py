"""Multi-provider LLM interface (ai_helper-style).

This module provides a model→function registry and a single send_prompt
entry point that can route prompts to different providers (OpenAI, Gemini,
Claude, Ollama) based on the model name.

API keys are resolved centrally via configs/api_keys.py:
    1. Provider-specific env var (e.g. DEEPSEEK_API_KEY)
    2. STORYDAEMON_API_KEY (single key for all providers)
"""

from typing import Callable, Dict, List, Optional
import os
import re

from ..configs.api_keys import resolve_api_key
from ..configs.constants import (
    DEEPSEEK_BASE_URL,
    OLLAMA_DEFAULT_BASE_URL,
    OLLAMA_DEFAULT_MODEL,
)


def strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> blocks and collapse whitespace."""
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return re.sub(r'\s+', ' ', cleaned).strip()


try:  # OpenAI is a declared dependency
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - should be installed via setup.py
    OpenAI = None  # type: ignore

try:
    import google.generativeai as genai  # type: ignore
except ImportError:  # pragma: no cover - optional, only needed for Gemini
    genai = None  # type: ignore

try:
    import anthropic  # type: ignore
except ImportError:  # pragma: no cover - optional, only needed for Claude
    anthropic = None  # type: ignore


_openai_client: Optional["OpenAI"] = None
_anthropic_client: Optional["anthropic.Anthropic"] = None
_gemini_configured: bool = False
_ollama_client: Optional["OpenAI"] = None
_deepseek_client: Optional["OpenAI"] = None
_local_client: Optional["OpenAI"] = None


def _get_openai_client() -> "OpenAI":
    """Return a shared OpenAI client, initialized from OPENAI_API_KEY."""
    global _openai_client

    if OpenAI is None:
        raise RuntimeError(
            "openai package is not installed. Install it with 'pip install openai' "
            "or switch llm.backend to 'codex'."
        )

    if _openai_client is None:
        _openai_client = OpenAI(api_key=resolve_api_key("openai"))

    return _openai_client


def _get_anthropic_client() -> "anthropic.Anthropic":
    """Return a shared Anthropic client, initialized from CLAUDE_API_KEY."""
    global _anthropic_client

    if anthropic is None:
        raise RuntimeError(
            "anthropic package is not installed. Install it with 'pip install anthropic' "
            "or use a different model that does not require Claude."
        )

    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=resolve_api_key("claude"))

    return _anthropic_client


def _ensure_gemini_configured():
    """Configure Gemini client using GEMINI_API_KEY if available."""
    global _gemini_configured

    if _gemini_configured:
        return

    if genai is None:
        raise RuntimeError(
            "google-generativeai package is not installed. Install it with "
            "'pip install google-generativeai' or use a different model."
        )

    genai.configure(api_key=resolve_api_key("gemini"))
    _gemini_configured = True


def _get_ollama_client() -> "OpenAI":
    """Return a shared Ollama client using OpenAI-compatible API."""
    global _ollama_client

    if OpenAI is None:
        raise RuntimeError(
            "openai package is not installed. Install it with 'pip install openai'."
        )

    if _ollama_client is None:
        base_url = os.environ.get("OLLAMA_BASE_URL", OLLAMA_DEFAULT_BASE_URL) + "/v1"
        _ollama_client = OpenAI(api_key="ollama", base_url=base_url)

    return _ollama_client


def _get_deepseek_client() -> "OpenAI":
    """Return a shared DeepSeek client (OpenAI-compatible API)."""
    global _deepseek_client

    if OpenAI is None:
        raise RuntimeError(
            "openai package is not installed. Install it with 'pip install openai'."
        )

    if _deepseek_client is None:
        _deepseek_client = OpenAI(
            api_key=resolve_api_key("deepseek"),
            base_url=DEEPSEEK_BASE_URL,
        )

    return _deepseek_client


def _get_local_client() -> "OpenAI":
    """Return a shared OpenAI client pointed at the local llama-server."""
    global _local_client

    if OpenAI is None:
        raise RuntimeError("openai package is not installed.")

    if _local_client is None:
        base_url = os.environ.get("LOCAL_LLM_URL", "http://127.0.0.1:8080/v1")
        _local_client = OpenAI(api_key="local", base_url=base_url)

    return _local_client


# --- Provider-specific prompt helpers -------------------------------------------------


def send_prompt_openai(
    prompt: str,
    model: str = "gpt-5.1",
    max_tokens: int = 2000,
    temperature: float = 0.7,
    role_description: str = (
        "You are a helpful fiction writing assistant. You will create original text only."
    ),
) -> str:
    """Send a prompt to the OpenAI Chat API."""
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": role_description},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


def send_prompt_gemini(
    prompt: str,
    model_name: str = "gemini-2.5-pro",
    max_output_tokens: int = 2048,
    temperature: float = 0.9,
) -> str:
    """Send a prompt to the Gemini API and return the generated text."""
    _ensure_gemini_configured()
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(  # type: ignore[attr-defined]
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        ),
        stream=False,
    )
    return getattr(response, "text", "")


def send_prompt_claude(
    prompt: str,
    model: str = "claude-4.5-20250929",
    max_tokens: int = 4096,
    temperature: float = 0.7,
    role_description: str = (
        "You are a skilled creative writer focused on producing original fiction."
    ),
) -> str:
    """Send a prompt to Anthropic Claude and return the generated text."""
    client = _get_anthropic_client()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=role_description,
        messages=[{"role": "user", "content": prompt}],
    )
    # Anthropic returns a list of content blocks; we take the first text block
    if response.content and hasattr(response.content[0], "text"):
        return response.content[0].text  # type: ignore[no-any-return]
    return ""


def send_prompt_ollama(
    prompt: str,
    model: str = "huihui_ai/qwen3-abliterated:8b",
    max_tokens: int = 2000,
    temperature: float = 0.7,
    top_p: float = 0.8,
    top_k: int = 20,
    min_p: float = 0.0,
    repeat_penalty: float = 1.0,
    enable_thinking: bool = False,
    role_description: str = (
        "You are a skilled creative writer focused on producing original fiction."
    ),
) -> str:
    """Send a prompt to a local Ollama server via its native /api/chat endpoint.

    Uses the native API (not OpenAI-compatible) so that think=false is
    properly honoured on qwen3-style reasoning models.
    """
    import json
    import urllib.request

    base_url = os.environ.get("OLLAMA_BASE_URL", OLLAMA_DEFAULT_BASE_URL)
    url = base_url.rstrip("/") + "/api/chat"

    options: dict = {
        "num_predict": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "min_p": min_p,
    }
    if repeat_penalty != 1.0:
        options["repeat_penalty"] = repeat_penalty

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": role_description},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": enable_thinking,
        "options": options,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    content = body.get("message", {}).get("content", "")
    return strip_think_blocks(content)


def send_prompt_deepseek(
    prompt: str,
    model: str = "deepseek-chat",
    max_tokens: int = 8192,
    temperature: float = 0.7,
    role_description: str = (
        "You are a skilled creative writer focused on producing original fiction."
    ),
) -> str:
    """Send a prompt to DeepSeek API (OpenAI-compatible, base_url=api.deepseek.com)."""
    client = _get_deepseek_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": role_description},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


def send_prompt_local(
    prompt: str,
    model: str = "local",
    max_tokens: int = 2000,
    temperature: float = 0.7,
    role_description: str = "You are a helpful fiction writing assistant.",
) -> str:
    """Send a prompt to the local llama-server (OpenAI-compatible API)."""
    client = _get_local_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": role_description},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


# --- Model registry (ai_helper-style) --------------------------------------------------


ModelFn = Callable[[str, int], str]


_model_config: Dict[str, ModelFn] = {
    # OpenAI GPT-5 family
    "gpt-5": lambda prompt, max_tokens: send_prompt_openai(
        prompt=prompt,
        model="gpt-5",
        max_tokens=max_tokens,
    ),
    "gpt-5-mini": lambda prompt, max_tokens: send_prompt_openai(
        prompt=prompt,
        model="gpt-5-mini",
        max_tokens=max_tokens,
    ),
    "gpt-5.1": lambda prompt, max_tokens: send_prompt_openai(
        prompt=prompt,
        model="gpt-5.1",
        max_tokens=max_tokens,
    ),
    "gpt-5.1-mini": lambda prompt, max_tokens: send_prompt_openai(
        prompt=prompt,
        model="gpt-5.1-mini",
        max_tokens=max_tokens,
    ),
    # Gemini 2.5 Pro
    "gemini-2.5-pro": lambda prompt, max_tokens: send_prompt_gemini(
        prompt=prompt,
        model_name="gemini-2.5-pro-exp-03-25",
        max_output_tokens=max_tokens,
    ),
    # Claude 4.5
    "claude-4.5": lambda prompt, max_tokens: send_prompt_claude(
        prompt=prompt,
        model="claude-sonnet-4-5-20250929",
        max_tokens=max_tokens,
    ),
    # DeepSeek models
    "deepseek-chat": lambda prompt, max_tokens: send_prompt_deepseek(
        prompt=prompt,
        model="deepseek-chat",
        max_tokens=max_tokens,
    ),
    "deepseek-reasoner": lambda prompt, max_tokens: send_prompt_deepseek(
        prompt=prompt,
        model="deepseek-reasoner",
        max_tokens=max_tokens,
    ),
    # Local llama-server (OpenAI-compatible, default http://127.0.0.1:8080/v1)
    "local-llama": lambda prompt, max_tokens: send_prompt_local(
        prompt=prompt,
        model="local",
        max_tokens=max_tokens,
    ),
    # Ollama local models
    "huihui_ai/qwen3-abliterated": lambda prompt, max_tokens: send_prompt_ollama(
        prompt=prompt,
        model="huihui_ai/qwen3-abliterated:8b",
        max_tokens=max_tokens,
    ),
    "huihui_ai/qwen3-abliterated:8b": lambda prompt, max_tokens: send_prompt_ollama(
        prompt=prompt,
        model="huihui_ai/qwen3-abliterated:8b",
        max_tokens=max_tokens,
    ),
}


def get_supported_models() -> List[str]:
    """Return the list of supported model identifiers."""
    return list(_model_config.keys())


def send_prompt(prompt: str, model: str = "gpt-5.1", max_tokens: int = 2000) -> str:
    """Send a prompt using the configured model registry.

    If the model key is not found, tries a "-latest" suffix before failing.
    """
    # Resolve model key
    if model not in _model_config:
        alt = f"{model}-latest"
        if alt in _model_config:
            model = alt
        else:
            supported = ", ".join(sorted(get_supported_models()))
            raise ValueError(
                f"Unsupported model: {model}. Supported models are: {supported}"
            )

    try:
        return _model_config[model](prompt, max_tokens)
    except Exception as e:  # noqa: BLE001 - we want a simple wrapper
        raise RuntimeError(f"Error calling model '{model}': {e}") from e


def send_prompt_with_retry(
    prompt: str,
    model: str = "gpt-5.1",
    max_tokens: int = 2000,
    max_retries: int = 3,
) -> str:
    """Send a prompt with simple retry logic on failure."""
    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            return send_prompt(prompt, model=model, max_tokens=max_tokens)
        except Exception as e:  # noqa: BLE001
            last_error = e
            if attempt < max_retries - 1:
                continue

    raise RuntimeError(
        f"Model '{model}' failed after {max_retries} attempts. Last error: {last_error}"
    ) from last_error


def ollama_health_check(model: Optional[str] = None) -> dict:
    """Check if the Ollama server is reachable and optionally if a model is available.

    Args:
        model: Optional model name to verify availability.

    Returns:
        Dictionary with status information:
        - "available": True if the server responded
        - "message": Status description
        - "model_available": True/None if the specified model was found
    """
    import json
    import urllib.request

    base_url = os.environ.get("OLLAMA_BASE_URL", OLLAMA_DEFAULT_BASE_URL)

    try:
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/tags",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"available": False, "message": str(exc), "model_available": None}

    if model:
        models = body.get("models", [])
        model_names = [m.get("name", "") for m in models]
        available = any(model in m for m in model_names)
        return {
            "available": True,
            "message": f"Model '{model}' {'found' if available else 'not found'}",
            "model_available": available,
        }

    return {"available": True, "message": "Ollama server is reachable", "model_available": None}


class MultiProviderInterface:
    """Thin adapter exposing generate / generate_with_retry.

    This class allows the rest of StoryDaemon to treat the ai_helper-style
    functions as a simple LLM client with generate(...) and
    generate_with_retry(...), similar to CodexInterface.
    """

    def __init__(self, model: str = "gpt-5.1"):
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 2000, timeout: int = 120) -> str:  # noqa: ARG002
        # timeout is accepted for interface compatibility but not used directly
        return send_prompt(prompt, model=self.model, max_tokens=max_tokens)

    def generate_with_retry(
        self,
        prompt: str,
        max_tokens: int = 2000,
        timeout: int = 120,  # noqa: ARG002
        max_retries: int = 3,
    ) -> str:
        return send_prompt_with_retry(
            prompt,
            model=self.model,
            max_tokens=max_tokens,
            max_retries=max_retries,
        )


class OllamaInterface:
    """Ollama backend that bypasses the model registry.

    Accepts any model name supported by the local Ollama server,
    so no registry entry is needed when switching models.
    """

    def __init__(
        self,
        model: str = "huihui_ai/qwen3-abliterated:8b",
        temperature: float = 0.7,
        top_p: float = 0.8,
        top_k: int = 20,
        min_p: float = 0.0,
        repeat_penalty: float = 1.0,
        enable_thinking: bool = False,
    ):
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.min_p = min_p
        self.repeat_penalty = repeat_penalty
        self.enable_thinking = enable_thinking

    def generate(self, prompt: str, max_tokens: int = 2000, timeout: int = 300) -> str:  # noqa: ARG002
        return send_prompt_ollama(
            prompt,
            model=self.model,
            max_tokens=max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
            min_p=self.min_p,
            repeat_penalty=self.repeat_penalty,
            enable_thinking=self.enable_thinking,
        )

    def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 2000,
    ) -> "Generator[str, None, str]":
        """Stream tokens from the Ollama model.

        Args:
            prompt: User message text.
            max_tokens: Maximum tokens to generate.

        Yields:
            Individual text tokens as they arrive.

        Returns:
            Full response text with think blocks stripped.
        """
        from .ollama_stream import stream_ollama

        return stream_ollama(
            prompt,
            model=self.model,
            max_tokens=max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
            min_p=self.min_p,
            repeat_penalty=self.repeat_penalty,
            enable_thinking=self.enable_thinking,
        )

    def health_check(self) -> dict:
        """Check if the Ollama server is reachable with the configured model."""
        return ollama_health_check(model=self.model)

    def generate_with_retry(
        self,
        prompt: str,
        max_tokens: int = 2000,
        timeout: int = 300,  # noqa: ARG002
        max_retries: int = 3,
    ) -> str:
        last_error: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                return self.generate(prompt, max_tokens=max_tokens)
            except Exception as e:  # noqa: BLE001
                last_error = e
                if attempt < max_retries - 1:
                    continue
        raise RuntimeError(
            f"Ollama model '{self.model}' failed after {max_retries} attempts. "
            f"Last error: {last_error}"
        ) from last_error
