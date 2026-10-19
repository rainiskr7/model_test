"""무엇: 분할 파일 입출력 · 입력: SplitPlan/경로 · 출력: 고정 JSON/계획 · 계약 §6."""

import json
from pathlib import Path
import re

from jeveval.types import SplitPlan


def _check_text(plan: SplitPlan) -> None:
    """감정 이름 외 한글을 거부하여 원문 묶음 키가 출력되는 오류를 잡는다."""
    data = plan.to_dict()
    data.pop("diagnostic_demotions")
    if re.search("[\u1100-\u11ff\u3130-\u318f\ua960-\ua97f\uac00-\ud7ff]",
                 json.dumps(data, ensure_ascii=False)):
        raise ValueError("Hangul is allowed only in diagnostic_demotions")


def split_bytes(plan: SplitPlan) -> bytes:
    """쓰기 전에 전체 분할의 직렬화도 검사할 수 있게 한다."""
    _check_text(plan)
    return (json.dumps(plan.to_dict(), ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")


def write_split_plan(plan: SplitPlan, path: str | Path) -> None:
    """보정 6의 정렬된 UTF-8 JSON과 LF 하나를 그대로 기록한다."""
    payload = split_bytes(plan)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def read_split_plan(path: str | Path) -> SplitPlan:
    """JSON 왕복 시 기존 dataclass의 필드·타입 검사를 적용한다."""
    plan = SplitPlan.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
    _check_text(plan)
    return plan
