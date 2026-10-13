"""무엇: 순수 호출 계획 · 입력: Item·task·모델/B1 설정 · 출력: CallPlan 목록 · 계약 §2·§8-6 C."""

import hashlib

from jeveval.client.vllm_chat import chat_body, chat_bytes
from jeveval.contract.b1_prompt import build_b1_call
from jeveval.contract.render import render_state
from jeveval.contract.request import build_request, check_request, request_bytes
from jeveval.types import B1Config, CallPlan, Item, ModelConfig, Rendered, TaskSpec


def _prepare(item, task, cfg):
    """렌더 실패도 보존하고 B1을 포함한 항목 전체의 요청 계약을 검사한다."""
    errors, request = [], None
    try:
        rendered = render_state(item.state_fields, task.state)
    except ValueError as exc:
        rendered = Rendered("", 0)
        errors.append(str(exc))
    try:
        request = build_request(cfg.served_name, rendered, item.questions)
        errors.extend(check_request(request, cfg.served_name))
    except ValueError as exc:
        errors.append(str(exc))
    return rendered, request, errors


def _plan(logical_id, questions, cfg, b1_config, rendered, request, errors):
    """항목 오류가 없을 때만 전송 바이트를 만들고 호출별 생성 실패를 보존한다."""
    errors, body, b1_call = list(errors), b"", None
    call_id = logical_id
    if cfg.kind == "b1":
        call_id += "/" + questions[0].id
    if not errors:
        try:
            if cfg.kind == "systemone":
                body = request_bytes(request)
            else:
                q = questions[0]
                b1_call = build_b1_call(b1_config, rendered, q, q.id)
                body = chat_bytes(chat_body(b1_call, cfg.served_name,
                                            cfg.b1["label_token_ids"]))
        except ValueError as exc:
            errors.append(str(exc))
    return CallPlan(call_id, logical_id, cfg.kind, [q.id for q in questions],
                    {q.id: q.type for q in questions}, body,
                    hashlib.sha256(body).hexdigest(), request, b1_call, rendered, errors)


def plan_calls(item: Item, task: TaskSpec, cfg: ModelConfig,
               b1_config: B1Config | None) -> list[CallPlan]:
    """설정 미완은 중단하고 로컬 요청 오류는 고유 호출 ID마다 계획으로 반환한다."""
    if cfg.kind not in ("systemone", "b1"):
        raise ValueError("unknown model kind")
    if cfg.served_name is None or (cfg.kind == "b1" and (
            b1_config is None or cfg.b1 is None or cfg.b1.get("label_token_ids") is None)):
        raise ValueError("incomplete call configuration")
    rendered, request, errors = _prepare(item, task, cfg)
    logical_id = f"{item.set}:{item.group_id}:{item.item_id}"
    groups = [item.questions]
    if cfg.kind == "b1":
        unique = {}
        for q in item.questions:
            unique.setdefault(q.id, q)
        groups = [[q] for q in unique.values()]
    return [_plan(logical_id, qs, cfg, b1_config, rendered, request, errors)
            for qs in groups]
