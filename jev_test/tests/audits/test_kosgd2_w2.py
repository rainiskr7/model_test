"""W2 짝 문구·102a097 바이트 경계와 한쪽만 옛 문구인 반례. 데이터 원문 불필요."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from audits.audit_v4.independent.requests import approved

ROOT = Path(__file__).resolve().parents[2]
OLD_WORDING = """  instructions: 고객의 이번 발화에서 어떤 작업(예약·조회·구매 등)을 하고 싶다는 의사를 밝히는가?
  criteria:
    'true': 하고 싶은 작업을 밝힌다
    'false': 하고 싶은 작업을 밝히지 않는다
"""
W2_WORDING = """  instructions: 고객의 이번 발화에서 지금 진행되고 있지 않은 작업(예약·조회·구매 등)을 새로 하겠다고 스스로 꺼내는가? 이미 진행 중인 작업을 다시 말하거나 그 조건만 말하는 경우, 시스템이 먼저 제안한 작업에 동의만 하는 경우는 여기에 들지 않는다. 같은 발화에서 다른 작업을 새로 꺼내면 참이다.
  criteria:
    'true': 진행되고 있지 않은 작업을 새로 꺼낸다
    'false': 새로 꺼내는 작업이 없다 (진행 중인 작업만 다시 말하거나 제안된 작업에 동의만 하는 경우 포함)
"""
BASELINE_FULL = """# 개정 15 W1 — Phase B 감사 전, 모델 호출 없음.
set: kosgd2
variant: full
state:
  kind: json_string
  keys:
  - dialogue
  - catalog
  target_key: dialogue
questions:
- id: ongoing_1
  role: success
  type: choice
  instructions: 고객의 이번 발화와 관련된 서비스에서 지금 진행 중인 작업(시스템이 처리하고 있는 작업)은? 그런 작업이 둘이면 catalog
    의 서비스 순서에서 앞에 있는 서비스의 작업을 고른다. 없으면 NONE.
  options: catalog_intents_plus_none
  label: ongoing_slot_1
- id: ongoing_2
  role: success
  type: choice
  instructions: 고객의 이번 발화와 관련된 서비스에서 지금 진행 중인 작업이 서로 다른 서비스에서 둘인 경우, catalog 의 서비스
    순서에서 뒤에 있는 서비스의 작업은? 진행 중인 작업이 하나이거나 없으면 NONE.
  options: catalog_intents_plus_none
  label: ongoing_slot_2
- id: act_inform
  role: success
  type: noul
  instructions: 고객의 이번 발화에서 작업에 필요한 항목의 값(날짜·시간·장소·인원·이름 등)을 시스템에 알려 주는가? 작업 종류만 밝히는
    것은 여기에 들지 않는다.
  criteria:
    'true': 항목의 값을 하나 이상 알려 준다
    'false': 알려 주는 항목의 값이 없다
  label: act:INFORM
- id: act_request
  role: success
  type: noul
  instructions: '고객의 이번 발화에서 어떤 항목의 값(예: 주소, 가격, 시간)을 알려 달라고 시스템에 요청하는가?'
  criteria:
    'true': 항목의 값을 알려 달라고 요청한다
    'false': 요청하는 항목의 값이 없다
  label: act:REQUEST
- id: act_affirm
  role: success
  type: noul
  instructions: '고객의 이번 발화에서 시스템이 확인한 정보·조건이나 시스템의 말(예: ''내일 오후 3시, 2명 맞나요?'')에 동의하는가?
    제안된 작업을 할지 말지에 대한 동의는 따로 묻는다.'
  criteria:
    'true': 시스템이 확인한 내용에 동의한다
    'false': 동의하지 않거나, 동의할 확인 내용이 없다
  label: act:AFFIRM
- id: act_negate
  role: success
  type: noul
  instructions: 고객의 이번 발화에서 시스템이 확인한 정보·조건이나 시스템의 말을 부정하는가? 제안된 작업을 거절하는 것은 따로 묻는다.
  criteria:
    'true': 시스템이 확인한 내용을 부정한다
    'false': 부정하지 않는다
  label: act:NEGATE
- id: act_request_alts
  role: success
  type: noul
  instructions: 고객의 이번 발화에서 시스템이 보여 준 결과 말고 다른 결과(대안)를 더 찾아 달라고 하는가?
  criteria:
    'true': 다른 결과를 더 요청한다
    'false': 다른 결과를 요청하지 않는다
  label: act:REQUEST_ALTS
- id: act_select
  role: success
  type: noul
  instructions: 고객의 이번 발화에서 시스템이 보여 준 결과 가운데 하나를 고르는가?
  criteria:
    'true': 보여 준 결과 중 하나를 고른다
    'false': 고르지 않는다
  label: act:SELECT
- id: act_close
  role: success
  type: noul
  instructions: 고객의 이번 발화에서 감사 인사를 하거나 대화를 끝내는가?
  criteria:
    'true': 감사하거나 대화를 끝내려는 의사를 표현한다
    'false': 감사도, 대화를 끝내려는 의사도 표현하지 않는다
  label: act:CLOSE
- id: act_inform_intent
  role: success
  type: noul
  instructions: 고객의 이번 발화에서 어떤 작업(예약·조회·구매 등)을 하고 싶다는 의사를 밝히는가?
  criteria:
    'true': 하고 싶은 작업을 밝힌다
    'false': 하고 싶은 작업을 밝히지 않는다
  label: act:INFORM_INTENT
- id: act_affirm_intent
  role: diagnostic
  type: noul
  instructions: '고객의 이번 발화에서 시스템이 제안한 작업(예: ''이 식당을 예약해 드릴까요?'')을 하는 데 동의하는가?'
  criteria:
    'true': 제안된 작업을 하는 데 동의한다
    'false': 동의하지 않거나, 제안된 작업이 없다
  label: act:AFFIRM_INTENT
- id: act_negate_intent
  role: diagnostic
  type: noul
  instructions: 고객의 이번 발화에서 시스템이 제안한 작업을 하는 것을 거절하는가?
  criteria:
    'true': 제안된 작업을 거절한다
    'false': 거절하지 않거나, 제안된 작업이 없다
  label: act:NEGATE_INTENT
- id: ongoing_two
  role: diagnostic
  type: noul
  instructions: 고객의 이번 발화와 관련된 서비스에서 지금 진행 중인 작업이 서로 다른 서비스에서 둘인가?
  criteria:
    'true': 서로 다른 두 서비스에서 각각 작업이 진행 중이다
    'false': 진행 중인 작업이 하나이거나 없다
  label: ongoing_two
per_item_questions: null
group_key: dialogue_id
"""
BASELINE_ACTIONS_ONLY = """# 초안 (10-13, Claude) — 사용자 결정 전. 동결 대상 (계획 §4-6). 형식: P1_CONTRACT.md §1-1.
# 근거: SGD README 의 user act 정의 (google-research-datasets/dstc8-schema-guided-dialogue), 계획 §3 KoSGD 세부, 진행 중인 일 문구는 감사 v3 (audits/audit_v3/build/wording.py) 그대로
set: kosgd2
variant: actions_only
state:
  kind: json_string
  keys:
  - dialogue
  - catalog
  target_key: dialogue
questions:
- id: act_inform
  role: success
  type: noul
  instructions: 고객의 이번 발화에서 작업에 필요한 항목의 값(날짜·시간·장소·인원·이름 등)을 시스템에 알려 주는가? 작업 종류만 밝히는 것은 여기에 들지 않는다.
  criteria:
    'true': 항목의 값을 하나 이상 알려 준다
    'false': 알려 주는 항목의 값이 없다
  label: act:INFORM
- id: act_request
  role: success
  type: noul
  instructions: '고객의 이번 발화에서 어떤 항목의 값(예: 주소, 가격, 시간)을 알려 달라고 시스템에 요청하는가?'
  criteria:
    'true': 항목의 값을 알려 달라고 요청한다
    'false': 요청하는 항목의 값이 없다
  label: act:REQUEST
- id: act_affirm
  role: success
  type: noul
  instructions: '고객의 이번 발화에서 시스템이 확인한 정보·조건이나 시스템의 말(예: ''내일 오후 3시, 2명 맞나요?'')에 동의하는가? 제안된 작업을 할지 말지에 대한 동의는 따로 묻는다.'
  criteria:
    'true': 시스템이 확인한 내용에 동의한다
    'false': 동의하지 않거나, 동의할 확인 내용이 없다
  label: act:AFFIRM
- id: act_negate
  role: success
  type: noul
  instructions: 고객의 이번 발화에서 시스템이 확인한 정보·조건이나 시스템의 말을 부정하는가? 제안된 작업을 거절하는 것은 따로 묻는다.
  criteria:
    'true': 시스템이 확인한 내용을 부정한다
    'false': 부정하지 않는다
  label: act:NEGATE
- id: act_request_alts
  role: success
  type: noul
  instructions: 고객의 이번 발화에서 시스템이 보여 준 결과 말고 다른 결과(대안)를 더 찾아 달라고 하는가?
  criteria:
    'true': 다른 결과를 더 요청한다
    'false': 다른 결과를 요청하지 않는다
  label: act:REQUEST_ALTS
- id: act_select
  role: success
  type: noul
  instructions: 고객의 이번 발화에서 시스템이 보여 준 결과 가운데 하나를 고르는가?
  criteria:
    'true': 보여 준 결과 중 하나를 고른다
    'false': 고르지 않는다
  label: act:SELECT
- id: act_close
  role: success
  type: noul
  instructions: 고객의 이번 발화에서 감사 인사를 하거나 대화를 끝내는가?
  criteria:
    'true': 감사하거나 대화를 끝내려는 의사를 표현한다
    'false': 감사도, 대화를 끝내려는 의사도 표현하지 않는다
  label: act:CLOSE
- id: act_inform_intent
  role: success
  type: noul
  instructions: 고객의 이번 발화에서 어떤 작업(예약·조회·구매 등)을 하고 싶다는 의사를 밝히는가?
  criteria:
    'true': 하고 싶은 작업을 밝힌다
    'false': 하고 싶은 작업을 밝히지 않는다
  label: act:INFORM_INTENT
- id: act_affirm_intent
  role: diagnostic
  type: noul
  instructions: '고객의 이번 발화에서 시스템이 제안한 작업(예: ''이 식당을 예약해 드릴까요?'')을 하는 데 동의하는가?'
  criteria:
    'true': 제안된 작업을 하는 데 동의한다
    'false': 동의하지 않거나, 제안된 작업이 없다
  label: act:AFFIRM_INTENT
- id: act_negate_intent
  role: diagnostic
  type: noul
  instructions: 고객의 이번 발화에서 시스템이 제안한 작업을 하는 것을 거절하는가?
  criteria:
    'true': 제안된 작업을 거절한다
    'false': 거절하지 않거나, 제안된 작업이 없다
  label: act:NEGATE_INTENT
per_item_questions: null
group_key: dialogue_id
"""
BASELINES = {"full": BASELINE_FULL, "actions_only": BASELINE_ACTIONS_ONLY}
EXPECTED = yaml.safe_load(W2_WORDING)


def intent(task):
    return next(q for q in task["questions"] if q["id"] == "act_inform_intent")


def read_pair():
    return {variant: (ROOT / f"configs/tasks/kosgd2_{variant}.yaml").read_bytes()
            for variant in BASELINES}


def assert_w2_pair(payloads):
    wording = [{key: intent(yaml.safe_load(payload))[key] for key in EXPECTED}
               for payload in payloads.values()]
    assert wording[0] == wording[1] == EXPECTED


def test_both_variants_have_exact_w2_instructions_and_criteria():
    assert_w2_pair(read_pair())


@pytest.mark.parametrize("variant", BASELINES)
def test_only_instructions_and_criteria_differ_from_102a097(variant):
    payload = read_pair()[variant]
    current, baseline = yaml.safe_load(payload), yaml.safe_load(BASELINES[variant])
    restored = deepcopy(current)
    for key in ("instructions", "criteria"):
        intent(restored)[key] = intent(baseline)[key]
    # Includes question order, all other questions and top-level metadata.
    assert restored == baseline
    # Stronger byte check also preserves comments, quoting and newlines.
    assert payload.count(W2_WORDING.encode()) == 1
    assert payload.replace(W2_WORDING.encode(), OLD_WORDING.encode()) == BASELINES[variant].encode()


@pytest.mark.parametrize("variant", BASELINES)
def test_independent_audit_accepts_w2_task_sha(variant):
    payload = read_pair()[variant]
    assert approved(yaml.safe_load(payload), f"kosgd2_{variant}", payload)


@pytest.mark.parametrize("old_variant", BASELINES)
def test_one_variant_with_old_wording_is_rejected(old_variant):
    payloads = read_pair()
    payloads[old_variant] = payloads[old_variant].replace(W2_WORDING.encode(), OLD_WORDING.encode())
    with pytest.raises(AssertionError):
        assert_w2_pair(payloads)
    payload = payloads[old_variant]
    assert not approved(yaml.safe_load(payload), f"kosgd2_{old_variant}", payload)
