"""LLM interface for StoryDaemon.

Provides a backend-agnostic interface for LLM access.

Backends:
- "codex"       → Codex CLI (GPT-5 via codex exec)
- "api"         → Multi-provider API backend (OpenAI, Gemini, Claude) using
                   an ai_helper-style model registry.
- "gemini-cli"  → Gemini CLI backend using the local `gemini` binary.
- "claude-cli"  → Claude Code CLI backend using the local `claude` binary.
- "ollama"      → Local Ollama server via OpenAI-compatible API
                   (default: http://localhost:11434, override with OLLAMA_BASE_URL).

The API backend uses model names (e.g. "gpt-5.1", "claude-4.5",
"gemini-2.5-pro", "huihui_ai/qwen3-abliterated") to route to the correct provider.
"""
from typing import Optional, Union

from ..configs.constants import OLLAMA_DEFAULT_MODEL
from .codex_interface import CodexInterface
from .multi_provider_llm import MultiProviderInterface, OllamaInterface
from .gemini_cli_interface import GeminiCliInterface
from .claude_cli_interface import ClaudeCliInterface


LLMClient = Union[CodexInterface, MultiProviderInterface, GeminiCliInterface, ClaudeCliInterface, OllamaInterface]


# Global LLM client instance used by helper functions
_llm_client: Optional[LLMClient] = None


def initialize_llm(
    backend: str = "codex",
    codex_bin: str = "codex",
    model: str = "gpt-5.1",
    temperature: float = 0.7,
    top_p: float = 0.8,
    top_k: int = 20,
    min_p: float = 0.0,
    repeat_penalty: float = 1.0,
    enable_thinking: bool = False,
) -> LLMClient:
    """Initialize the LLM client for the given backend.

    Args:
        backend: LLM backend identifier ("codex", "api", "gemini-cli", "claude-cli", or "ollama").
        codex_bin: Path to Codex CLI binary (for backend="codex").
        model: Model identifier for API-like backends.
        temperature: Sampling temperature.
        top_p: Top-p nucleus sampling.
        top_k: Top-k sampling.
        min_p: Min-p sampling.
        repeat_penalty: Repetition penalty (1.0 = disabled).
        enable_thinking: Enable chain-of-thought thinking blocks (Qwen3 etc.).

    Returns:
        An initialized LLM client instance.

    Raises:
        RuntimeError: If the requested backend cannot be initialized.
    """
    global _llm_client

    backend_normalized = backend.lower().strip()

    if backend_normalized == "codex":
        _llm_client = CodexInterface(codex_bin)
    elif backend_normalized in {"api", "openai"}:
        # "openai" kept for backward compatibility; it now means
        # "use the API backend" with the configured model.
        _llm_client = MultiProviderInterface(model=model)
    elif backend_normalized in {"gemini-cli", "gemini"}:
        _llm_client = GeminiCliInterface(model=model)
    elif backend_normalized in {"claude-cli", "claude"}:
        _llm_client = ClaudeCliInterface()
    elif backend_normalized == "ollama":
        resolved_model = model if model != "gpt-5.1" else OLLAMA_DEFAULT_MODEL
        _llm_client = OllamaInterface(
            model=resolved_model,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            min_p=min_p,
            repeat_penalty=repeat_penalty,
            enable_thinking=enable_thinking,
        )
    else:
        raise RuntimeError(
            f"Unsupported LLM backend: {backend}. "
            "Supported backends are: 'codex', 'api', 'gemini-cli', 'claude-cli', 'ollama'."
        )

    return _llm_client


def send_prompt(prompt: str, max_tokens: int = 2000) -> str:
    """Send a prompt using the initialized LLM client.

    Args:
        prompt: The prompt to send.
        max_tokens: Maximum tokens to generate.

    Returns:
        Generated text from the configured LLM backend.

    Raises:
        RuntimeError: If no backend is initialized or generation fails.
    """
    if _llm_client is None:
        # Default to Codex if nothing has been explicitly initialized
        initialize_llm(backend="codex")

    return _llm_client.generate(prompt, max_tokens=max_tokens)  # type: ignore[union-attr]


def send_prompt_with_retry(
    prompt: str,
    max_tokens: int = 2000,
    max_retries: int = 3,
) -> str:
    """Send prompt with automatic retry on failure.

    Args:
        prompt: The prompt to send.
        max_tokens: Maximum tokens to generate.
        max_retries: Maximum retry attempts.

    Returns:
        Generated text from the configured LLM backend.

    Raises:
        RuntimeError: If all retry attempts fail or no backend is initialized.
    """
    if _llm_client is None:
        # Default to Codex if nothing has been explicitly initialized
        initialize_llm(backend="codex")

    return _llm_client.generate_with_retry(  # type: ignore[union-attr]
        prompt,
        max_tokens=max_tokens,
        max_retries=max_retries,
    )


def is_initialized() -> bool:
    """Check if an LLM backend has been initialized.

    Returns:
        True if initialized, False otherwise.
    """
    return _llm_client is not None
