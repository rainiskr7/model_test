"""Frozen wording constants only (SPEC §3)."""

INTENT_1 = "고객의 이번 발화와 관련된 서비스에서 지금 진행 중인 일은? 그런 일이 둘이면 서비스 목록에서 앞에 있는 서비스의 일을 고른다. 없으면 NONE."
INTENT_2 = "고객의 이번 발화와 관련된 서비스에서 지금 진행 중인 두 번째 일은? 그런 일이 둘일 때 서비스 목록에서 뒤에 있는 서비스의 일을 고른다. 하나 이하이면 NONE."
NONE_DESCRIPTION = "진행 중인 일이 없다 (이 칸에 해당하는 일이 없다)"
ACTION_TEMPLATE = "고객이 이 턴에서 {description} 했는가?"
ACTIONS = {
    "INFORM": "정보를 제공",
    "REQUEST": "정보를 요청",
    "AFFIRM": "동의하거나 긍정",
    "NEGATE": "부정하거나 거절",
    "REQUEST_ALTS": "다른 대안을 요청",
    "SELECT": "제시된 선택지를 선택",
    "CLOSE": "작별 인사 또는 감사 표현",
    "INFORM_INTENT": "원하는 작업이나 의도를 전달",
    "AFFIRM_INTENT": "제안된 작업이나 의도에 동의",
    "NEGATE_INTENT": "제안된 작업이나 의도를 거절",
}
