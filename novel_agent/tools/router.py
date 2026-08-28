"""LLM Router — per-task model selection with fallback support.

Maps task types (planner, writer, extractor) to specific models and
backends, so that smaller/faster models can handle planning and extraction
while larger models handle the actual writing.
"""

from typing import Optional

from .llm_interface import (
    initialize_llm,
    LLMClient,
)


class ModelRouter:
    """Route tasks to the most appropriate model backend.

    When ``enabled``, the router selects a backend and model per task
    type.  Each task has a primary model and a fallback; if the primary
    backend raises a connection error, the fallback is tried instead.

    When disabled the router always delegates to ``default_model`` /
    ``default_backend``, matching the pre-router behaviour.
    """

    def __init__(self, config: dict):
        self._cfg = config
        self._router_cfg = config.get("router", {}) if isinstance(config, dict) else {}
        self._llm_cfg = config.get("llm", {}) if isinstance(config, dict) else {}
        self._enabled = self._router_cfg.get("enabled", False) if isinstance(self._router_cfg, dict) else False
        self._default_model = self._llm_cfg.get("model", "gpt-5.1") if isinstance(self._llm_cfg, dict) else "gpt-5.1"
        self._default_backend = self._llm_cfg.get("backend", "codex") if isinstance(self._llm_cfg, dict) else "codex"

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_model_for_task(self, task: str) -> str:
        """Return the configured model name for *task*.

        Returns empty string when the task model is not explicitly set,
        signalling the caller to use the main LLM instead.
        """
        if not self._enabled:
            return self._default_model
        if isinstance(self._router_cfg, dict):
            return self._router_cfg.get(f"{task}_model", "")
        return ""

    def get_backend_for_task(self, task: str) -> str:
        """Return the configured backend for *task*."""
        if not self._enabled:
            return self._default_backend
        return self._router_cfg.get(f"{task}_backend", self._default_backend) if isinstance(self._router_cfg, dict) else self._default_backend

    def get_fallback_for_task(self, task: str) -> Optional[str]:
        """Return the fallback model for *task*, or None."""
        if not self._enabled:
            return None
        return self._router_cfg.get(f"fallback_{task}") if isinstance(self._router_cfg, dict) else None

    def get_interface_for_task(self, task: str) -> LLMClient:
        """Return an initialised LLM client suitable for *task*.

        When the task model is empty (not configured), raises ValueError
        immediately so the caller can fall back to the main LLM without
        a failed connection attempt.

        Tries the primary backend/model.  If a fallback is configured
        and the primary raises a ``ConnectionError`` / ``OSError`` /
        ``RuntimeError``, attempts the fallback (with ``codex`` backend)
        before giving up.
        """
        model = self.get_model_for_task(task)
        backend = self.get_backend_for_task(task)

        if not model:
            raise ValueError(f"No model configured for task '{task}'")

        try:
            return initialize_llm(backend=backend, model=model)
        except (ConnectionError, OSError, RuntimeError):
            fallback = self.get_fallback_for_task(task)
            if fallback and fallback != model:
                return initialize_llm(backend="codex", model=fallback)
            raise

    def get_default_interface(self) -> LLMClient:
        """Return a client using the global default backend/model."""
        return initialize_llm(backend=self._default_backend, model=self._default_model)
