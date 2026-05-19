"""LLM 统一接口：字符串 generate + 消息 chat。

将后端类型标记注入 LLMProvider，上层调用时按需选择 generate() 或 chat()。
chat() 支持 Anthropic cache_control，非 Anthropic 后端自动 fallback 为 text。
"""

from typing import List, Dict, Optional


class LLMProvider:
    """LLM 调用封装。兼容旧接口 generate()，新增 chat() 消息模式。"""

    def __init__(self, backend, backend_type: str = "api"):
        self._backend = backend
        self.backend_type = backend_type

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """纯文本 prompt（兼容旧接口）。"""
        return self._backend.generate(prompt, max_tokens=max_tokens)

    def chat(self, messages: List[Dict], max_tokens: int = 2000) -> str:
        """消息列表模式（支持 Anthropic cache_control）。"""
        if self.backend_type == "anthropic":
            return self._anthropic_chat(messages, max_tokens)
        return self._fallback_chat(messages, max_tokens)

    def _anthropic_chat(self, messages: List[Dict], max_tokens: int) -> str:
        """Anthropic 消息格式。"""
        from anthropic import Anthropic
        import os
        from ..configs.api_keys import resolve_api_key

        system_parts = []
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                content = m.get("content", "")
                if isinstance(content, list):
                    for c in content:
                        if c["type"] == "text":
                            system_parts.append(c["text"])
                else:
                    system_parts.append(content)
            else:
                user_messages.append(m)

        client = Anthropic(api_key=resolve_api_key("claude"))
        kwargs = {
            "model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            "max_tokens": max_tokens,
            "messages": user_messages,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)

        response = client.messages.create(**kwargs)
        return response.content[0].text

    def _fallback_chat(self, messages: List[Dict], max_tokens: int) -> str:
        """非 Anthropic 后端：拼回字符串再 generate。"""
        parts = []
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, list):
                content = "\n".join(c["text"] for c in content if c["type"] == "text")
            parts.append(content)
        return self._backend.generate("\n\n".join(parts), max_tokens=max_tokens)
