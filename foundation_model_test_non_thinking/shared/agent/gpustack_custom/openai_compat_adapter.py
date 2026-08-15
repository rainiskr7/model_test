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
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI
from .base_adapter import BaseAdapter
from .tool_call_parser import extract_tool_calls
from ..observability import observe

def _load_serving_constraints():
    """shared/serving/constraints.apply 로드.

    ⚠️ 이 파일은 run_gpustack_custom.sh 에 의해
       data/Ko-AgentBench/bench/adapters/ 로 *복사되어* 실행된다.
       따라서 __file__ 기준 상대경로로는 shared/ 를 절대 못 찾는다.
       run_full_eval.sh 가 export 하는 MODEL_TEST_BASE 를 기준으로 찾는다.

    못 찾으면 no-op 으로 폴백한다. MODEL_TEST_BASE 가 없다는 건 보통
    load_model_config.py 를 안 거쳤다는 뜻이고, 그러면 SERVING_* env 도
    없어서 제약 자체가 불필요하다. 다만 SERVING_* 는 설정됐는데 모듈만
    못 찾는 경우는 조용히 넘어가면 안 되므로 stderr 로 경고한다.
    """
    base = os.environ.get("MODEL_TEST_BASE")
    if base:
        shared_dir = Path(base) / "shared"
        if (shared_dir / "serving" / "constraints.py").is_file():
            if str(shared_dir) not in sys.path:
                sys.path.insert(0, str(shared_dir))
            try:
                from serving.constraints import apply
                return apply
            except Exception as exc:  # pragma: no cover
                print(f"[adapter] serving.constraints import 실패: {exc}", file=sys.stderr)

    if any(k.startswith("SERVING_") for k in os.environ):
        print(
            "[adapter] 경고: SERVING_* env 가 설정됐는데 shared/serving 을 못 찾음 "
            f"(MODEL_TEST_BASE={base!r}). 서빙 제약이 적용되지 않는다.",
            file=sys.stderr,
        )

    def _noop(payload, *, sdk=False):
        return payload

    return _noop


apply_serving_constraints = _load_serving_constraints()

_DEFAULT_BASE_URL = "http://172.16.1.81:18090/v1"


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        print(f"[adapter] warning: {name}={raw!r} is not a positive number; using {default}", file=sys.stderr)
        return default
    if value <= 0:
        print(f"[adapter] warning: {name}={raw!r} is not positive; using {default}", file=sys.stderr)
        return default
    return value


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
        # max_retries=0: SDK 기본 재시도(3회)와 러너 재시도(run.py max_retries=3)가
        # 곱해져 실패 1건당 timeout 의 9배를 태우기 때문이다. 실측(dense 27B, timeout 60):
        # 재시도 간격 183초 = 60×3, 태스크당 ~9분 소모. 재시도는 러너 쪽 하나로 충분하다.
        self.client = OpenAI(base_url=self.base_url, api_key=api_key, max_retries=0)

        # 평가 default: 결정론적 (codex 권장 — temp=0.0 메인, 분산 제거 비교 기준선)
        # agent pass@k 보조 트랙은 호출 시 temperature=0.3~0.7로 override
        self.temperature = config.get("temperature", 0.0)
        # 트랙별 합리 상한: agent는 tool call + reasoning + multi-turn 고려해 16384
        # (전역 default는 8192, 호출 시 override 가능)
        self.max_tokens = config.get("max_tokens", 8192)
        # 60초는 dense 모델에서 구조적으로 맞을 수 없다. GB10 에서 dense 27B 는
        # 대역폭 바운드로 ~4.3 tok/s 이므로 max_tokens 2048 을 다 쓰면 476초가 필요하다.
        # 실측: dense 런 36태스크 만에 타임아웃 43건, L2 는 15개 중 9개가 steps=0 으로
        # 통째로 유실됐다(SelectAcc 0.400 — 실력이 아니라 시도조차 못 한 것).
        # MoE 는 호출당 ~3초라 91태스크 완주에도 0건이었다 — dense 로만 드러나는 함정이다.
        # KRETA 의 timeout 60 함정과 같은 계열이고 thinking 은 이미 THINK_TIMEOUT 600 이다.
        self.timeout = config.get("timeout", _env_float("AGENT_TIMEOUT", 600.0))
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
            # 서빙 백엔드 제약 적용 (SERVING_* env 미설정 시 no-op)
            return apply_serving_constraints(req, sdk=True)

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
        return apply_serving_constraints(req, sdk=True)

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

    @classmethod
    def _parse_tool_calls_from_text(cls, canonical: Dict[str, Any]) -> Dict[str, Any]:
        content = canonical.get("message", {}).get("content", "")
        if not content:
            return canonical

        tool_calls = extract_tool_calls(content)
        if tool_calls:
            canonical["message"]["tool_calls"] = tool_calls
            canonical["finish_reason"] = "tool_calls"

        return canonical
