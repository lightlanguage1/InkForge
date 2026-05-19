"""Ollama streaming — token-by-token generation from local models."""

import json
import os
from typing import Generator, Optional

from .multi_provider_llm import strip_think_blocks
from ..configs.constants import OLLAMA_DEFAULT_BASE_URL


OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", OLLAMA_DEFAULT_BASE_URL)


def stream_ollama(
    prompt: str,
    model: str = "huihui_ai/qwen3-abliterated:8b",
    max_tokens: int = 2000,
    temperature: float = 0.7,
    top_p: float = 0.8,
    top_k: int = 20,
    min_p: float = 0.0,
    repeat_penalty: float = 1.0,
    enable_thinking: bool = False,
    system_prompt: str = (
        "You are a skilled creative writer focused on producing original fiction."
    ),
) -> Generator[str, None, str]:
    """Stream tokens from a local Ollama model.

    Yields individual text tokens as they arrive and returns the
    full assembled text (with think blocks stripped) when exhausted.

    Args:
        prompt: User message text.
        model: Ollama model tag.
        max_tokens: Maximum tokens to generate.
        temperature: Sampling temperature.
        top_p: Nucleus sampling threshold.
        top_k: Top-k sampling.
        min_p: Minimum probability threshold.
        repeat_penalty: Repetition penalty (1.0 = disabled).
        enable_thinking: Whether to include <think> reasoning blocks.
        system_prompt: System-level instruction.

    Yields:
        Text tokens as they are streamed from the server.

    Returns:
        Full response text with think blocks stripped.
    """
    import urllib.request

    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"

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
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "think": enable_thinking,
        "options": options,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    full_text_parts: list[str] = []

    with urllib.request.urlopen(req, timeout=300) as resp:
        buffer = ""
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            buffer += chunk.decode("utf-8")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = data.get("message", {}).get("content", "")
                if token:
                    full_text_parts.append(token)
                    yield token
                if data.get("done", False):
                    break

    full_text = "".join(full_text_parts)
    return strip_think_blocks(full_text)
