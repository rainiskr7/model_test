# SPEC: 판 6 9단계 — 시험 없는 모듈에 시험 + 큰 운영 파일 기능 단위 분해 (2026-10-20, 판 2: X 반박 반영)

> 상태: 부분 구현 후 종료 — 9-0·9-1a/b/c·9-2a/b 완료(`17aec7b`, `0989e2f`, `a5c5010`, `e4c235c`, `d59d60b`, `d8c95c0`); 9-3~9-6·10단계는 하지 않기로 결정, gpustack 분해 보류(아래 종료 결정).

담당: A 계획·검증·커밋, X 반박·구현. 공통 규칙은 판 6 §0 그대로. CONVENTIONS §12(함수 80줄·main 40줄, 순수 함수 우선, 분해는 출력 불변, `exec(compile())`·`sys.excepthook`·`sys.argv[0]` 트릭 금지, 예외는 "유지: 리터럴 조립" 처럼 이유), §13(분해로 뽑은 순수 함수마다 `test_<모듈>_units.py`, **기존 시험은 분해 때 수정하지 않는다** — 수정이 필요하면 분해가 동작을 바꾼 것), §14(조각은 Codex 1회 구현 + A 검증 크기 = 함수 10~20개).

**목표는 줄 수가 아니라 "한 기능만 읽고 고칠 수 있는가".** 파일 수를 늘리는 것 자체는 성과가 아니다(판 7 평가: 너무 잘게 쪼개 7개 파일을 오가야 했던 스모크).

## 측정(A, 10-20)

| 파일 | 줄 | 함수 | 비고 |
|---|---:|---:|---|
| `shared/multimodal/publish/adapters.py` | 984 | 36 | 벤치별 어댑터 + 공통 — 이미 `adapters_protocol` 일부 분리·재수출(판 6 평가: 기존 시험이 재수출 이름 호출) |
| `shared/agent/gpustack_custom/run_gpustack_benchmark_with_logging.py` | 978 | 31 | **외부 배치 코드**(Ko-AgentBench 로 복사, 복사 목록 `shared/agent/run_gpustack_custom.sh`) |
| `shared/agent/scoring/aggregate.py` | 935 | 31 | 시험이 모듈 의존성 monkeypatch(`test_aggregate_units.py:24-26`) |
| `shared/taubench/scoring/score_run.py` | 839 | 24 | |
| `shared/multimodal/publish/report.py` | 805 | 32 | |
| `shared/taubench/runner/run_taubench.py` | 787 | 28 | `_build_manifest` 104줄(리터럴 조립 성격) |
| `shared/agent/scoring/validate_rules.py`·`functionchat/runner/run_functionchat.py`·`reports/report_agent_tracks.py` | 567~609 | | 이번 범위 밖(필요 시 다음 판) |

- main 40줄 초과 9개: `taubench/runner/tau2_cli_shim.py`(75), `functionchat/judge/analyze_pilot.py`(71), `reports/report_agent_tracks.py`(68), `functionchat/judge/judge_pilot.py`(62 — 8단계 뒤 다시 잼), `functionchat/scoring/score_run.py`(59), `agent/scoring/score_run.py`(52), `reports/report_taubench_tracks.py`(51), `taubench/scoring/score_run.py`(47), `multimodal/benches/session_sanity.py`(41).
- 시험 참조 0 모듈 6개: `agent/scoring/bench_path.py`, `functionchat/judge/analyze_pilot.py`, `multimodal/benches/cli.py`, `multimodal/benches/textnorm.py`, `taubench/patch_dummy_user.py`, `taubench/runner/tau2_cli_shim.py`.

## 조각(순서대로, 조각마다 X 구현 → A 검증 → 커밋)

- **9-0 시험 먼저(운영 코드 무변경)**: 위 6개 모듈에 특성화 시험(현재 출력을 리터럴로 고정, §13). 판 6 평가의 고정 대상: bench_path(환경 누락·파일 누락 예외, 경로 중복 삽입 방지), analyze_pilot(합성 입력의 stdout·rc), cli(필수 인자·기본값·오류 rc), textnorm(전각·문장부호·숫자·잘못된 타입), patch_dummy_user(최초 패치·재실행·미지원 본문의 파일 byte·rc), tau2_cli_shim(후보·사용자 요청 제약 적용 구분과 기록). 시험은 서버·data·results 없이.
- **9-1 main 분해**: 위 main 9개를 조정자(40줄 안)로. `_build_manifest` 는 리터럴 조립이면 "유지: 리터럴 조립" 주석으로 예외, 분기가 섞여 있으면 분기만 뽑기.
- **9-2 `publish/adapters.py`**: 벤치별로(공통 helper 1 + 벤치 어댑터 모듈들). `adapters.py` 는 기존 공개 이름을 다시 내보내는 얇은 진입점으로 남긴다. **기존 시험이 `adapters` 모듈 속성을 monkeypatch 하는 경우, 그 이름이 실제 호출 경로에 남아야 한다**(판 5 교훈: 단순 재수출은 patch 가 안 닿음) — X 는 분해 전 patch 사용처 표를 먼저 만들고, 닿지 않게 되는 함수는 옮기지 않는다.
- **9-3 `agent/scoring/aggregate.py`**: 같은 원칙. `test_aggregate_units.py` 가 patch 하는 이름(`score_level`·`_score_level_with_specs`·`prepare_v3_loaded`·`build_eval_context` 등, 판 5 메모)은 실제 호출 경로에 남긴다.
- **9-4 `taubench/scoring/score_run.py`**, **9-5 `publish/report.py`**, **9-6 `taubench/runner/run_taubench.py`**: 같은 원칙, 하나씩.
- **gpustack 러너(978줄)**: 외부 배치 코드라 파일을 나누면 복사 목록(`run_gpustack_custom.sh`·`run_gpustack_passk.sh`)과 배치 import 계약(형제 import)이 바뀐다. **이번 단계에서는 분해하지 않고** CONVENTIONS §11 예외 표의 기존 행에 "크기 예외: 배치 복사 단위" 를 덧붙인다. X 가 반박에서 분해 이득이 크다고 판단하면 별도 판으로 제안.

## 반박 반영 결정(판 2, 10-20 X 반박 → A 채택)

**조각 순서(12개, 조각마다 X 구현 → A 검증 → 커밋)** — §14 크기(함수 10~20개)를 넘기지 않되, **하한을 채우려고 patch 결합부까지 옮기지 않는다**(작은 조각 허용).

| 조각 | 내용 | 앵커(출력 기준선 밖 경로) |
|---|---|---|
| 9-0 | 시험 없는 6개 모듈 특성화 시험(운영 코드 무변경). shim 은 `finally` 기록·예외 전파, analyze 는 빈 입력 예외(IndexError·부분 stdout 뒤 ZeroDivisionError)까지 현재 동작 그대로 고정 | — |
| 9-1a | main 분해: `tau2_cli_shim`·`analyze_pilot`·`judge_pilot`·`session_sanity` | 9-0 신규 시험, `FC/test_judge_identity.py`, `M/test_run_all_helpers.py:81,124` |
| 9-1b | main 분해: `agent/scoring/score_run`·`functionchat/scoring/score_run` | `AG/test_agent_scoring.py:3072~3343`(rc 0/1/3·2), `FC/test_functionchat_scoring.py:84,100` |
| 9-1c | main 분해: `reports/report_agent_tracks`·`reports/report_taubench_tracks` + **새 CLI 특성화 시험**(stdout/stderr 문구·rc — 기존 strict 시험은 mock 이라 문구 앵커 아님) | 신규 CLI 시험 |
| 9-2a | `adapters_common.py`(load_json·_fraction·_counts·_run_config·_base_result·_same_metric·`EXPECTED_COUNTS` **같은 dict 객체**) + `adapters_accuracy.py`(정답 판정·KRETA 파서 14개) | 출력 기준선(208 derive 가 최상위 33개 전부 호출) + 기존 adapters 시험 |
| 9-2b | `adapters_koffvqa.py`(5) + `adapters_customb.py`(7) + `adapters.py` 는 `ADAPTERS`·`adapt_source`·명시 재수출만 | 같음 |
| 9-3 | `aggregate_observations.py` 관측 진단 5개만(`_tasks`·`_matches_seeded_only_zero_step_signature`·`_build_swallowed_exception_diagnostics`·`_finite_number`·`_build_possible_absorbed_request_timeouts`). `score_level`·`_score_level_with_specs`·`prepare_v3_loaded`·`build_eval_context`·`result_field_coverage_*` 와 **그 호출자**(`_build_v2_summary`·`build_summary_from_loaded`·`_build_infrastructure_error_diagnostics`·L3/L5/L7 진단·`_average_metric`)는 원래 모듈에 남김. `LEVEL_SPECS`·`LEVEL_SPECS_V3` 는 같은 객체 | 출력 기준선 + `AG/test_agent_scoring.py:1294`(인프라 오류 재채점), `test_aggregate_units*.py` |
| 9-4a | `taubench/scoring/domain_score.py` 도메인 채점 12개(후보 실패 판정과 분모 계산은 함께) | 출력 기준선 + `TA/test_taubench_scoring.py:387~421`(`_failure_actor` 미호출 경로) |
| 9-4b | `summary_policy.py` 요약·검증 10개 + `score_run.main` 분해(`parse_args` 를 try 밖으로 빼지 않음) + 신규 CLI 시험(--dry-run·잘못된 CLI·읽기 실패) | 출력 기준선 + 신규 CLI 시험 |
| 9-5 | `report_evidence.py` 비교·재현성 14개(+공용 표시 함수). 표·섹션 렌더링은 `report.py` 에 유지 | 출력 기준선(보고서는 live results 를 읽음) + `M/test_publish_select_report.py:427,438,515`(`strict_failed`) |
| 9-6 | `taubench/runner/task_split.py` task split 8개만. 실행 생명주기·manifest·마스킹·저장은 유지(`_unsupported_sampling_params`·`datetime`·`_package_version`·`write_json_atomic` 이름 교체 patch, `__file__` 기반 경로). `_build_manifest` 는 "유지: 리터럴 조립" | **출력 기준선이 러너를 실행하지 않음** → `TA/test_run_taubench_units.py:90,193`, `test_taubench_runner_storage.py:20` 필수, 신규 `is_programmatic_basis` 시험 |
| gpustack | 분해 보류. CONVENTIONS §11 예외 행에 "크기 예외 사유: 복사 목록 두 곳(`run_gpustack_custom.sh:42-53`·`run_gpustack_passk.sh:31-41`)·형제 import·원본 AST 시험(`AG/test_agent_scoring.py:3596,3608,3672`)을 함께 바꿔야 함 — 영구 예외 아님, 별도 판" | — |

**원칙 보강**
- 이동하는 함수가 기존 시험에서 `모듈.이름` 으로 **교체(patch·대입)** 되는 이름을 전역 조회하면, 그 함수는 옮기지 않는다(호출자까지 남김). 단순 **읽기** 접근은 재수출로 보존. private 이름도 기존 시험이 쓰면 재수출.
- 모듈 상수 dict(`EXPECTED_COUNTS`·`LEVEL_SPECS*`)는 복사하지 말고 같은 객체를 공유.
- `import os/subprocess` 형태 유지(`from subprocess import run` 으로 바꾸면 `runner.subprocess.*` patch 가 끊김).
- 기존 시험은 이번에도 무수정. 단 "시험 수정 필요 ⇒ 반드시 동작 변경" 은 과한 일반화임을 인정 — 시험이 구현 위치를 계약으로 삼는 경우도 있으므로 **그 위치 계약까지 보존**한다.

**수용 조건 정정**
- C9.1: 출력 기준선은 보고서가 live results 를 읽고, tau/functionchat 은 summary.json·rc 만 비교(stdout·stderr 미비교)함을 전제로, 조각별 위 표의 앵커 시험을 함께 요구.
- C9.4: 기존 시험 파일을 고쳐 실패값을 넣는 대신 **신규 patch 도달 시험**(spy 호출 횟수·인자, sentinel 효과)으로 확인.
- C9.5: 셸 묶음은 운영 레인이 돌지 않을 때만(guard 실프로세스 시험).

## 수용 조건(조각마다)

- **C9.1 출력 불변**: `python -B -m tools.output_baseline.baseline --out <tmp>` rc 0(216 MATCH) — 9-2·9-3·9-4·9-5 는 이 도구가 직접 덮는다. 러너 조각(9-6, 9-1 의 러너 main)은 `-k runner_requests` 와 해당 트랙 요청·저장 앵커 시험.
- **C9.2 기존 시험 무수정**: 분해 조각에서 기존 시험 파일 diff 0(신규 `_units` 시험만 추가). 9-0 은 신규 시험만.
- **C9.3 크기·응집**: 바뀐 운영 파일의 함수 80줄 안·main 40줄 안(예외는 주석으로 이유). 새 모듈마다 짝 시험 파일. "한 기능 = 한 파일" 을 X 가 표로(모듈 → 담당 기능 → 짝 시험).
- **C9.4 patch 도달**: 분해 전 monkeypatch 사용처 표의 모든 항목이 분해 뒤에도 실제 호출 경로에 닿는다(각 patch 를 실패 유도 값으로 바꿨을 때 시험이 실패하는지로 확인 — 음성 검증).
- **C9.5 전체**: 셸 묶음 6개 rc 0, pytest 캐시 허용·차단, 동결 0, 운영 logs/results/data 쓰기 0.

## 기록

| 조각 | 커밋 | C 결과 | 기록 |
|---|---|---|---|
| 9-0 | | | |
| 9-1a | | | |
| 9-1b | | | |
| 9-1c | | | |
| 9-2a | | | |
| 9-2b | | | |
| 9-3 | | | |
| 9-4a | | | |
| 9-4b | | | |
| 9-5 | | | |
| 9-6 | | | |
| gpustack 예외 | | | |

## 종료(10-20, 사용자 결정)
9-0·9-1a·9-1b·9-1c·9-2a·9-2b 까지 하고 **9-3·9-4·9-5·9-6·10단계는 하지 않는다**. 이유: 함수는 이미 전부 80줄 안이라 남은 분해는 파일만 늘리고(9-3 은 935줄 중 153줄, 9-6 은 787줄 중 109줄만 떼어 큰 파일이 그대로 남음) 바이브코딩 이득이 작다 — 해당 파일을 실제로 고칠 일이 생길 때 그 부분만 나눈다. gpustack 러너도 보류(예외 사유는 위 표).
결과: 발행 어댑터 984줄 → 진입점 adapters.py 70 + common 127 + accuracy 445 + koffvqa 182 + customb 243(+기존 protocol 123), main 40줄 초과 9개 → 0, 시험 없던 모듈 6개 → 0.

