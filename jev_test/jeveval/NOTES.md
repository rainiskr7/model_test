# 세부 규칙·기존 시험·이전 구현 결정

모든 dataclass는 frozen이다. 내부 list/dict까지 불변인 것은 아니다. from_dict는 중첩 타입을 복원하고 별칭 없는 사본을 만들며 알 수 없는 필드·필수 필드 누락·비선택 필드의 null·잘못된 타입·NaN/Infinity를 거부한다.
B1Response는 메모리 로그확률의 -inf를 JSON 왕복 때만 "-inf"로 인코딩하고 복원한다. CallRecord.top_logprobs_raw에는 storable_top_logprobs가 만든 사본을 넣는다.
ThresholdFile은 by_tau 키와 값의 tau가 같은지도 검사한다. 요청·응답·채점 도메인 검사는 contract/score, 순수 상태 결합은 run/outcome, 전송·기록 순서 제어는 executor의 책임이다.

load_taskspec은 TaskSpec을 반환하며 오류 목록은 TaskSpecError.errors에 담는다. task yaml의 score 질문은 기존대로 오류 목록이며 NotImplementedError로 바꾸지 않는다.
per_item_questions의 충돌 검사는 k 상한 없이 앞자리 0 없는 양의 정수를 대조한다. 실제 질문 펼치기와 중복 재검사는 data/expand가 수행한다. 무상한 패턴 충돌은 taskspec이 검사한다.
Request가 봉투 구조를 보장하고 build_request가 질문 ID 중복을 거부한다. systemone criteria는 options 순서를 보존하며 B1만 코드포인트 순서로 라벨을 배정한다.
usage 없음/null은 usage_input_tokens_invalid 경고를 내지 않는다. 추가 봉투 키 경고는 별도다. 응답 검증 실패 시 answers는 None이며, 그때까지 수집한 경고는 중복 없이 보존한다.
B1 allowed_token_ids는 client가 채운다. calibrate의 모집단 구성은 호출자 책임이다. client는 재시도·terminal·상태 결합을 결정하지 않는다. 본문 수신 오류는 HTTP 코드와 함께 남긴다. headers는 전송에만 사용하고 Content-Type 덮어쓰기·머리글 값의 예외 메시지 노출을 막는다.
missing_for_run의 B1 라벨 인자는 b1.yaml에서 읽어 전달한다. 생략하면 incomplete로 판정한다.
timeout은 소켓 단위이며 총 소요 시간 상한이 아니다. clock.utc_now()는 aware datetime을 돌려준다.
resume은 append 전에 repair_tail을 호출해야 한다. read_attempts/read_finals는 파일을 바꾸지 않는다. 재시도 5회는 기록된 시도 기준이다. 전송 뒤 fsync 전에 중단되면 실제 전송이 더 일어날 수 있다.
call_record는 상한에 이른 non-terminal도 재전송 없이 복구하며, 상한 초과·기록 연결 불일치는 거부한다.
plan_calls·length·policy·outcome·resume_check·derive는 순수 함수다. B1은 hf_chat_template_no_think로 로컬 측정하며 systemone 측정은 NotImplementedError다.
score/tasks는 KoSGD 한 칸만 MISSING이면 상태와 무관하게 거부하고, 두 칸 모두 MISSING이면 묶음을 마스크에서 뺀다.
score/threshold의 호출자는 dev_complete를 통과한 dev 결과와 원본 바이트 sha256·nbytes를 넘긴다. certify는 ⑥b다.
score/risk도 완료된 dev/test 대표 집합을 받는다. stage·중복 대표·Item ID·threshold/dev 집계를 대조하고 시험으로 임계값을 다시 고르지 않는다.
위험의 세부 분포도 빈 마스크를 제외한다. 길이 미측정 로컬 오류는 unmeasured에 세며 다섯 칸 sampled 합은 test.n_denom이다. valid 요청에는 측정 길이가 필요하다.
n_min은 (1-tau)**n <= 0.05를 Fraction으로 비교한다. b_flip은 MEETS에서만 쓰며 바꿀 정답이 없는 k=n 입력은 ValueError다.
risk_file은 세 tau의 RiskCell을 일반 JSON dict로 복사한다. cost_by_stage는 Cost 객체를 유지하며 ScoreTable.to_dict()/io.run_files.json_bytes가 중첩 값을 직렬화한다.
cost 호출자는 완료 final과 연결된 시도, 명시적 kind(b1/systemone), 단계 derived.json의 출처를 전달한다. 토큰은 CallRecord.usage가 아닌 마지막 terminal의 원문에서 읽고 미측정 호출도 missing에 센다.

⑥a-2b population 호출자는 test 대표 또는 FunctionChat dev+test+extra를 골라 outcomes/finals를 넘긴다. 두 ID 집합은 같아야 하며 Item은 빈 공통 코호트에도 질문 틀을 남기도록 상위 집합을 허용한다. outcome을 final/Item에서 재계산해 대조한다. 요청 오류와 KoSGD 묶음 정답은 칸별 고정 정답 점수와 분리한다. 칸 없는 행동판 set_specific은 {}다. 질문 경고는 ok ParsedAnswer의 answer/probs에서 다시 세며 정답 MISSING도 경고 집계에는 남는다.
qstats의 tool은 동결 FunctionChat 도구 질문 ID다. population은 fc:tool 라벨로도 이를 식별한다. KorFin은 관측을 먼저 합쳐 pooled.aspect를 계산하고 aspect_not_in_text.wrong도 {num,den}으로 남긴다.
compare 호출자는 check_comparable로 분할/task sha와 시험 ID 집합을 확인한 뒤 common_cohort(..., "test")를 사용한다. FunctionChat 전체 행 F1에는 common_cohort(..., "all_rows")를 별도로 쓴다. compare_file의 공통 Population은 test 기준이며 bootstrap 결과는 별도 전달한다. ID 해시는 정렬 ID를 LF로 연결한 UTF-8 바이트(끝 LF 없음)의 SHA-256이다.
F1 입력은 gold 있는 ok Observation만 만든다. KoSGD gold는 고정 칸 정답, KorFin pooled 관측은 question_id="aspect"로 바꾸되 요청당 여러 관측을 유지한다. f1_diff는 전달된 코호트·질문의 관측을 묶음 단위로 재표집하며 모델별 정답/관측 다중집합이 다르면 거부한다. coverage_diff는 같은 시험 대표 ID·묶음·마스크를 요구하고 빈 마스크만 제거한다. 실패는 수락 0, NO_THRESHOLD도 수락 0이다.
bootstrap 반환은 {models, n_groups, reps, pairs}; F1은 question_id도 포함한다. pairs의 각 셀은 {models: [a,b], estimate: a-b, ci95: [lo,hi], n_defined}이며 모델·묶음은 정렬한다. 95% 백분위는 비용 백분위와 같은 (n-1)p 선형 보간이다. 정의되지 않는 빈 모집단의 estimate/CI는 null이며, 정의되지 않은 반복을 버려 조건부 CI로 만들지 않는다.

`run_stage` 전에는 반드시 `gate.prepare_stage`를 호출한다. 실행기는 tail 복구·fingerprint·seal을 하지 않는다. 모든 항목(완료 항목 포함)의 계획과 기존 시도를 먼저 대조하고, 통과 후 빈 기록 파일 생성→측정→post→attempt fsync→대기/다음 호출→final fsync 순서다. 부모 폴더는 gate가 만든다.
반환은 **RunSummary만**이다. records 읽기 경고는 재반환하지 않으며 gate의 경고를 호출자가 보존한다. `n_calls`는 이번에 처리한 호출 수(로컬 오류·복구 포함, 완료 final skip 제외), `by_status`는 이번에 쓴 final만 센다. `session_id`는 호출자가 프로세스별 UUID4를 한 번 만들어 전달하고 재개 프로세스에서는 새 값으로 바꾼다.
non-terminal 재개는 잠 없이 다음 기록 번호로 전송한다. 기록 k 다음 전송(k+1)이 fsync 전에 중단되면 재개는 **같은 k+1**을 사용한다. 실제 전송 1회 추가가 가능한 기록 예산의 한계이며 cost는 미기록 전송을 관측할 수 없다. 5회째 non-terminal 복구는 과거 attempts를 고치지 않는다.
`derive_stage(full_finals, items_full, action_qids, derived_from)`는 완료 ID 집합을 대조한다. 파생 호출의 attempts·usage·length는 원본 관측값을 유지하며, 논리 상태는 제거된 B1 호출의 오류도 보존한다. 호출자가 separate 모델·같은 단계의 전체판을 선택하고 파생 판 자체의 gate/threshold/seal을 적용한다(⑥b).
`io.derived_stage.write_derived_stage`도 gate 통과 뒤 호출한다. 출처가 일치하는 final 접두 기록은 이어 쓰고, 변경/중복/실제 attempts는 쓰기 전에 거부한다. `derived.json`을 final append 전에 기록하므로 중단 후 재개가 가능하다. 빈 단계도 final·빈 attempts·출처 파일이 생긴다.
⑥a-2a cost는 `<stage>/derived.json`에서 전달받은 `derived_from`으로 파생을 판별하고 **모든 수치 0·p50/p95 null**을 적용한다. 남긴 CallRecord의 attempts/usage를 비용으로 합산하지 않는다. population/risk는 보존된 final 상태와 파생 Item을 사용한다.

## 테스트

- `tests/score/population_support.py`: 원본 데이터 없는 Item/final/outcome 합성 도우미.
- `tests/score/test_population.py`: 기존 F1·보정·MISSING fixture, 경고 재계산·B1·빈 코호트·입력 대조·scores/1 왕복.
- `tests/score/test_population_sets.py`: FunctionChat test/all_rows·도구 분모, KorFin pooled, KoSGD 칸 Brier·묶음·베끼기·전체 결측.
- `tests/score/test_compare.py`: 기존 코호트 fixture의 정확한 교집합·C4 거부·정렬 ID 해시·compare/1 사본.
- `tests/score/test_bootstrap.py`: 결정성·실패 포함 처리율·고정 임계값·공유 묶음 재표집·복수 aspect·FunctionChat 전체 행·빈 코호트.

- `tests/score/test_risk.py`: 기존 CP·위험 상태·임계값 fixture를 실제 함수에 통과, risk/1 직렬화·입력 대조.
- `tests/score/test_risk_mix.py`: missing_mask의 실제 채점→위험 경계, 고정 칸·서비스 중복·KLUE 층·KorFin 1–8 질문·진단·길이 경계·unmeasured 분모 불변식.
- `tests/score/test_cost.py`: 기존 cost fixture의 JSONL 읽기→비용 경계, usage 타입·kind·terminal·로컬 오류·resume·파생·ScoreTable 직렬화.
- `tests/run/conftest.py`, `executor_support.py`: 합성 설정·시도·실제 gate 연결·R3 메모리 계획 치환.
- `tests/run/test_executor.py`: 순차 실행·Retry-After·바이트·fsync 순서·B1 오류 후 계속·빈 단계.
- `tests/run/test_executor_fixtures.py`: 기존 완료/중복/terminal/retry_budget과 B1 부분 답 구조를 실제 실행기에 통과.
- `tests/run/test_executor_interrupt.py`: terminal fsync 뒤 복구·미기록 번호 재사용 한계·B1 호출 사이 재개.
- `tests/run/test_resume_check.py`: 전체 기록 선검사·완료/뒤 항목 오류의 무변경 거부·non-terminal 소진.
- `tests/run/test_derive.py`, `tests/io/test_derived_stage.py`: 파생 상태/사본·질문/완료 대조·출처·중단 재개·빈 dev 봉인.
- `tests/run/test_executor_live.py`: 실제 client의 loopback 503→200; bind 권한 거부만 skip.
- `tests/run/test_plan_calls.py`, `test_length.py`, `test_policy.py`, `test_outcome.py`: 계획·길이 경계·재시도·응답/B1/복구 fixture와 상태 결합.
- `tests/run/test_encoders.py`, `test_encoder_trim.py`: 합성 WordLevel/BPE·해시·오프라인 로드·offsets·Jinja trim 경계.
- `tests/types/`: 합성 표본과 전체 타입 왕복·frozen·null/비유한 수 거부·별칭 없는 사본·CallPlan 메모리 경계.
- `tests/contract/test_model_config.py`, `test_b1_response.py`: 모델 설정·실행 누락·B1 로그확률/usage·기록 연결.
- `tests/io/test_models.py`, `test_hashes.py`, `test_run_files.py`, `test_records.py`: 설정·해시·정규 JSON·원자 교체·JSONL 복구/연속성/fsync.
- `tests/client/`: 가짜 전송/시계·loopback·proxy/리디렉트 금지·부분 응답·봉투/라벨 바이트·AttemptRecord.
- `tests/conftest.py`: 격리 Python 경로·동명 시험의 importlib 수집.
- `tests/contract/test_taskspec.py`, `test_render.py`, `test_request.py`: 질문/target 경계·렌더 바이트/해시·요청 ID/타입/선택지/중복/사본.
- `tests/contract/test_response.py`, `test_b1_prompt.py`: 응답 fixture·사유/usage 경고·B1 라벨/문구/설정 사본.
- `tests/score/test_answers.py`, `test_f1.py`, `test_calibration.py`: 답/B1·F1·보정 fixture·동률/중복·클래스/길이/bin 경계·파서 연결.
- `tests/score/test_kosgd_slots.py`, `test_tasks.py`, `test_threshold.py`: 칸/Brier·MISSING·B1 병합·상태/길이/사본·임계값/seal 재계산·위험 경계·dev 완료/단계 분리.
- `tests/io/test_tasks.py`: 목록 순서·중복 JSON·B1 필수 키·틀 오류.
- `tests/score/test_labels.py`: 모든 규칙 양/음성·정답 누락·타입·도구 호출·카탈로그 순서.
- `tests/data/test_expand.py`: 기존 KorFin fixture·무상한/실제 ID 충돌·중괄호·정답 클래스.
- `tests/data/items/conftest.py`: 동결 task와 합성 SplitPlan 준비.
- `tests/data/items/test_kosgd.py`, `test_functionchat.py`: 두 판·직전 USER·카탈로그/묶음·도구 선택지·extra·원본 불변.
- `tests/data/items/test_kmhas.py`, `test_kote.py`: 단계/분할·동결 설정/B1·과반수·감정 강등·라벨 충돌.
- `tests/data/items/test_korfin.py`, `test_klue_mrc.py`: SID/정답/flag 연결·state·bool·층·빈 단계 요약.
- `tests/run/test_item_summary.py`: tmp_path CLI 전체 경로·extra·원문 누출 없음·오류 종료.
- `tests/io/test_config.py`: 안전 YAML·중복 키·검사기 위임.
- `tests/io/test_sources_kosgd.py`: USER 위치·dialogue·services·파일 순서·선정 읽기·중복 대화 거부.
- `tests/io/test_sources_functionchat.py`: system 선행·중첩 도구·첫 USER 기준의 전이 연결.
- `tests/io/test_sources_kmhas.py`: 물리 행 번호와 Python 라벨 목록.
- `tests/io/test_sources_kote.py`: info 메타데이터 경로와 메타데이터 누락 거부.
- `tests/io/test_sources_korfin.py`: SID 행 순서 보존과 SRC별 단일 항목.
- `tests/io/test_sources_klue_mrc.py`: 답변 불가능 행을 포함한 guid·중첩 answers 보존.
- `tests/data/test_grouping.py`: 기존 union-find·충돌 fixture, 숫자 최소·문자열 정렬·ID/source 거부.
- `tests/data/test_pool.py`: 기존 추출·비례 fixture, 동률·cap·빈 모집단·잘못된 고정 선정.
- `tests/data/test_split.py`: 기존 중간 shuffle·최종 정렬, 풀 대표 강등·충돌·extra·KorFin 행 수.
- `tests/io/test_splits.py`: 고정 바이트·왕복·입력 순서 불변·한글 감정 강등과 원문 제외.
- `tests/run/test_make_splits.py`: 여섯 합성 셋 CLI 두 번의 바이트 일치·단일 셋·expect_groups 실패.
- `tests/fixtures/test_fixtures_wellformed.py`: JSON·README·CP·temperature·바이트·정확한 대상 prefix·canary 입력.
- `tests/fixtures/reference_scoring.py`: 테스트 전용 독립 F1·보정·임계값 참조 계산.
- `tests/fixtures/test_scoring_fixtures.py`: 빈 bin·빈 채점·빈 마스크·21묶음 분모·코호트·pooled 검산.
- `tests/fixtures/test_answer_fixtures.py`: API 확신·B1 교환 동률·누락 라벨·고정 칸 Brier.
- `tests/fixtures/test_record_fixtures.py`: 다섯 기록 사례·길이 상태·KorFin 연결·terminal 복구 기대값.
- `tests/fixtures/test_cost_fixtures.py`: 논리 완료 지연·백분위·세션 제외·토큰·파생 비용.
- `tests/fixtures/test_seal_fixtures.py`: 바이트 해시·개발 임계값 재계산·mtime·resume 교체 거부.
- `tests/fixtures/test_split_fixtures.py`: ID 묶음·라벨 충돌·연결요소·분할·비례 할당.
- `tests/fixtures/test_resume_fixtures.py`: JSONL 손상·중복·완료 ID·누적 재시도 자료.

fixture 폴더: render, responses, answers, scoring, splits, expand, records, resume, length, seal, temperature, b1, canary. 각 README는 한 줄이다. fixture 검산은 실제 실행 모듈 통합 테스트를 대신하지 않는다. 작업 ②·⑤b·⑥a-1 짝 테스트는 기존 fixture를 실제 함수에 통과시키며 기대값은 변경하지 않는다.
- `tests/run/test_fingerprint.py`: 기존 비교 fixture·실제 파일 해시·원본/토크나이저 변조·null/등록 규칙.
- `tests/run/test_stage_inputs.py`: 합성 FunctionChat의 세 단계·읽기 불가 test/extra와 dev 경로 격리.
- `tests/run/test_gate.py`: resume fixture·검사 전후 전체 디렉터리 불변·완료 검사·현재 단계 tail 복구.
- `tests/run/test_seal.py`: 기존 seal fixture의 첫 진입/재진입 분리·바이트 해시·mtime·덮어쓰기 거부.
- `tests/run/stage_support.py`: 위 짝 테스트의 합성 실행 폴더·분할·전체 바이트 스냅샷 도우미.
추가 fixture `tests/fixtures/b1/prompt.json`은 합성 설정으로 choice/noul 문구·매개변수를 고정한다. canary는 표식 있는 입력만 만들며, 일곱 커밋 출력의 누출 검사는 작업 ⑥에서 한다.

검사: `../foundation_model_test_non_thinking/.venv/bin/python -I -m pytest -q -p no:cacheprovider -rs tests`

실제 데이터 미리보기 (저장소 루트에서, `-I` 경로 처리는 실행 명령에만 둔다):

```sh
../foundation_model_test_non_thinking/.venv/bin/python -I -c 'import runpy, sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); runpy.run_module("jeveval.run.make_splits", run_name="__main__")' --rules configs/splits/rules.yaml --root . --set all --out .work/splits_preview
```

분할 파일에는 평가 풀 묶음만 담는다. KOTE 강등 이름만 한글을 허용하며 원문 묶음 키는 저장하지 않는다. `pool_rule`은 YAML pool 객체 그대로, 바이트는 `ensure_ascii=False, indent=1, sort_keys=True`와 끝 LF다.
`Groups`·`PoolResult`는 frozen JsonRecord이며, strata 입력은 group_id→층 이름이다. KoSGD 고정 선정은 원본 USER 구성원 존재 여부로 검증한다 (없는 대화·중복·SYSTEM·범위 밖 거부).
CLI의 상대 `--rules`와 source/선정 경로는 `--root` 기준, 상대 `--out`은 실행 cwd 기준이다.

## SPEC_AMBIGUOUS

⑥b-1: 실행 명령·summary·canary와 반박 R1–R7을 구현했다. 아래 실행 순서와 후속 인수조건을 따른다.

⑥a-2b: R1–R3 반영. 추가 SPEC_AMBIGUOUS / FIXTURE_CONFLICT 없음. missing_mask fixture의 present는 사례마다 noul과 NONE choice를 나타내므로 통합 시험에서는 NONE 사례만 별도 질문 ID로 연결한다. fixture 파일과 각 사례의 정답·예측·상태는 변경하지 않는다.

⑥a-2a: R1 반영으로 미측정 길이의 모호성은 해소했다. risk_cases.json은 질문/길이 입력 없는 집계 예이므로 인증 필드(상태·dev/test·by_status·플래그)를 대조하고 빈 세부 분포 자리는 별도 합성 Item 시험으로 검증한다. fixture는 수정하지 않았다. 추가 SPEC_AMBIGUOUS / FIXTURE_CONFLICT 없음.

⑤c: 명세 B2의 `read_stage_finals -> list[FinalRecord]`와 경고 반환 요구는 함께 만족할 수 없어 기존 `io.records.read_finals`의 `(records, warnings)`를 따른다.
`code_sha256` 경로는 root 기준 POSIX 상대 경로(`jeveval/...`)로 고정한다. 상대 tokenizer.path도 root 기준이다. path가 있는데 해시 목록이 null/빈 경우는 검증 불가로 거부한다.
extra는 명세 B4.3 그대로 test 대표 완료와 **존재하는** seal만 검사한다. seal 누락 자체를 거부하는 규칙은 아직 없다.
FIXTURE_CONFLICT: `seal/cases.json`의 tampered/hash_mismatch/dev_changed는 start_allowed=true지만 기존 seal을 설치하면 명세 B4.2·계약 §8-6 A에 따라 거부해야 한다. start_allowed는 봉인 전 첫 진입으로 시험하고, 제공된 seal을 설치한 resume는 별도 거부 시험으로 고정했다. 기존 fixture는 수정하지 않았다. certify의 재계산·mtime 판정은 ⑥b 범위다.
gate는 tail 복구의 중간 손상/잘못된 기록 거부도 쓰기 전에 발견한다. 검사 거부 메시지에 원문을 넣지 않는다. 이 순서는 단일 실행자 기준이며 외부 동시 변경의 트랜잭션 격리를 제공하지 않는다.

⑤d SPEC_AMBIGUOUS / FIXTURE_CONFLICT 없음: R1–R5 반영. 기존 fixture는 수정하지 않는다. 시험에서만 R3대로 계획의 해시/바이트를 메모리 치환하며 B1 partial은 상태·사유·답 키 구조만 비교한다.
②·③a 반박은 보정 4·6으로 해결했다. 당시 승인된 fixture 변경은 union_find 구성원 11–15 문자열화·label_conflicts notes 키 변경이며 deterministic.json은 불변이다.
§10의 systemone 서버 인코더·길이 거부 응답 확인은 P0 후속 작업이다. B1 로컬 offsets 생성은 구현했다.
⑤a SPEC_AMBIGUOUS: threshold_cases의 232개 축약 outcome에는 질문 ID가 없어 roles={}로 추가했다.
길이 fixture는 합성 LengthInfo 입력이다. ⑤b·⑥a-1의 남은 SPEC_AMBIGUOUS / FIXTURE_CONFLICT는 없으며 부분 결측은 §7-2대로 거부한다.
P0-B1: null/빈 해시 목록은 미확정으로 거부한다. user는 하나이며 state 접두사·trim 뒤 본문의 유일성을 검사하고 앞 공백만큼 state 범위·대상 끝을 보정한다. 전부 공백 state·state로 끝나는 user·state까지 침범하는 뒤쪽 trim은 거부한다. offsets는 start 비감소·0 ≤ start ≤ end를 요구하며 겹침·반복을 허용하고 대상 문자를 덮는 마지막 토큰 다음 번호를 반환한다. state 시작 경계를 가로지르는 음수 상대 offset은 ValueError이며 임의로 자르지 않는다.

작업 ③b: 반박 반영 R1–R6 구현. extra 의미 검사는 구성원 소속을 검사한다. 라벨 변경 감지는 fingerprint 입력 해시 검사로 남긴다. 정답 규칙은 누락을 MISSING으로 대체하지 않는다. 요약은 dev/test/extra별이며 noul 선택지 수는 2, flag 접두별 항목 수를 센다.

```sh
../foundation_model_test_non_thinking/.venv/bin/python -I -c 'import runpy, sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); runpy.run_module("jeveval.run.item_summary", run_name="__main__")' --rules configs/splits/rules.yaml --root . --tasks configs/tasks --splits configs/splits --task all
```


판 4 변경 기록(10-19): 이전 기록은 보존하고 다음 규칙을 추가한다.

- choice confidence는 모델 고유 수락 확신이다. 유한·0–1 구조는 choice_pick 오류, 선택 확률과 1e-9 초과 차이는 통과 요청에만 confidence_differs 경고다. T0도 최종 통과 때만 경고를 합친다.
- ECE는 probs[answer]를 bin·평균 확신에 사용하며 s_i의 min confidence는 유지한다. 같은 코호트의 Brier/log loss 계산식은 불변이다.
- replay는 검사 후 출처 바이트 복사와 replay/1 metadata만 기록한다. run --offline이 전체 계획 검사 뒤 복구 가능한 논리 요청만 판정하며 나머지는 n_deferred다.
- offline의 post는 거부 함수, 인증 헤더는 빈 객체다. T0·누락 설정·길이 측정·fingerprint·gate 검사를 유지한다. test 일부 완료는 채점/비교/보존/파생할 수 없다.
- replay의 final 존재 거부를 우선한다(계획 2판 C6와 충돌). 멱등 복사는 offline 전에만 가능하며 원 copied_at·reason을 보존한다. 다음 전송은 일반 run으로 재개한다.
- 원 시각·토큰을 재사용해도 실패율·지연 모집단은 새 final에서 계산한다. 파생 판 final의 derived_from은 새 run 경로로 바뀌므로 C3는 출처 치환·threshold dev 해시 제외를 적용한다.
- audits/replay_20261019의 C2/C3/C4 도구는 원문 없는 집계만 출력하며 실제 데이터 실행은 별도 작업이다. 기존 audits는 수정하지 않는다.

## 판 5 Phase A 변경 기록

기존 fingerprint/replay/offline 비교는 그대로다. 코드·공용 설정 변경으로 기존 run이 현재
restore를 거부하는 것이 정상이며, 역사 읽기는 별도 증거 검사를 사용한다.
summary의 run_id 부재/비주판 summary 부재는 기존 스키마 그대로 유지한다.
역사 재구성은 task/split/lists/데이터 manifest와 실제 request hash를 확인한다. 파생 판의
원본 full 재구성 정책은 아직 정하지 않아 역사 question-risk는 그런 입력을 거부한다.
`ongoing_two`는 service/intent 집합 크기를 사용한다. 동일 서비스에 서로 다른 두 의도가
있을 때 “서로 다른 서비스” W1과 충돌할 수 있으므로 Phase B 감사에서 INCOMPLETE로 중단한다.

기존 시험 node는 제거하지 않는다. 명세 확장으로 변경되는 기존 기대값은 frozen task 수
7→9, 라벨 규칙 수33→34, reader의 set_name 키워드 전달이다. Harness는 family를 기준으로
동일한 기존/별칭 합성 실행을 구성한다. 새 node는 역사 손상/공개 canary/질문 동치/가족
집계/선정 배제/원본 파일 해시 앵커를 확인한다. 전역 split seed/dev_fraction은 바꾸지 않는다.

Phase B 미정 사항: 새 선정이 옛 풀 밖의 USER 있는 모든 대화를 쓰면 kosgd+kosgd2 풀 합집합에
가족 전체가 들어가 T0의 풀 밖 원본이 남지 않을 수 있다. 현재 코드는 그 경우 거부하며
합성 fixture 대체나 제외 범위 변경은 자동으로 결정하지 않는다. 기존 T0로 이미 노출된
대화가 새 풀에 들어가는지도 Phase B에서 별도로 확인해야 한다.

## Phase A 최종 검증 기록 (2026-10-19)

Phase A만 구현했다. 커밋·모델 호출·실데이터 검증·Phase B 실행은 하지 않았다.
루트 results/dataset/.work는 생성하거나 읽고 쓰지 않았다. 합성 시험 임시 파일은 작업 cwd 안에서만 만들고 제거했다.

실행 환경의 PATH에 기존 venv를 넣고, PYTHONDONTWRITEBYTECODE=1과
PYTEST_ADDOPTS='--basetemp=.phase_a_tmp -rs'를 사용했다.

```text
$ python -m pytest tests -q -p no:cacheprovider
2 failed, 2324 passed, 25 skipped in 48.82s
```

실패는 기존 HEAD를 별도 임시 디렉터리에 추출한 시험에서도 재현했다(2 failed, 6 passed).
두 node는 tests/io/test_models.py::test_six_registered_models_and_pending_run_fields와
tests/io/test_models.py::test_systemone_encoder_limits_and_manifest[pplx_v1_1]이다.
원인은 pplx_v1_1의 실제 YAML이 HTTP 400/does not fit인 데 비해 시험은 HTTP 422/exceeds를 기대하는 차이다.
모델 YAML과 해당 시험은 범위 밖이므로 수정하지 않았다. 따라서 C1 전체 통과는 미달이다.
25 skip은 기존 live loopback 시험의 sandbox bind 제한이며 새 skip/xfail은 없다.

기존 node 2259, 현재 2351, 추가 92, 삭제 0. 새 skip/xfail 0. 코드 크기/경계 위반 0. 보존 SHA 일치.
git diff --check도 통과했다. 실데이터 C2~C5 및 Phase B 검증은 수행하지 않았다.

교체·삭제한 기존 node: 없음. 기존 node의 기대값 수정은 아래와 같다.

- tests/data/items/test_kmhas.py::test_all_frozen_tasks_and_b1_template: task 개수 7→9.
- tests/score/test_labels.py::test_all_rules_reject_missing_fields_and_unknown_name: 규칙 개수 33→34.
- tests/io/sources/test_init.py::test_only_kote_receives_votes_config의 기존 6 parameter node: set_name 전달 기대 추가.

파일별 한 줄 요약(총 94개, M=기존 수정, A=신규·미추적):

| 상태 | 파일 | 변경 |
|---|---|---|
| M | `JEV_TEST_PLAN.md` | 개정 15와 W1·파일럿 1회 게이트·선정·감사·질문 위험 등록 절차를 이력으로 추가. |
| M | `P1_CONTRACT.md` | 판 5의 family·역사 검증·보고·질문 위험·감사 v4 계약을 추가. |
| M | `README.md` | 판 5 Phase A 문서와 실행 안내로 연결. |
| M | `audits/README.md` | kosgd2 선정 도구와 Phase B 감사 v4/v5 예정 범위를 명시. |
| A | `audits/kosgd2_selection/select_turns.py` | 표준 라이브러리로 결정적 USER 턴 선정·제외·집계 출력을 구현. |
| A | `configs/analysis/question_risk_v1.yaml` | 탐색적 질문 위험의 손실·분모·결측·무효·claim 정책을 고정. |
| M | `configs/datasets.yaml` | kosgd2 family·출처·선정 사유·임시 primary_variant를 등록. |
| M | `configs/splits/rules.yaml` | 기존 seed/fraction을 유지하고 kosgd2 고정 선정과 대화 단위 제외를 등록. |
| A | `configs/tasks/kosgd2_actions_only.yaml` | 기존 행동 질문을 유지하는 kosgd2 파생 task 추가. |
| A | `configs/tasks/kosgd2_full.yaml` | W1 ongoing_2와 ongoing_two 진단을 담은 full task 추가. |
| M | `jeveval/NOTES.md` | 구현 결정·보수적 거부·검증 결과·파일별 변경 기록을 추가. |
| M | `jeveval/README.md` | 새 CLI 사용법과 추가 모듈 지도를 기록. |
| M | `jeveval/contract/label_vocab.py` | 어휘를 가족 대표 셋에서 공유하는 규칙을 명시. |
| M | `jeveval/data/items/kosgd.py` | 진단 ongoing_two에 catalog 순서를 주입. |
| M | `jeveval/data/pool.py` | 고정 선정 제외 증거와 대화 단위 교집합을 검사. |
| M | `jeveval/data/t0_fixture.py` | family 기반 state 추출과 가족 전체 풀 합집합 제외를 적용. |
| A | `jeveval/io/analysis.py` | 질문 위험 정책을 검증하고 manifest SHA를 읽음. |
| M | `jeveval/io/datasets.py` | family 조회·설정 간 일치 검사·대표 셋 어휘 공유를 구현. |
| A | `jeveval/io/history.py` | 역사 산출물·final·분할 증거를 읽고 오류를 고정 코드로 수집. |
| A | `jeveval/io/history_inputs.py` | 역사 Item 재구성에 필요한 동결 입력 해시를 확인. |
| A | `jeveval/io/report_inputs.py` | 명시 compare ID·주판 정보·root 안 출력 경로를 처리. |
| A | `jeveval/io/report_markdown.py` | typed 보고서를 원문 없는 Markdown으로 렌더링. |
| M | `jeveval/io/run_files.py` | 원자적 write_text를 추가. |
| M | `jeveval/io/sources/__init__.py` | family로 reader를 선택하고 원래 set_name을 전달. |
| M | `jeveval/io/sources/functionchat.py` | reader에 set_name 인자를 추가하고 SourceRow에 보존. |
| M | `jeveval/io/sources/klue_mrc.py` | reader에 set_name 인자를 추가하고 SourceRow에 보존. |
| M | `jeveval/io/sources/kmhas.py` | reader에 set_name 인자를 추가하고 SourceRow에 보존. |
| M | `jeveval/io/sources/korfin.py` | reader에 set_name 인자를 추가하고 SourceRow에 보존. |
| M | `jeveval/io/sources/kosgd.py` | set_name 보존과 고정 선정 제외 목록 읽기를 추가. |
| M | `jeveval/io/sources/kote.py` | votes 설정과 함께 set_name을 받도록 통일. |
| M | `jeveval/io/t0_sources.py` | kosgd2를 등록하고 가족 전체 분할 풀을 합쳐 제외. |
| M | `jeveval/run/cli.py` | report와 question-risk 명령·옵션을 등록. |
| M | `jeveval/run/cmd_compare.py` | 파일에서 읽은 family를 순수 위험 계산에 전달. |
| A | `jeveval/run/cmd_question_risk.py` | 완료 run 또는 검증된 역사 run의 탐색적 질문 위험을 기록. |
| A | `jeveval/run/cmd_report.py` | 역사 검증·분해·비교·Markdown 쓰기를 조립. |
| M | `jeveval/run/cmd_score.py` | 파일에서 읽은 family를 모집단·위험 계산에 전달. |
| A | `jeveval/run/history_check.py` | identity·seal·출처·ID 집합으로 역사 상태 세 가지를 판정. |
| A | `jeveval/run/history_stage.py` | 동결 입력과 요청 해시를 확인해 역사 Item/final 단계를 복원. |
| A | `jeveval/run/history_statistics.py` | 역사 집계 구조·개수·threshold 연결을 순수 검사. |
| M | `jeveval/run/item_summary.py` | 중복 BUILDERS를 없애고 stage_inputs의 family 디스패치를 공유. |
| M | `jeveval/run/layout.py` | 보고서 기본 경로 report_path를 추가. |
| M | `jeveval/run/make_splits.py` | 파생 셋을 허용하고 exclude 증거를 풀 검사에 전달. |
| M | `jeveval/run/stage_inputs.py` | set 경로·ID를 유지하면서 family로 Item builder를 선택. |
| A | `jeveval/score/kosgd_decompose.py` | 4분할·배타적 오류 유형·3×3 그리드·중복 일치를 계산. |
| M | `jeveval/score/labels.py` | 기존 칸 규칙을 유지하고 검증된 완전 ID 집합으로 ongoing_two를 계산. |
| M | `jeveval/score/population.py` | 호출자가 전달한 family에 따라 KoSGD 묶음 통계를 생성. |
| A | `jeveval/score/question_outcomes.py` | FinalRecord와 Item을 질문·묶음 단위 관측으로 변환. |
| A | `jeveval/score/question_risk.py` | 기존 threshold/CP 핵심으로 질문별 탐색적 위험 셀을 계산. |
| A | `jeveval/score/report_extras.py` | 명시 비교와 질문 위험을 안전한 공개 통계로 투영. |
| A | `jeveval/score/report_tables.py` | 검증 상태에 따라 공개 주 지표·질문·공통 오류 자료를 구성. |
| M | `jeveval/score/risk.py` | 기존 판정을 cell_status로 분리하고 family 전달 경로를 추가. |
| M | `jeveval/score/risk_mix.py` | family를 기준으로 by_service 등 세부 분포를 생성. |
| M | `jeveval/types/__init__.py` | 새 QuestionOutcome 자료형을 공개. |
| A | `jeveval/types/history.py` | 역사 읽기·검사 결과를 frozen dataclass로 정의. |
| M | `jeveval/types/outcomes.py` | 질문별 존재·정답·확신·유효성을 담는 frozen 자료형 추가. |
| A | `jeveval/types/report.py` | 보고서·질문·위험·분해·비교의 frozen dataclass를 정의. |
| M | `jeveval/types/t0_io.py` | T0Sources에 family 대응을 추가. |
| A | `tests/audits/test_kosgd2_selection.py` | 선정 결정성·제외·집계·원문 미출력을 검사. |
| M | `tests/data/items/test_kmhas.py` | 기존 task 전체 검사 기대 개수를 7에서 9로 확장. |
| M | `tests/data/test_pool.py` | 제외 증거 누락·같은 대화의 다른 턴 선정 거부를 검사. |
| M | `tests/data/test_t0_fixture.py` | family state와 가족 합집합 풀 제외를 검사. |
| A | `tests/fixtures/phase_a_preserved.sha256` | 기존 KoSGD task/split 및 lists의 불변 SHA 앵커를 저장. |
| A | `tests/fixtures/test_phase_a_preserved.py` | 기존 파일의 SHA가 앵커와 같은지 검사. |
| M | `tests/io/sources/test_init.py` | 모든 reader의 set_name 전달 계약을 검사. |
| M | `tests/io/sources/test_kosgd.py` | 별칭 set_name 보존과 제외 목록 읽기를 검사. |
| A | `tests/io/test_analysis.py` | 정책 내용·SHA·변조 거부를 검사. |
| M | `tests/io/test_datasets.py` | family 기본값·설정 불일치·어휘 공유를 검사. |
| A | `tests/io/test_history.py` | 역사 파일 읽기·증거 불명·부분 final·손상 읽기를 검사. |
| A | `tests/io/test_history_inputs.py` | 역사 재구성 입력 해시 검사를 확인. |
| A | `tests/io/test_report_inputs.py` | compare 정확 경로·주판·출력 경계 거부를 검사. |
| A | `tests/io/test_report_markdown.py` | typed Markdown의 상태·수치·공개 필드 렌더링을 검사. |
| M | `tests/io/test_run_files.py` | write_text의 원자적 저장을 검사. |
| M | `tests/io/test_t0_sources.py` | kosgd2 등록과 같은 가족 전체 풀 제외를 검사. |
| M | `tests/run/cli_support.py` | 합성 Harness의 셋 하드코딩을 family 기준으로 정리. |
| A | `tests/run/history_support.py` | 완료 합성 run과 정책을 만드는 공용 시험 도우미 추가. |
| A | `tests/run/test_cli_analysis.py` | 두 새 CLI의 인자·거부·출력 계약을 검사. |
| A | `tests/run/test_cmd_question_risk.py` | 현재/역사 CLI·manifest·KLUE 요청 위험 동치를 검사. |
| A | `tests/run/test_cmd_report.py` | 2모델 보고·손상·미완·compare·canary·입력 불변을 검사. |
| A | `tests/run/test_family_pipeline.py` | 별칭의 생성·채점·파생·요약 통합 경로를 검사. |
| A | `tests/run/test_history_check.py` | identity·seal·threshold·final·replay/derived 손상 주입을 검사. |
| A | `tests/run/test_history_stage.py` | 역사 Item 복원·요청 바이트 검증·파생 거부를 검사. |
| A | `tests/run/test_history_statistics.py` | 역사 집계 개수·비율·threshold 연결 손상을 검사. |
| M | `tests/run/test_layout.py` | 보고서 기본 경로를 검사. |
| M | `tests/run/test_make_splits.py` | kosgd2 분할 생성과 대화 교집합 거부를 검사. |
| A | `tests/score/test_kosgd_decompose.py` | 오류 유형·그리드·순서 교환·부분 MISSING 거부를 검사. |
| M | `tests/score/test_labels.py` | 규칙 개수를 확장하고 ongoing_two의 정상·거부 사례를 검사. |
| A | `tests/score/test_question_outcomes.py` | 묶음·가변 질문·결측·전체 요청 무효 상속을 검사. |
| A | `tests/score/test_question_risk.py` | 손계산·동률·미수락·희소 수락·1질문 위험 동치를 검사. |
| A | `tests/score/test_report_extras.py` | 비교와 질문 위험의 공개 투영·잘못된 연결 거부를 검사. |
| A | `tests/score/test_report_tables.py` | 상태별 수치 제한·희소 라벨·공통 오류 집합을 검사. |
| M | `tests/score/test_risk.py` | 분리된 순수 상태 판정과 기존 위험 계산의 일치를 검사. |
| A | `tests/types/test_history.py` | 역사 자료형의 불변성과 기본 계약을 검사. |
| M | `tests/types/test_outcomes.py` | QuestionOutcome 직렬화 계약을 검사. |
| A | `tests/types/test_report.py` | 보고서 자료형의 불변성과 기본 계약을 검사. |

최종 작업 트리 상태(임시 시험 디렉터리 제거 후):

```text
$ git status --short | grep -v __pycache__
 M JEV_TEST_PLAN.md
 M P1_CONTRACT.md
 M README.md
 M audits/README.md
 M configs/datasets.yaml
 M configs/splits/rules.yaml
 M jeveval/NOTES.md
 M jeveval/README.md
 M jeveval/contract/label_vocab.py
 M jeveval/data/items/kosgd.py
 M jeveval/data/pool.py
 M jeveval/data/t0_fixture.py
 M jeveval/io/datasets.py
 M jeveval/io/run_files.py
 M jeveval/io/sources/__init__.py
 M jeveval/io/sources/functionchat.py
 M jeveval/io/sources/klue_mrc.py
 M jeveval/io/sources/kmhas.py
 M jeveval/io/sources/korfin.py
 M jeveval/io/sources/kosgd.py
 M jeveval/io/sources/kote.py
 M jeveval/io/t0_sources.py
 M jeveval/run/cli.py
 M jeveval/run/cmd_compare.py
 M jeveval/run/cmd_score.py
 M jeveval/run/item_summary.py
 M jeveval/run/layout.py
 M jeveval/run/make_splits.py
 M jeveval/run/stage_inputs.py
 M jeveval/score/labels.py
 M jeveval/score/population.py
 M jeveval/score/risk.py
 M jeveval/score/risk_mix.py
 M jeveval/types/__init__.py
 M jeveval/types/outcomes.py
 M jeveval/types/t0_io.py
 M tests/data/items/test_kmhas.py
 M tests/data/test_pool.py
 M tests/data/test_t0_fixture.py
 M tests/io/sources/test_init.py
 M tests/io/sources/test_kosgd.py
 M tests/io/test_datasets.py
 M tests/io/test_run_files.py
 M tests/io/test_t0_sources.py
 M tests/run/cli_support.py
 M tests/run/test_layout.py
 M tests/run/test_make_splits.py
 M tests/score/test_labels.py
 M tests/score/test_risk.py
 M tests/types/test_outcomes.py
?? audits/kosgd2_selection/
?? configs/analysis/
?? configs/tasks/kosgd2_actions_only.yaml
?? configs/tasks/kosgd2_full.yaml
?? jeveval/io/analysis.py
?? jeveval/io/history.py
?? jeveval/io/history_inputs.py
?? jeveval/io/report_inputs.py
?? jeveval/io/report_markdown.py
?? jeveval/run/cmd_question_risk.py
?? jeveval/run/cmd_report.py
?? jeveval/run/history_check.py
?? jeveval/run/history_stage.py
?? jeveval/run/history_statistics.py
?? jeveval/score/kosgd_decompose.py
?? jeveval/score/question_outcomes.py
?? jeveval/score/question_risk.py
?? jeveval/score/report_extras.py
?? jeveval/score/report_tables.py
?? jeveval/types/history.py
?? jeveval/types/report.py
?? tests/audits/test_kosgd2_selection.py
?? tests/fixtures/phase_a_preserved.sha256
?? tests/fixtures/test_phase_a_preserved.py
?? tests/io/test_analysis.py
?? tests/io/test_history.py
?? tests/io/test_history_inputs.py
?? tests/io/test_report_inputs.py
?? tests/io/test_report_markdown.py
?? tests/run/history_support.py
?? tests/run/test_cli_analysis.py
?? tests/run/test_cmd_question_risk.py
?? tests/run/test_cmd_report.py
?? tests/run/test_family_pipeline.py
?? tests/run/test_history_check.py
?? tests/run/test_history_stage.py
?? tests/run/test_history_statistics.py
?? tests/score/test_kosgd_decompose.py
?? tests/score/test_question_outcomes.py
?? tests/score/test_question_risk.py
?? tests/score/test_report_extras.py
?? tests/score/test_report_tables.py
?? tests/types/test_history.py
?? tests/types/test_report.py
```

SPEC_AMBIGUOUS (Phase A 종료):

- 역사 summary에는 run_id가 없고 비주판은 summary 자체가 없다. 존재하면 model/benchmark와 선택적 run_id를 검사하며 기존 스키마를 바꾸지 않는다.
- 역사 파생 판의 원본 full Item/요청 복원 절차가 명세에 없다. 역사 집계 읽기는 허용하지만 해당 question-risk --history는 거부한다.
- W1은 서로 다른 서비스를 말하지만 ongoing_two는 완전 서비스/의도 ID가 2개인지 센다. 같은 서비스의 두 의도 여부는 Phase B 독립 감사에서 확인하고 발견 시 중단해야 한다.
- 가족 풀 합집합 때문에 T0 풀 밖 후보가 사라질 수 있고 기존 T0 노출 대화가 새 풀에 들어갈 수 있다. 표본이나 제외 규칙을 자동 변경하지 않았다.
- 실데이터 C2~C5와 파일럿/감사는 실행하지 않았으므로 수치 재현·표본 가용성·실제 요청 길이는 확인하지 못했다.
