"""무엇: 분석 선언 정규화 · 입력: overlay analysis 값 · 출력: 종류별 경로 · 계약 §7-4b·7-4d."""

import re


def normalize_declarations(value):
    """구 문자열은 질문 선언이다. 파일 내용 검사는 I/O 경계가 수행한다."""
    if value is None:
        return {}
    if isinstance(value, str):
        value = {"question_risk": value}
    if not isinstance(value, dict) or not value or set(value) - {"question_risk", "score_variants"}:
        raise ValueError("invalid analysis kinds")
    if any(not isinstance(p, str) or re.fullmatch(r"configs/analysis/[A-Za-z0-9][A-Za-z0-9_-]*\.yaml", p) is None
           for p in value.values()) or len(set(value.values())) != len(value):
        raise ValueError("analysis must name distinct confined analysis YAML files")
    return dict(sorted(value.items()))
