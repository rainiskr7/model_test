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
`io.run_files.write_derived_stage`도 gate 통과 뒤 호출한다. 출처가 일치하는 final 접두 기록은 이어 쓰고, 변경/중복/실제 attempts는 쓰기 전에 거부한다. `derived.json`을 final append 전에 기록하므로 중단 후 재개가 가능하다. 빈 단계도 final·빈 attempts·출처 파일이 생긴다.
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

