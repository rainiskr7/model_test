# KoSGD 감사 v3 — 구현 명세 (Claude 작성, Codex 구현)

규칙의 원문은 `jev_test/JEV_TEST_PLAN.md` §7-1 (사전 등록, 10-13). 이 명세와 충돌하면 §7-1 이 우선이다. 판정 기준을 바꾸지 말 것.

## 0. 제약
- 라벨만 읽는다. **모델 호출·네트워크 없음.** 입력 파일은 읽기 전용.
- `jev_test/dataset/` (AI-Hub) 는 절대 열지 않는다.
- 실행: `<venv>/bin/python -I run.py` (`foundation_model_test_non_thinking/.venv`, `tokenizers` 0.22.2). `-I` 는 `-P` 를 포함해 스크립트 폴더를 `sys.path` 에 넣지 않는다 → `run.py`·`selftest.py` 첫머리에서 자기 폴더를 `sys.path[0]` 에 명시적으로 넣는다.
- **기능별 파일로 나눈다** (아래 §1). `run.py` 는 조립만 한다. 한 파일에 몰지 말 것.
- 규칙 FAIL 이어도 exit 0 으로 끝내고 결과에 FAIL 을 적는다. 입력 이상(파일 없음·중복 ID·형식 위반)은 예외로 멈춘다 (exit ≠ 0).

## 1. 파일 구성
```
audit_v3/
  run.py                    # 진입점: 로드 → 빌드 → 검사 → 통계 → 보고
  config.py                 # 경로 · 상수 (8192, 0.95, seed 파일, 토크나이저 3개)
  common/io.py              # JSON 읽기, 파일 목록 (빈 목록이면 예외)
  common/request.py         # noul/choice 생성자, serialize — length_audit/common/request.py 와 바이트 동일 동작
  load/kosgd.py             # KoSGD test 대화 34 파일 + extended_schema.json
  load/sgd_en.py            # 영어 SGD test 대화
  load/selection.py         # kosgd_audit/audit_result.json 의 selected_turns (3000 개, 순서 유지)
  build/catalog.py          # 서비스 목록 (이름·설명·의도 이름·설명), 선택지 ID "서비스/의도"
  build/wording.py          # 질문 문구 (§3) — 상수만
  build/requests.py         # full / actions_only 두 판의 (state, questions)
  build/labels.py           # 빌더 경로 정답: 칸 묶음 · 행동 noul 10 개
  verify/labels_independent.py  # R7 용 두 번째 경로 — build/·load/ 를 import 하지 않는다, 원본 JSON 을 다시 읽는다
  verify/source_projection.py   # R4(e)(f) 용: 원본에서 대화 투영·catalog 를 따로 다시 만든다 (build/ import 금지)
  selftest.py               # 오류 주입 검사 (§8) — run.py 와 별도 진입점
  checks/length.py          # R2v3
  checks/leak.py            # R4
  checks/coverage.py        # R5
  checks/timing.py          # R6
  checks/consistency.py     # R7
  stats/copy_baseline.py
  stats/version_diff.py
  stats/distribution.py     # ② 칸 NONE 비율, 바뀐 턴 비율
  report/table.py           # stdout 표
  report/json_out.py        # out/result.json
  out/                      # result.json, example_full.json, example_actions_only.json
```

## 2. 입력 (경로는 config.py, scratchpad 기준 상대)
- KoSGD: `data_kosgd/dialogues_*.json` (34), `data_kosgd/extended_schema.json` (서비스 21 · 의도 38).
- 영어 SGD: `data_sgd_en/dialogues_*.json`.
- 표본: `kosgd_audit/audit_result.json` → `selected_turns` (각 `dialogue_id`, `turn_index`; 3000 개가 아니면 예외).
- 토크나이저: `tokenizers/clef/tokenizer.json`, `tokenizers/pplx_v1_1/tokenizer.json`, Qwen3.8 사본 (`length_audit/config.py` 의 `qwen38` 경로). `no_truncation`, `no_padding`, `add_special_tokens=False`.

## 3. 요청 구성 (최종 구성 초안)
- 선택지 ID: `f"{service_name}/{intent_name}"` (서비스 이름은 KoSGD 한국어 이름 그대로, 의도 이름은 영어). 서비스가 달라도 같은 의도 이름이 4 개 있으므로 반드시 접두. ID 중복이면 예외.
- **catalog** (스키마 파일 순서 = "서비스 목록 순서"):
  `[{"service": name, "description": desc, "intents": [{"id": "서비스/의도", "description": 의도 설명}, ...]}, ...]` — 슬롯·required_slots 등은 넣지 않는다.
- **state**: `{"dialogue": [{"speaker", "utterance"} ... 첫 턴부터 대상 USER 턴까지 포함], "catalog": catalog}` — 키 순서 dialogue → catalog.
- **질문** (dict 순서 그대로 직렬화):
  - full: `진행중_1`, `진행중_2`, 행동 8 (INFORM, REQUEST, AFFIRM, NEGATE, REQUEST_ALTS, SELECT, CLOSE, INFORM_INTENT), 진단 2 (AFFIRM_INTENT, NEGATE_INTENT) = 12 질문.
  - actions_only: 행동 8 + 진단 2 = 10 질문.
  - 진행중 criteria: catalog 순서의 의도 38 개 (`ID → 의도 설명`) + `"NONE": "진행 중인 일이 없다 (이 칸에 해당하는 일이 없다)"`.
  - 문구 (build/wording.py):
    - 진행중_1: `"고객의 이번 발화와 관련된 서비스에서 지금 진행 중인 일은? 그런 일이 둘이면 서비스 목록에서 앞에 있는 서비스의 일을 고른다. 없으면 NONE."`
    - 진행중_2: `"고객의 이번 발화와 관련된 서비스에서 지금 진행 중인 두 번째 일은? 그런 일이 둘일 때 서비스 목록에서 뒤에 있는 서비스의 일을 고른다. 하나 이하이면 NONE."`
    - (10-13 수정 사유: '이 턴까지' 는 앞 턴에만 있던 서비스도 포함하는 것으로 읽히는데, 정답은 이번 턴 frame 의 서비스만 담는다 — 예 12_00101 turn 6. 열거형 사유 '지시가 두 가지로 읽힘'.)
    - 행동: `f"고객이 이 턴에서 {설명} 했는가?"` — 설명은 length_audit/datasets/kosgd.py 의 `actions` 사전과 같은 문자열. CLOSE 설명은 `"작별 인사 또는 감사 표현"`, 키 `CLOSE` 는 GOODBYE 또는 THANK_YOU.

## 4. 정답 (build/labels.py)
- USER frame 은 `state.active_intent` 가 문자열이어야 한다 — 없거나 null·다른 타입이면 입력 오류로 멈춘다 (기본값 NONE 으로 채우지 않는다). SYSTEM frame 의 state 부재는 정상.
- 칸 묶음: 대상 턴 frames 중 `active_intent != "NONE"` 인 것의 `서비스/의도` → **중복 제거** → R5(a)(b) 검사(catalog 밖 ID·2 개 초과는 여기서 위반으로 기록하고 그 턴은 정렬·패딩하지 않는다) → catalog 순서(서비스, 다음 의도)로 정렬 → `NONE` 으로 채워 **길이가 정확히 2 인 리스트**. 비교는 정렬된 리스트끼리 (`[NONE, NONE]` 도 원소 2 개).
- 행동 noul: 대상 턴 모든 frame 의 `actions[].act` 합집합에 그 act 가 있으면 true (CLOSE 는 GOODBYE ∪ THANK_YOU).

## 5. 규칙 (§7-1 그대로)
- **R2v3**: 두 판 × 3 토크나이저. 방식 clef = `serialize(state, questions)` 전체 토큰 수, pplx = 질문 하나씩 `serialize(state, {qid: q})` 중 최대. PASS ⇔ 두 판·세 토크나이저·두 방식 모두 > 8192 인 요청 0. p50/p95/max 도 기록 (length_audit/measure/lengths.py 와 같은 percentile 정의).
- **R4**: (a) catalog 의 `json.dumps(ensure_ascii=False)` sha256 이 3000 요청에서 1 종류 (b) 판마다 questions 직렬화 sha256 1 종류 (c) state.dialogue 의 각 항목 키 집합이 정확히 {speaker, utterance}, state 최상위 키가 정확히 {dialogue, catalog} (d) dialogue 길이 == turn_index + 1 이고 마지막 항목이 USER (e) 요청의 dialogue 가 원본 `turns[:turn_index+1]` 의 {speaker, utterance} 투영과 위치별로 완전히 같다 (verify/source_projection.py) (f) catalog 가 verify/source_projection.py 가 스키마에서 따로 만든 catalog 와 같고, questions 가 build/wording.py 상수로 만든 것과 같다 (문구 sha256 기록). PASS ⇔ (a)–(f) 전부.
- **R5**: 3000 턴에서 (a) NONE 이 아닌 active_intent 의 `서비스/의도` 가 catalog ID 에 없음 (b) 서로 다른 진행 중인 일 > 2 (c) act 가 11 종 {INFORM, REQUEST, AFFIRM, NEGATE, REQUEST_ALTS, SELECT, GOODBYE, THANK_YOU, INFORM_INTENT, AFFIRM_INTENT, NEGATE_INTENT} 밖. PASS ⇔ (a)+(b)+(c) = 0.
- **R6**: 관측 단위 = KoSGD test **전체 대화**의 USER 턴 (turn, frame) 중 INFORM_INTENT action 이 있는 frame. X = 그 action 의 `values` 가 **문자열 1 개짜리 리스트**일 때 그 값. 형식이 다르거나(빈 리스트·여러 값·문자열 아님) 한 frame 에 INFORM_INTENT action 이 여러 개면 **불일치로 분모에 남기고** 건수를 따로 적는다 (분모에서 빼지 않는다). 같은 턴 그 frame 의 active_intent == X 비율. PASS ⇔ ≥ 0.95. 분모 0 이면 INCONCLUSIVE (PASS 아님). 함께 (판정 없음): **바로 이웃한** 직전·다음 USER 턴에 같은 서비스 frame 이 있을 때 그 active_intent == X 비율, 이웃 USER 턴에 같은 서비스 frame 이 없는 건수, 3000 표본 안에서의 같은 비율. 해석은 'INFORM_INTENT 가 있는 frame 에서 라벨이 같은 턴에 반영된다' 까지만.
- **R7** (의미: 구현 일치성): build 경로는 요청마다 `{request_id, labels: {질문ID: 값}}` 을 만든다 (request_id = `dialogue_id#turn_index`, 질문 ID 는 요청 questions 의 키와 같은 집합; 칸은 `진행중` 키 하나에 길이 2 리스트). verify/labels_independent.py 는 원본 파일과 selection 만 입력으로 같은 구조를 따로 만든다. 대조: request_id 집합·건수 일치, 판마다 labels 키 == 그 판 questions 키 집합(칸 두 질문은 `진행중` 하나로), 값 타입(bool / 길이 2 리스트), 값. 추가로 verify 모듈은 자기 상수표(act → 설명)를 따로 갖고, 요청 questions[act].instructions 에 그 설명이 들어 있는지 확인한다 (질문 문구–정답 키 뒤바뀜 검출). PASS ⇔ 전부 일치. verify/ 는 build/·load/ 를 import 하지 않는다 (common/io.py 만 허용).

## 6. 통계 (판정 없음)
- **copy_baseline**: 같은 대화의 바로 이웃한 직전 USER 턴 칸 묶음을 답으로 — 첫 USER 턴이면 `[NONE, NONE]`. 3000 턴 정답률. 변화율은 두 가지로 따로: (i) 첫 USER 포함(이전을 NONE 으로 본 것) (ii) 실제 직전 USER 가 있는 턴만. 첫 USER 표본 수도 적는다.
- **frame 빠짐**: 직전 USER 턴에서 NONE 이 아닌 의도가 있던 서비스가 이번 턴 frame 에 없는 표본 턴 수 (문구 '이번 발화와 관련된 서비스' 가 필요한 이유의 크기).
- **distribution**: ② 칸이 NONE 인 비율, 진행 중인 일 0/1/2 개 턴 수 (frame 수와 따로), frame 1/2 개 턴 수, 행동별 양성 수.
- **version_diff**: 3000 턴에 대해 같은 dialogue_id·turn_index 의 영어 SGD 턴. 먼저 대응 턴 존재·발화자 일치·frame 수 일치를 센다 (불일치 턴은 그 턴의 칸 비교를 INCONCLUSIVE). 서비스 이름 대응표 = frame 수가 같은 턴에서 위치로 짝지은 (한국어, 영어) 쌍 — 1:1 이고 **이름 끝 번호(`_3` 등)가 같아야** 유효. 아니면 `mapping_valid: false` 로 적고 칸 묶음 비교 전체를 INCONCLUSIVE (행동 비교는 대응표가 필요 없으므로 계속). 질문별 불일치 수 (칸 묶음 1 + 행동 10), "성공 판정 질문 중 하나라도 불일치" 턴 수 (full: 칸+행동 8 / actions_only: 행동 8). 영어 턴의 frame 수가 다르면 그 수도.

## 7. 출력
- `out/result.json`: 지문 — SPEC.md·모든 .py·문구 상수의 sha256, 판마다 전체 요청 직렬화를 줄바꿈으로 이은 sha256. 입력 파일 목록·sha256, 표본 수, 각 규칙 {status: PASS|FAIL, 분자, 분모, 위반 예시 최대 5 개 (dialogue_id, turn_index)}, 통계, 토크나이저 파일 sha256, python·tokenizers 버전, 실행 시각.
- `out/example_full.json`, `out/example_actions_only.json`: 표본 첫 요청의 직렬화 그대로 (검토용).
- stdout: 규칙별 한 줄 `R? STATUS 분자/분모` + 길이 표 + 통계 요약. 마지막 줄 `PRIMARY_VARIANT: full|actions_only|STOP` (§7-1 결과 처리 규칙: 모두 PASS → full; 하나라도 FAIL → actions_only; 단 actions_only 의 R2v3 나 R4 가 FAIL 이면 STOP). R2v3·R4 는 판별로도 상태를 낸다.

## 8. 자체 점검 (Codex 가 돌려도 되지만 PASS 근거는 아님 — Claude 가 다시 돌린다)
- `python -I run.py` 가 끝까지 돈다. `result.json` 이 JSON 으로 읽힌다.
- `python -I selftest.py`: 메모리에서 아래 오류를 하나씩 주입해 해당 규칙이 **FAIL** 하는지 확인, 하나라도 FAIL 하지 않으면 exit 1. (1) 한 요청의 USER 발화 끝에 정답 의도 ID 를 붙임 → R4 (2) 한 요청의 대화를 미래 턴까지 늘림 → R4 (3) 모든 요청에서 INFORM·REQUEST 질문 문구 교환 → R7 (4) 한 요청의 칸 정답에서 의도 하나를 NONE 으로 → R7 (5) 한 요청 labels 에서 키 하나 삭제 → R7 (6) catalog 에서 의도 설명 하나 변경(모든 요청) → R4.
- verify/ 독립성: `grep -n "import" verify/*.py` 에 build/·load/ 가 없다.
