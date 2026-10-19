# SPEC: 판 6 7단계 — 중복 함수 통합 (2026-10-20, 판 2: X 반박 반영)

담당: A(Claude) 계획·검증·커밋, X(Codex) 반박·구현. 공통 규칙은 판 6 명세 §0 그대로(동결 파일 `shared/harness/*`·`configs/tests/*` 금지, CONVENTIONS §11~§14, 기능별 작은 파일, 운영 logs/results/data 쓰기 금지, commit/push 는 A, X 의 "통과" 는 PASS 아님, 시험은 바이트코드 허용·차단 두 환경).
N = `foundation_model_test_non_thinking/`. thinking 쪽 이식은 하지 않는다(사용자 결정: non_thinking 끝난 뒤).

**이 단계는 순수 이동이다. 저장 결과·stdout·rc·예외 종류·모듈 속성 이름이 하나도 바뀌면 안 된다.**

## 측정(A, 10-20 AST 비교 — docstring 제외 본문·인자 동일)

| 이름 | 위치 | 판정 |
|---|---|---|
| `safe_model_name` | `shared/resultspath/model_dir.py:6`(목적지), `agent/scoring/aggregate.py:781`, `functionchat/scoring/score_run.py:37`, `multimodal/benches/paths.py:16`, `nlu/nlu_gpustack.py:145`, `taubench/runner/run_taubench.py:24`, `taubench/scoring/score_run.py:38` | 7곳 동일 |
| `_safe_model_name` | `functionchat/runner/run_functionchat.py:341` | 위와 동일 본문 |
| `results_model_dir_name` | `resultspath/model_dir.py:16`(목적지), `functionchat/scoring/score_run.py:41`, `nlu/nlu_gpustack.py:159`, `taubench/runner/run_taubench.py:28` | 4곳 동일 |
| `_digest` | `agent/scoring/repro.py:24`, `functionchat/scoring/repro.py:36` | 동일(taubench `scoring/cohort.py:39` 는 **다름 — 제외**) |
| `_identity` / `_metadata_identity` | `agent/scoring/repro.py:29`, `functionchat/scoring/repro.py:41` | 동일 |
| `_load`, `_results_dir` | `functionchat/scoring/score_run.py:240,248`, `taubench/scoring/score_run.py:543,551` | 동일 |
| `_env_flag` | `agent/gpustack_custom/run_gpustack_benchmark_with_logging.py:57`, `functionchat/runner/run_functionchat.py:26` | 동일하지만 **gpustack_custom 은 외부 배치 코드(§11 예외)** — 공용 import 불가 |
| `shared/results_dir.sh` | 셸 함수 안 파이썬 heredoc(5~17행) | §12 "heredoc 은 .py 로" 대상 |

## 결정

7a. **`safe_model_name`·`results_model_dir_name`**: 6개 모듈의 로컬 정의를 지우고 `from shared.resultspath.model_dir import safe_model_name[, results_model_dir_name]` 로 바꾼다. **모듈 속성 이름은 그대로 남는다**(import 로 같은 이름이 생김) — 다른 코드·시험이 `모듈.safe_model_name` 을 쓰거나 `from 모듈 import safe_model_name` 해도 계속 동작. `run_functionchat._safe_model_name` 은 `from … import safe_model_name as _safe_model_name`.
  - AST 동일은 **자유 변수까지 같다는 뜻이 아니다**. X 는 각 로컬 정의가 참조하는 전역 이름(예: `Path`)이 목적지 모듈에서 같은 객체인지 확인하고 표로 적는다.
  - 각 모듈이 이 함수를 monkeypatch 하는 시험이 있으면, 이동 뒤에도 patch 가 실제 호출 경로에 닿는지 확인(판 5 의 교훈: 재수출만으로는 monkeypatch 가 안 닿을 수 있다). 닿지 않는 경우가 있으면 그 모듈은 옮기지 말고 이유를 적는다.
7b. **`_digest`·`_identity`**: agent·functionchat 두 `repro.py` 의 동일 쌍을 새 공용 모듈 하나로(이름은 X 제안 — `shared/` 아래, CONVENTIONS §11 의 최상위 이름 충돌 규칙 준수). 두 repro.py 는 그 모듈을 import 하고 기존 이름(`_digest`, `_identity`, `_metadata_identity`)을 유지. taubench `cohort._digest` 는 본문이 달라 그대로 두고, 다르다는 주석을 단다(§11 "본문이 다르면 합치지 말고 주석으로 차이를 적는다").
7c. **`_load`·`_results_dir`**: 두 채점기의 동일 쌍. 자유 변수(예: `PREFIX`·모듈 상수)가 같은지 먼저 확인. 같으면 `shared/resultspath/run_dir.py`(이미 `scoring_results_dir` 가 있음) 또는 X 가 제안하는 기존 공용 모듈로 옮기고, 다르면 옮기지 않고 주석.
7d. **`_env_flag`**: gpustack_custom 쪽은 §11 예외라 옮기지 않는다. 남은 하나(`run_functionchat`)는 N 안에서 유일하므로 공용화하지 않는다. 두 곳에 "gpustack_custom 은 외부 배치 코드라 공용 import 불가 — 같은 본문 유지" 주석.
7e. **`shared/results_dir.sh` heredoc → 파이썬**: `shared/resultspath/` 아래 CLI(예: `python -m shared.resultspath.cli <base> <safe_model>`)가 `results_model_dir_name` 을 써서 stdout 한 줄, 모호하면 stderr 에 **지금과 byte 같은 메시지** + rc 2. 셸 함수는 자기 위치에서 N 을 계산해 `PYTHONPATH=<N>` 을 **그 명령에만** 붙여 `python3 -B -m …` 호출. 지금 heredoc 은 `python3` 를 쓴다 — 인터프리터 선택은 그대로(`python3`).
  - `results_model_dir_name` 은 입력에 `safe_model_name` 을 다시 적용한다. 셸 호출부는 이미 safe 이름을 넘기므로, 정규화가 멱등임을 단위 시험으로 고정(`safe(safe(x)) == safe(x)`).
  - 이 helper 를 복사해 쓰는 fixture(`orchestration/tests/host_lock_fixture.py:45`, `orchestration/tests/test_run_lane_full.sh:84,143`)는 준비 코드만 고쳐 `shared/resultspath` 도 함께 둔다(기대값 무변경). `test_run_lane_full.sh:143` 의 "helper 호출 감지" 의도는 유지.
  - 호출부: `orchestration/tracks/full.sh:163-165`, `shared/agent/run_gpustack_custom.sh:76-77`. 기존 시험 `shared/agent/tests/test_results_dir.py` 가 셸 helper 계약의 앵커.

## 반박 반영 결정(판 2, 10-20 X 반박 → A 확인)
- **7a 추가**: `run_functionchat._results_model_dir_name`(345행)도 같은 알고리즘 — `from shared.resultspath.model_dir import results_model_dir_name as _results_model_dir_name`. 옮긴 `results_model_dir_name` 사본들은 지금 **자기 모듈의** `safe_model_name` 을 전역 조회하지만, 이동 뒤에는 목적지 모듈의 것을 조회한다. 그런 patch 사용처는 없음(X 확인) → 허용, 커밋 메시지에 기록. `multimodal/benches/paths.py` 는 §11 예외가 아님(X 확인) → 대상.
- **7b**: 새 모듈 `shared/reproidentity/core.py`(+`__init__.py`). 충돌 검사는 X 가 함(로컬). 공개 함수 이름은 `digest`·`metadata_identity`, 두 repro.py 는 `_digest = digest`, `_identity`/`_metadata_identity = metadata_identity` 로 기존 이름 유지.
- **7c 축소**: `_load` 만 공용으로(목적지는 X 제안, 기존 `shared/jsonwrite` 는 쓰기 전용이라 부적합하면 새 읽기 helper 를 같은 resultspath 가 아닌 적절한 곳에). **`_results_dir` 은 옮기지 않는다** — `Path(__file__).resolve().parents[3]` 이 모듈 위치에 묶여 옮기면 `MODEL_TEST_BASE` 없을 때 결과 루트가 모노레포 루트로 바뀐다. 두 곳에 이유 주석. C7.2 의 `is` 검사에서 `_results_dir` 제외, 대신 "두 채점기의 기본 루트 == N" 단위 시험 추가(`MODEL_TEST_BASE` 없이).
- **7e 취소(이번 단계)**: `shared/results_dir.sh` 는 **동결된** `shared/harness/run_harness.sh:50` 이 source 하고, 동결 시험 `shared/harness/tests/runner_checks.py:294` 는 helper 파일만 복사한다. 또 `shared/agent/tests/test_results_dir.py:78-86` 의 가짜 python3 는 stdin 의 heredoc 을 compile 하는 방식이다. heredoc 을 `-m` 모듈 호출로 바꾸면 동결 시험이 깨지므로 동결 규칙과 충돌한다. → heredoc 유지, 파일 머리에 "§12 예외: 동결 harness 가 이 helper 를 단독 복사해 쓴다" 주석. C7.1 의 heredoc 0 조건과 C7.4 삭제.

## 수용 조건

- **C7.1 잔여 grep**: `def safe_model_name`·`def results_model_dir_name` 운영 정의가 `shared/resultspath/model_dir.py` 한 곳(태그: 동적 정의는 못 잡음). `_digest`·`_identity` 동일 쌍 정의 1곳. `shared/results_dir.sh` 에 heredoc 0.
- **C7.2 모듈 속성 보존**: 바뀐 각 모듈에서 `safe_model_name`·`results_model_dir_name`·`_safe_model_name`·`_digest`·`_identity`·`_metadata_identity`·`_load`·`_results_dir` 이 전처럼 import 가능하고 목적지 함수와 `is` 동일(신규 단위 시험).
- **C7.3 출력 불변**: `python -B -m tools.output_baseline.baseline --out <tmp>` rc 0(216 MATCH). 러너 쪽은 기준선 밖이므로 `bash tests/run_pytests.sh -k runner_requests` 와 각 트랙 시험 전체 PASS.
- **C7.4 셸 helper byte 동일**: `results_model_dir` 의 stdout·stderr·rc 를 HEAD heredoc 판과 비교 — 결과 폴더 없음 / 같은 철자 / 대소문자만 다른 철자 / 모호(두 철자) / results 가 파일인 경우 등 X 가 경우를 표로 정하고 전부 byte 동일. `test_results_dir.py` 무수정 통과.
- **C7.5 전체**: 셸 묶음 6개 rc 0, pytest 전체(캐시 허용·차단), 레인 5개 dry-run byte 동일(full 은 helper 를 dry-run 에서 안 부르므로 실실행 fixture 시험 F 계열이 앵커).
- **C7.6 동결·운영**: `git diff --stat` 에 동결 경로 0, `gpustack_custom/` 변경은 주석뿐.

## 기록

| 조각 | 커밋 | C 결과 | 기록 |
|---|---|---|---|
| 7a~7e | (git log) | C7.1 PASS(중복 목록 운영 정의는 resultspath/model_dir·reproidentity/core·jsonread/object 각 1곳, 같은 이름 남은 것은 인자가 다른 별개 함수) · C7.2 PASS(신규 48) · C7.3 PASS(A: 기준선 216 MATCH, runner_requests 50, 트랙 시험 전체) · C7.5 PASS(A: 셸 묶음 6개 rc 0, pytest 1217 캐시 허용·차단, 레인 5개 dry-run byte 동일 — X 보고) · C7.6 PASS(동결 0, gpustack_custom 주석 1줄) | 순수 이동 −204/+27. 의도된 의존 변화: nlu 가 shared/resultspath 에 의존 → nlu 격리 시험 fixture 에 복사 2줄. 옮긴 results_model_dir_name 은 이제 목적지 모듈의 safe_model_name 을 조회(patch 사용처 없음). 7e 취소(동결 harness), _results_dir 유지(__file__) |
