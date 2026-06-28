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
from .reasoning import split_reasoning, message_content_and_reasoning
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

        # thinking 모델 default: 권장 sampling (THINK_* env). greedy 는 thinking 에서
        # 반복·퇴화를 유발하므로 temp 0.6 / top_p 0.95 / top_k 20 기본.
        # pass@k 보조 트랙은 호출 시 temperature 등 override.
        self.temperature = config.get("temperature",
                                      float(os.environ.get("THINK_TEMPERATURE", "0.6")))
        self.top_p = config.get("top_p", float(os.environ.get("THINK_TOP_P", "0.95")))
        self.top_k = config.get("top_k", int(os.environ.get("THINK_TOP_K", "20")))
        # tool call + 추론(<think>) + multi-turn 고려해 크게. thinking 은 추론 토큰이
        # 더해지므로 16384 기본 (THINK_MAX_TOKENS env override).
        self.max_tokens = config.get("max_tokens",
                                     int(os.environ.get("THINK_MAX_TOKENS", "16384")))
        # thinking 은 느려서 timeout 큼 (기존 60 → THINK_TIMEOUT 600).
        self.timeout = config.get("timeout", float(os.environ.get("THINK_TIMEOUT", "600")))
        # seed: 재현성. pass@k 보조 트랙은 매 반복마다 다른 seed 로 override.
        self.seed = config.get("seed", int(os.environ.get("THINK_SEED", "42")))

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
            self._apply_sampling(req)
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
        self._apply_sampling(req)
        return req

    def _apply_sampling(self, req: Dict[str, Any]) -> None:
        """thinking sampling(top_p / top_k / seed) 을 요청에 주입.

        top_k 는 OpenAI 표준이 아니라 vLLM extra_body 로 전달.
        """
        if self.top_p is not None:
            req["top_p"] = self.top_p
        if self.top_k is not None and self.top_k > 0:
            req["extra_body"] = {"top_k": self.top_k}
        if self.seed is not None:
            req["seed"] = self.seed

    def convert_from_provider_format(self, response: Any) -> Dict[str, Any]:
        choice = response.choices[0]
        # thinking 모델 대응: content 에서 추론을 분리. tool-call 정규식이 추론 안의
        # tool_call 모양 JSON 을 오인하지 않도록 *strip 된* content 만 쓰고,
        # 추론은 reasoning_content 로 따로 보존.
        raw_content, raw_reasoning = message_content_and_reasoning(choice.message)
        final_content, reasoning = split_reasoning(raw_content, raw_reasoning)
        result: Dict[str, Any] = {
            "message": {
                "role": choice.message.role,
                "content": final_content,
                "reasoning_content": reasoning,
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
