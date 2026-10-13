# 명세: KoSGD 재구성 감사 스크립트 (kosgd_audit.py)

목적: 평가 계획이 KoSGD 를 "대화당 USER 턴 1개 → 의도 choice + 행동 7개 noul" 로 재구성할 때 생기는 문제의 비율을 잰다.
파이썬 표준 라이브러리 + tokenizers 패키지만 쓴다. 네트워크 금지. 이 디렉터리 밖에 쓰지 않는다.

입력 (모두 읽기 전용, 경로는 인자로 받는다 — 기본값 아래):
- --kosgd   /private/tmp/claude-501/-Users-rainis-Desktop-workspace-source-model-test/aa7fe33a-3991-4573-b7d5-6bce4ff44cd9/scratchpad/data_kosgd      : dialogues_*.json (각 파일은 대화 리스트; 대화 = {dialogue_id, services[], turns[]}; 턴 = {speaker, utterance, frames[]}; frame = {service, actions[{act, slot, values, canonical_values}], slots[], state{active_intent, requested_slots, slot_values}} — state 는 USER 턴에만 있을 수 있음) + extended_schema.json (서비스 리스트: {service_name, description, slots[], intents[]})
- --sgd-en  /private/tmp/claude-501/-Users-rainis-Desktop-workspace-source-model-test/aa7fe33a-3991-4573-b7d5-6bce4ff44cd9/scratchpad/data_sgd_en     : 영어 SGD test, dialogues_*.json (같은 구조, dialogue_id 만 쓴다). schema.json 은 무시
- --tokenizer /Users/rainis/Desktop/workplace/models/Qwen_Qwen3.8_27B/tokenizer.json  (tokenizers.Tokenizer.from_file)

표본 (결정적):
1. 모든 KoSGD 대화를 dialogue_id 로 정렬. rng = random.Random(20261012).
2. rng.sample(정렬된 대화, 3000) → 고른 3000 대화를 다시 dialogue_id 로 정렬.
3. 각 대화에서 speaker=="USER" 턴 중 하나를 rng.choice 로 고른다 (USER 턴이 없으면 그 대화는 건너뛰고 건수 보고).

측정 (고른 턴 기준, 분모 = 고른 턴 수):
(a) len(frames) > 1 인 비율
(b) 어떤 frame 이든 state.active_intent == "NONE" 인 비율, state 가 없는 비율도 따로
(c) 턴의 모든 frame 의 act 빈도표 전체 출력 + ALLOWED = {INFORM, REQUEST, AFFIRM, NEGATE, REQUEST_ALTS, SELECT, GOODBYE, THANK_YOU} 밖 act 를 하나라도 가진 턴 비율 (밖 act 별 건수도)
(d) act 를 7항목(INFORM, REQUEST, AFFIRM, NEGATE, REQUEST_ALTS, SELECT, GOODBYE|THANK_YOU 를 '종료/감사' 하나로) 에 매핑한 뒤 집합이 빈 턴 비율
(e) 입력 길이: text = json.dumps([그 대화의 services 에 해당하는 스키마 항목들], ensure_ascii=False) + "\n" + 첫 턴부터 고른 턴까지 "SPEAKER: utterance" 줄들. Qwen3.8 토크나이저 토큰 수. >8192, >16384 비율, p50/p95/max
(f) 고른 3000 dialogue_id 중 영어 SGD test 에 같은 dialogue_id 가 있는 비율. 있을 때 턴 수가 같은 비율도
R1 = (a) 또는 (c) 또는 (d) 에 걸리는 턴의 합집합 비율

판정 (사전 고정, 출력에 그대로 찍는다):
- R1 > 10% → "R1 FAIL: KoSGD 문항 재설계"
- (e) >8192 비율 > 5% → "R2 FAIL: 잘림/거부 비대칭 먼저 해소"
- (f) < 90% → "R3 FAIL: 영어 짝 비교 제외"
- 각각 아니면 PASS

출력: 사람이 읽는 보고를 stdout 에, 같은 내용을 audit_result.json 에 (입력 파일 수, 대화 수, 건너뛴 대화, 각 지표의 분자/분모/비율, act 빈도표, 판정). 실패 시 0 이 아닌 종료코드는 쓰지 않는다 (판정은 내용으로).
금지: 입력 파일 수정, 네트워크, 이 디렉터리 밖 쓰기.
