"""무엇: 응답 검증·B1 호출 타입 · 입력: 계약 필드 · 출력: JSON 왕복 · 계약 §8-5."""

from dataclasses import asdict, dataclass, replace
import json

from .base import JsonRecord


@dataclass(frozen=True)
class Validated(JsonRecord):
    reason: str | None
    warnings: list[str]
    answers: dict[str, dict] | None


@dataclass(frozen=True)
class B1Config(JsonRecord):
    system: str
    user_template: str
    labels: list[str]
    params: dict


@dataclass(frozen=True)
class B1Call(JsonRecord):
    call_qid: str
    messages: list[dict]
    label_order: list[str]
    label_map: dict[str, str]
    params: dict


@dataclass(frozen=True)
class B1Response(JsonRecord):
    """B1 읽기 결과. 메모리의 -inf만 JSON 왕복 때 문자열로 보존한다 (§5-5b)."""

    reason: str | None
    warnings: list[str]
    top_logprobs: list[dict] | None
    usage: dict | None

    def to_dict(self) -> dict:
        data = asdict(self)
        for row in data["top_logprobs"] or []:
            if row.get("logprob") == float("-inf"):
                row["logprob"] = "-inf"
        return json.loads(json.dumps(data, ensure_ascii=False, allow_nan=False))

    @classmethod
    def from_dict(cls, value: dict):
        result = super().from_dict(value)
        rows = result.top_logprobs
        if rows is not None:
            rows = [dict(row, logprob=float("-inf")) if row.get("logprob") == "-inf"
                    else row for row in rows]
        return replace(result, top_logprobs=rows)
