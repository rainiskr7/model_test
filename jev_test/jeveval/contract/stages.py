"""무엇: 셋별 실행 단계 · 입력: 현재/역사 set ID · 출력: 단계 목록 · 계약 §6-1."""


def stage_names(set_name: str) -> tuple[str, ...]:
    """기존 셋 정체성만 사용한다. overlay/family/현재 설정은 역사 해석에 넣지 않는다."""
    return ("dev", "test", "extra") if set_name == "fc_call_decision" else ("dev", "test")


def supports_extra(set_name: str) -> bool:
    """FunctionChat 원 셋만 지원하며 별칭의 extra 확장은 별도 계약이다."""
    return "extra" in stage_names(set_name)
