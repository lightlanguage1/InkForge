"""LLM connection pool with health checking and auto-reconnect."""

import time
import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMConnection:
    """LLM backend connection instance and its state."""
    backend: str
    instance: Any
    model: str
    created_at: float
    last_used: float = 0
    error_count: int = 0
    healthy: bool = True
    current_requests: int = 0


class LLMPool:
    """LLM connection pool managing multiple backend connections.

    Features:
    - Caches connections by backend+model key
    - Periodic health checks
    - Auto-reconnect on failure
    - Connection reuse across projects
    """

    def __init__(self, config: dict):
        self.config = config
        self.connections: Dict[str, LLMConnection] = {}
        self._health_check_interval = config.get('daemon.health_check_interval', 60)
        self._max_error_count = config.get('daemon.max_error_count', 3)

    def get_connection(self, backend: str, model: str = None, **kwargs) -> Any:
        """Get or create an LLM connection.

        Same backend+model reuses the connection.
        """
        model = model or self.config.get('llm.model', 'gpt-5.1')
        key = f"{backend}:{model}"

        if key in self.connections and self.connections[key].healthy:
            conn = self.connections[key]
            conn.last_used = time.time()
            return conn.instance

        return self._create_connection(backend, model, key, **kwargs)

    def _create_connection(self, backend: str, model: str, key: str, **kwargs) -> Any:
        """Create a new LLM connection."""
        from .llm_interface import initialize_llm

        instance = initialize_llm(
            backend=backend,
            model=model,
            temperature=kwargs.get('temperature', self.config.get('llm.temperature', 0.7)),
            top_p=kwargs.get('top_p', self.config.get('llm.top_p', 0.8)),
            top_k=kwargs.get('top_k', self.config.get('llm.top_k', 20)),
            min_p=kwargs.get('min_p', self.config.get('llm.min_p', 0.0)),
            repeat_penalty=kwargs.get('repeat_penalty', self.config.get('llm.repeat_penalty', 1.0)),
            enable_thinking=kwargs.get('enable_thinking', self.config.get('llm.enable_thinking', False)),
        )

        self.connections[key] = LLMConnection(
            backend=backend,
            instance=instance,
            model=model,
            created_at=time.time()
        )
        logger.info("Created LLM connection: %s (backend=%s, model=%s)", key, backend, model)
        return instance

    def health_check(self):
        """Check all connections, mark unhealthy ones."""
        for key, conn in self.connections.items():
            try:
                conn.instance.generate("ping", max_tokens=1)
                conn.healthy = True
                conn.error_count = 0
            except Exception as e:
                conn.error_count += 1
                if conn.error_count >= self._max_error_count:
                    conn.healthy = False
                    logger.warning("LLM connection %s marked unhealthy: %s", key, e)

    def get_stats(self) -> list:
        """Get connection statistics."""
        return [
            {
                "key": key,
                "backend": conn.backend,
                "model": conn.model,
                "healthy": conn.healthy,
                "error_count": conn.error_count,
                "current_requests": conn.current_requests,
                "created_at": conn.created_at,
                "last_used": conn.last_used,
            }
            for key, conn in self.connections.items()
        ]
