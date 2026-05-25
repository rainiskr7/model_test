"""OpenAI-compatible adapter for Ko-AgentBench.

Lightweight adapter that talks directly to any OpenAI-compatible
chat-completions endpoint (GPUStack, vLLM, Ollama, etc.) via the
``openai`` Python SDK — no LiteLLM dependency required.

When the remote server does not support native tool calling, tool
schemas are automatically injected into the system prompt so the model
can reason about tools and respond with JSON tool-call blocks.
"""

import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from openai import OpenAI
from .base_adapter import BaseAdapter
from ..observability import observe

_DEFAULT_BASE_URL = "http://172.16.1.81:18090/v1"


class OpenAICompatAdapter(BaseAdapter):
    """Adapter for any OpenAI-compatible endpoint (GPUStack, OpenRouter, vLLM, Ollama, Together, OpenAI 등)."""

    def __init__(self, model_name: str, **config):
        super().__init__(model_name, **config)

        base_url: str = config.get("base_url", _DEFAULT_BASE_URL)
        if base_url.endswith("/chat/completions"):
            base_url = base_url[: -len("/chat/completions")]
        self.base_url = base_url.rstrip("/")

        # Explicit config wins; else OPENAI_API_KEY from environment (.env via load_dotenv).
        api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY") or "EMPTY"
        self.client = OpenAI(base_url=self.base_url, api_key=api_key)

        # 평가 default: 결정론적 (codex 권장 — temp=0.0 메인, 분산 제거 비교 기준선)
        # agent pass@k 보조 트랙은 호출 시 temperature=0.3~0.7로 override
        self.temperature = config.get("temperature", 0.0)
        # 트랙별 합리 상한: agent는 tool call + reasoning + multi-turn 고려해 16384
        # (전역 default는 8192, 호출 시 override 가능)
        self.max_tokens = config.get("max_tokens", 8192)
        self.timeout = config.get("timeout", 60)
        # seed: pass@k 보조 트랙에서 매 반복마다 다른 seed 로 진짜 다양성 보장
        # (temp>0 + 같은 seed 면 vLLM/서빙 설정에 따라 동일 응답 가능)
        self.seed = config.get("seed", None)

        self.native_tool_calling = config.get("native_tool_calling", False)

    # ── public interface ──────────────────────────────────────────────

    @observe(as_type="generation")
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        task_level: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        request = self.convert_to_provider_format(messages, tools)
        request.update({k: v for k, v in kwargs.items() if k not in ("tool_choice",)})

        response = self.client.chat.completions.create(**request)
        canonical = self.convert_from_provider_format(response)

        if not self.native_tool_calling and tools:
            canonical = self._parse_tool_calls_from_text(canonical)

        return canonical

    # ── format conversion ─────────────────────────────────────────────

    def convert_to_provider_format(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        if self.native_tool_calling and tools:
            req = {
                "model": self.model_name,
                "messages": messages,
                "tools": tools,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "timeout": self.timeout,
            }
            if self.seed is not None:
                req["seed"] = self.seed
            return req

        if tools:
            messages = self._inject_tools_into_prompt(messages, tools)

        req = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
        }
        if self.seed is not None:
            req["seed"] = self.seed
        return req

    def convert_from_provider_format(self, response: Any) -> Dict[str, Any]:
        choice = response.choices[0]
        result: Dict[str, Any] = {
            "message": {
                "role": choice.message.role,
                "content": choice.message.content or "",
            },
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            "model": response.model,
            "finish_reason": choice.finish_reason,
        }

        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            result["message"]["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        return result

    # ── tool-prompt injection (for servers without native tool calling) ──

    @staticmethod
    def _inject_tools_into_prompt(
        messages: List[Dict[str, str]],
        tools: List[Dict],
    ) -> List[Dict[str, str]]:
        lines = []
        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name", "unknown")
            desc = func.get("description", "")
            params = json.dumps(func.get("parameters", {}), ensure_ascii=False)
            lines.append(f"- {name}: {desc}\n  Parameters: {params}")

        block = (
            "You have access to the following tools.\n"
            "To call a tool, include a JSON block in your response:\n"
            '{"tool_call": {"name": "<tool_name>", "arguments": {...}}}\n\n'
            + "\n".join(lines)
        )

        messages = list(messages)
        if messages and messages[0].get("role") == "system":
            messages[0] = {
                **messages[0],
                "content": messages[0].get("content", "") + "\n\n" + block,
            }
        else:
            messages.insert(0, {"role": "system", "content": block})
        return messages

    # ── parse tool calls from plain-text model output ─────────────────

    _TOOL_CALL_RE = re.compile(
        r'\{\s*"tool_call"\s*:\s*\{.*?\}\s*\}',
        re.DOTALL,
    )

    @classmethod
    def _parse_tool_calls_from_text(cls, canonical: Dict[str, Any]) -> Dict[str, Any]:
        content = canonical.get("message", {}).get("content", "")
        if not content:
            return canonical

        tool_calls: List[Dict[str, Any]] = []
        for match in cls._TOOL_CALL_RE.finditer(content):
            try:
                parsed = json.loads(match.group())
                tc = parsed.get("tool_call", {})
                name = tc.get("name")
                arguments = tc.get("arguments", {})
                if name:
                    tool_calls.append(
                        {
                            "id": f"call_{uuid.uuid4().hex[:24]}",
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": (
                                    json.dumps(arguments, ensure_ascii=False)
                                    if isinstance(arguments, dict)
                                    else str(arguments)
                                ),
                            },
                        }
                    )
            except (json.JSONDecodeError, AttributeError):
                continue

        if tool_calls:
            canonical["message"]["tool_calls"] = tool_calls
            canonical["finish_reason"] = "tool_calls"

        return canonical
