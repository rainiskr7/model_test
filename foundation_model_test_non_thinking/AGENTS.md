# N 작업 안내

작업 범위는 이 디렉터리 `foundation_model_test_non_thinking/`(N)이다. 형제 T(`../foundation_model_test_thinking/`)와 `../jev_test/`는 별개이며 수정·이식하지 않는다. 버그 수정 경로가 T에도 있으면 보고에 **T 확인 필요**를 적는다. 근거: [입구 SPEC:4,19](orchestration/SPEC_vibe_entry_docs_20261020.md#L4).

## 수정 전 확인

- `shared/harness/`·`configs/tests/`는 동결이다. 파일·패키지 표식도 추가하지 않는다. 시험에서 운영 `results/`·`data/`·`logs/`에 쓰지 않는다. 근거: [CONVENTIONS.md:145](CONVENTIONS.md#L145), [CONVENTIONS.md:196](CONVENTIONS.md#L196), [입구 SPEC:7](orchestration/SPEC_vibe_entry_docs_20261020.md#L7).
- 공통 코드는 `shared/`에서 수정한다. `llm/`·`slm/`·`vlm/`·`vsm/`의 **공통 트랙 디렉터리**가 링크이며, 클래스별 추천·평가계획은 실파일이다. 근거: [CONVENTIONS.md:17,33](CONVENTIONS.md#L17).
- `orchestration/lanes/`의 진입 링크를 실파일로 바꾸거나 진입 파일 자체를 resolve하지 않는다. 호출 basename이 트랙을 정한다. 근거: [run_lane.sh:2,8](orchestration/run_lane.sh#L2).
- 수정 전 [CONVENTIONS §11~14](CONVENTIONS.md#11-패키지-구조import실행)의 해당 절을 읽는다. 외부 배치 `shared/agent/gpustack_custom/`, `shared/serving/` import 계약은 §11 예외를 따른다([CONVENTIONS.md:152,158](CONVENTIONS.md#L152)).
- import 부작용 예외는 [CONVENTIONS.md:183](CONVENTIONS.md#L183), 동결 harness가 단독 복사하는 셸 helper의 heredoc 유지 예외는 [shared/results_dir.sh:2](shared/results_dir.sh#L2)를 따른다.

## 진입점과 검증

평가 명령·재개·실패 정책은 [README 실행 진입점](README.md#실행-진입점)을 먼저 본다. 아래 명령은 N에서 실행하며, 현재 작업의 실행 금지 지시가 우선한다.

| 명령 | 범위·근거 |
|---|---|
| `bash tests/run_pytests.sh --list` | 정적 트랙 목록만 출력. pytest 실행 없음([선택기:8](tests/run_pytests.sh#L8)). |
| `bash tests/run_pytests.sh [track] [pytest options...]` | Python 단위·격리 시험. orchestration 선택/전체 실행에는 fixture lane·guard 실행도 포함([pytest.ini:2](pytest.ini#L2), [test_registry_acceptance.py:26,38](orchestration/tests/test_registry_acceptance.py#L26)). |
| `bash tests/run_shell_tests.sh` | 셸·격리 프로세스 시험 묶음. guard 시험은 소유 PID에 실제 STOP/CONT를 보낸다. 실행 금지 중에는 호출하지 않는다([셸 선택기:6](tests/run_shell_tests.sh#L6), [adapter.py:37](orchestration/tests/lane_guard_check/adapter.py#L37)). |
| `.venv/bin/python -B -m tools.output_baseline.baseline --out <tmp.json>` | 저장된 실제 results/data를 읽는 출력 기준선 도구. HEAD와 작업 트리를 비교하고 임시 산출물을 쓴다. 요청 시험을 대체하지 않는다([baseline README:3,16,52](tools/output_baseline/README.md#L3)). |
| `bash orchestration/smoke/run_smoke.sh <model_conf> [track…]` | **실서버** 최소 요청. 임시 BASE 사용; harness·tau는 preflight이며 정식 벤치 완주가 아니다([smoke README:23,39,51](orchestration/smoke/README.md#L23)). |

## 문서 지도

- 현행 규칙·사용법: [CONVENTIONS](CONVENTIONS.md), [README](README.md), [레인](orchestration/README.md), [full 레인](orchestration/README_full.md), [트랙 훅 계약](orchestration/tracks/README.md), [멀티모달 발행 계약](MULTIMODAL_PUBLISH_CONTRACT.md).
- [MULTIMODAL_REPRO_PLAN.md](MULTIMODAL_REPRO_PLAN.md)는 현행 정책과 과거 구현·측정 기록이 섞여 있다. 현재 CLI의 `--strict`는 `--run`이 필수([reports/report_multimodal_tracks.py:25](reports/report_multimodal_tracks.py#L25)).
- 역사 기록: [REFACTORING_PLAN.md](REFACTORING_PLAN.md), `orchestration/SPEC_*.md` 중 완료·종료 문서. 각 제목 아래 상태와 근거 커밋을 확인한다. 채택 작업이 완료된 [입구 SPEC](orchestration/SPEC_vibe_entry_docs_20261020.md)은 반영 결정 절과 완료 기록을 따른다.
- 생성 문서 **손수정 금지**: [MULTIMODAL_TRACK_RESULTS.md:3](MULTIMODAL_TRACK_RESULTS.md#L3), [TAUBENCH_TRACK_RESULTS.md:3](TAUBENCH_TRACK_RESULTS.md#L3). 각각 보고 코드가 sidecar·summary에서 생성한다.

## 검색

`.ignore`의 `/results/`로 기본 검색에서 결과를 제외한다. 결과 조사에는 `rg --no-ignore-dot '패턴' results/`를 쓴다. `--no-ignore-dot`은 `.ignore`·`.rgignore` 규칙만 해제하고 `.gitignore`·숨김 파일 제외는 유지한다(`rg --help`, `--no-ignore-dot`).
`data/`·`logs/`는 Git 체크아웃의 기본 검색에서 이미 제외되므로 `.ignore`에 중복하지 않는다. 결과 내부 `llm_debug/`·`artifacts/` 제외도 남는다([.gitignore:14,20,42,47](.gitignore#L14)). 명시적으로 경로를 주는 검색과 기본 트리 검색은 구별한다.

## N/T 관계: 계약과 관측

- **동일성 계약**: `shared/harness/tests/runner_checks.py`만 T 사본과 `cmp` 동일을 요구한다([v6 SPEC:11](orchestration/SPEC_refactor_v6_steps1-6_20261019.md#L11)). 다른 동결 파일까지 N/T 동일성 의무로 확대하지 않는다.
- 확인 명령: `cmp shared/harness/tests/runner_checks.py ../foundation_model_test_thinking/shared/harness/tests/runner_checks.py`([레인 README:128](orchestration/README.md#L128)).
- **현재 관측(2026-10-20)**: 양쪽 추적 파일의 디렉터리 집합 및 실제 존재를 대조했다. 결과 데이터·캐시를 제외한 N 전용 최대 하위 트리는 아래와 같다. 이는 이식 대상 목록이 아니다.
  - `orchestration/`, `reports/`, `tools/`(따라서 `tools/output_baseline/` 포함), `configs/serving_profiles/`.
  - `shared/harness/scoring/`, `shared/nlu/scoring/`, `shared/nlu/tests/`, `shared/multimodal/publish/`, `shared/multimodal/tests/`.
  - `shared/jsonread/`, `shared/jsonwrite/`, `shared/publish/`, `shared/reproidentity/`, `shared/resultspath/`, `shared/serving/`.
- 부재에는 파일·행이 없으므로 재확인은 양쪽 `git ls-files`와 디렉터리 존재 비교로 한다. 의도된 thinking 차이는 [T/THINKING.md:7,27,54](../foundation_model_test_thinking/THINKING.md#L7)를 읽는다. 최신 차이 전체가 이 문서 하나에 기록됐다고 가정하지 않는다.
