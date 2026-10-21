# Conventions — model_test 코드 작성 규칙

LLM (Claude Code 등) 으로 유지보수할 때 일관성 유지를 위한 가이드.

## 1. 디렉토리 구조

```
shared/                          # 단일 소스 — 공통 코드. 트랙마다 run_*.sh(진입) · runner/ · scoring/ · tests/
├── harness/ nlu/ functionchat/ taubench/ agent/   # 텍스트 트랙 (4 클래스 공통)
├── multimodal/                  # vsm/vlm 공통 (benches/ · publish/)
├── publish/ serving/            # 발행 등급 · 서빙 제약
├── jsonwrite/ resultspath/      # 공용 모듈 (§11 참고)
└── results_dir.sh
orchestration/                   # 레인 실행·감시 (run_lane.sh + tracks/ + models/<모델>.conf, lane_guard.sh)
reports/                         # 트랙별 보고 스크립트

{llm,slm,vsm,vlm}/               # 클래스별 진짜 특화
├── recommended_models.md        # 모델 리스트 (각 클래스 다름)
├── agent → ../shared/agent      # symlink
├── nlu → ../shared/nlu
└── harness → ../shared/harness

{vsm,vlm}/
├── 비전평가계획.md
└── multimodal → ../shared/multimodal

configs/                         # 모델별 YAML
├── load_model_config.py
└── models/
    └── <model_name>.yaml
```

**원칙**: 공통 코드 변경 → `shared/` 한 곳만. 클래스별 메타 (모델 리스트, 평가 계획) 만 `{cls}/` 에 fork.

## 2. 평가 실행

```bash
./run_full_eval.sh <model_config_name>
# 예: ./run_full_eval.sh google_gemma_4_31B_it
```

YAML config 에서 MODEL, TOKENIZER, endpoint, tracks 자동 로드. **MODEL 변수 하드코딩 금지** — 새 모델 추가 = `configs/models/X.yaml` 한 파일.

새 config 파일명은 서빙 id를 소문자로 적은 `<org>_<model>[_<quant>].yaml`을 쓴다. 결과 폴더명은 서빙 id의 대소문자를 그대로 보존하며 기존 이름을 바꾸지 않는다. 철자 차이는 `configs/model_identity.json`으로 묶는다. 로더는 정확한 파일명을 우선하고, 대소문자 오입력은 casefold 일치 후보가 유일할 때만 받아 준다. 리눅스에서 예전에는 실패하던 대소문자 오입력이 이제 해석되는 것은 의도된 변경이다.

## 3. 인자 처리 (shell)

bash `shift N` 은 `$# < N` 일 때 fail. 안전 패턴:
```bash
if (($# >= N)); then shift N; else shift "$#"; fi
```

`shift 2 2>/dev/null || true` 같은 silent fail 패턴 금지 (인자 잔존으로 `$@` 가 다음 호출에 누수).

## 4. 결과 디렉토리 명명

```
results/<safe_model_name>/<timestamp>/<category>/<track>/<benchmark>.json
```

- `safe_model_name`: maker prefix + 풀네임 + 양자화 태그 (정규화는 `/`/`-`/`:` → `_` 만, 점/대소문자 보존)
  - 예: `Qwen/Qwen3.6-35B-A3B` → `Qwen_Qwen3.6_35B_A3B`
- `category`: `language` | `vision`
- `track`: `harness` | `nlu` | `agent` | `multimodal` | `customB`; agent 변형은 `AGENT_TRACK_NAME` 으로 `agent_<variant>` 를 선택 (`agent_passk`, 검증용 `agent_<purpose>` 등)
  - 변형 결과는 모델 비교 시 canonical `agent` 트랙과 절대 섞지 않는다.
- 최상위 `results/` 통합 (클래스 폴더 안에 결과 만들지 말 것)
- 결과 폴더명은 ASCII를 쓴다. 러너·채점기는 `results/`의 기존 철자를 `casefold()`로 재사용한다. 둘 이상이면 해당 러너는 0 이 아닌 rc 로 끝난다(harness·agent 채점·agent 러너는 2; KRETA 는 기존대로 1).

## 5. 결과 JSON 표준 (새 bench)

`shared/multimodal/benches/_schema.py` 의 Pydantic 모델 상속 또는 같은 키 구조:

```python
# accuracy 기반 bench
{
  "benchmark": "K-MMBench",
  "model": "google_gemma_4_31B_it",
  "total": 4329,
  "correct": 3812,
  "accuracy": 0.880,
  "by_category": {...}
}
```

`total`, `count`, `accuracy` 같은 표준 필드를 두면 `run_all.sh` 의 sanity check 가 자동 검증한다. 0건·schema 위반·`publish_status.publishable=false`는 실패이며, 낮은 accuracy 자체는 정상 측정일 수 있으므로 비치명 경고만 낸다.

## 6. 에러 처리 정책

- **트랙 wrapper** (`run_full_eval.sh`, `run_all.sh`): 트랙 하나가 nonzero를 반환해도 다음 트랙은 진행하되 실패 수를 누적하고 마지막에 nonzero를 반환한다. KOFFVQA의 깨끗한 `UNSCORED`는 실패가 아니지만 생성 오류는 실패다.
- **트랙 본체** (`run_kreta.sh`, `run_b4_*.sh` 등): 가능한 fail-fast. `set -e` 권장.
- **bench 코드** (.py): `except Exception: pass` 금지. 명시 예외 (`json.JSONDecodeError` 등) + 로깅.
- **bare `except:`** 금지 (KeyboardInterrupt 잡힘).

## 7. credential

- 하드코딩 금지. `.env` 파일에서 로드.
- `.env` 는 `.gitignore` 됨, `.env.example` template git 추적.
- `run_full_eval.sh` 가 `source .env` + assert (`: ${OPENAI_API_KEY:?...}`)

## 8. 외부 repo 재현성

각 `install.sh` 에 SHA 핀 default 값 박음. 다른 버전 평가 시 env var override:
```bash
KRETA_SHA=<sha> bash shared/multimodal/install.sh
```

## 9. 로깅 prefix 통일

각 트랙 메시지는 `[track-name] msg` 형식. 예:
- `[full_eval] vllm preflight: ...`
- `[multimodal/kreta] ./output stale 정리 완료`
- `[sanity] 3 건의 의심 결과:`

grep 친화 + LLM 이 로그 분류 용이.

## 10. 새 트랙/bench 추가 절차

새 트랙은 [트랙 등록과 입력 계약](orchestration/tracks/README.md)을 따른다. 아래는 기존 `multimodal` 트랙에 bench 를 추가할 때의 지도다. `M`은 `shared/multimodal/`, `S`는 `orchestration/smoke/`이며, 셸의 최상위 호출부는 함수 심볼이 없는 경우 그대로 적었다.

| 구분 | 파일·심볼 | 할 일 |
|---|---|---|
| (a) 항상 | `M/run_<bench>.sh`의 모듈 호출, `M/benches/<bench>.py`의 `main` | 실행 진입점·결과 저장 구현. 기존 wrapper 패턴과 결과 schema·발행 계약을 따른다. |
| (a) 항상 | `M/run_all.sh`의 `run_checked` 호출부·`skip_bench` 분기·`SKIP_BENCH_NAMES` | 일괄 실행에 연결하고 재개용 skip 훅과 허용 이름을 함께 추가한다(기존 B3 예외는 아래). |
| (a) 항상 | `M/publish/adapters.py`의 `ADAPTERS`, `M/publish/adapters_common.py`의 `BENCHMARK_IDS` | 결과 폴더 이름 → 어댑터 → 발행 ID 연결. `BENCHMARK_KEYS`는 ID 표에서 자동 파생한다. KRETA 예외는 아래. |
| (b) 채점 방식 | `M/publish/adapters_common.py`의 `EXPECTED_COUNTS`, `M/publish/adapters_accuracy.py`의 `summarize_records` 허용 집합 | 고정 건수·공통 정확도 집계를 쓰는 벤치만 추가. 전용 어댑터가 필요한 지표인지 먼저 판단한다. |
| (b) 채점 방식 | `M/publish/adapters_accuracy.py`의 `_score_classified_records`·`_accuracy_item_keys`·`_accuracy_protocol` | 정답 판정·문항키·split/limit 등 protocol 출처 확인. 기본 분기는 A–D 선택형·`index`를 가정하므로 이름만 허용해서는 안 된다. |
| (b) 발행·보고 | `M/publish/schema.py`의 `ACCURACY_BENCHMARK_IDS`, `M/publish/report.py`의 `collect`·`render_markdown` | 정확도 지표이면 overall fraction 검증 대상에 포함. 보고 수집은 `discover_sources`를 재사용하므로 일반 벤치마다 별도 보고 등록은 없다. |
| (b) 스모크 | `S/commands.py`의 `command`·`prerequisites`·`dependencies`, `S/artifacts.py`의 `multimodal`, `S/isolation.py`의 `copy_cache` | 스모크 대상에 넣을 때 요청·검사·의존성·오프라인 캐시를 함께 확인. 현재 `copy_cache`는 K-DTC 전용이다. |
| (c) 선택: 공식 재채점 | `M/rescore/manifest.py`의 `DATASETS`, `M/rescore/sessions.py`의 `BENCHES`·`rescore_source` | 고정 dataset manifest와 채점 함수 연결. 폴더 허용만 늘리지 말고 scorer 분기도 확인한다. |
| (c) 선택: paired 통계 | `shared/stats/selection.py`의 `BENCHMARKS`, `shared/stats/item_scores.py`의 `METRICS`·`score_items` | 발행 ID·지표명·문항/이미지 클러스터 점수 연결. |
| (c) 선택: 보고서 비교 쌍 | `M/rescore/report_inputs.py`의 `validate_pairs`, `reports/paired_pairs.yaml`의 `a`·`b`·`bench` | 지원 지표를 먼저 연결하고 비교 쌍 선언. `validate_pairs`는 `METRICS`를 참조하므로 별도 허용 집합을 만들지 않는다. |
| (d) 선택: 표시 순서 | `M/publish/report.py`의 `HEADLINE_ORDER` | 원하는 순서가 있을 때 추가. 미등록도 순서 99로 표시되며 발행 필수 등록은 아니다. |

- 모델 `configs/models/*.yaml`의 `tracks`에는 bench 이름이 아니라 `multimodal`을 넣는다. `configs/load_model_config.py`의 `SKIPPABLE_BENCHES`는 모델별 **측정 제외 정책**(현재 B4만)이지 벤치 등록부가 아니다. 재개용 skip 훅 추가만으로 늘리지 않는다([skip SPEC 반영 결정](orchestration/SPEC_skip_benches_20261020.md#반박-반영-결정판-2-10-20-x-반박--a-확인)).
- KRETA는 `M/publish/derive.py`의 `discover_sources`가 **부모 폴더 `kreta` + `.jsonl`**로 발견하고, `M/publish/adapters.py`의 `adapt_source`가 같은 조건으로 `adapt_kreta`를 선택한다. `ADAPTERS`에 없음이 정상이며 `preflight_kreta_source`의 집계 호출은 등록부가 아니다.
- B3/B4는 `ADAPTERS`·`BENCHMARK_IDS`에 있고 `EXPECTED_COUNTS`에는 없다. `M/run_all.sh`에서 B4는 `skip_bench` 훅, B3는 `B3_MANIFEST` 존재·`M/benches/b3_preflight.py`의 `main` 결과로 실행을 결정한다.
- 결과 경로는 `M/benches/paths.py`의 `get_results_dir`에서 bench 이름을 받는다(`vision/multimodal`, B3/B4는 `vision/customB`). `M/benches/session_sanity.py`의 `iter_result_files`는 `vision/` 아래를 탐색하고, `M/benches/_schema.py`의 `detect_and_validate`는 키로 판별한다. 별도 벤치명 목록을 추가하지 말고 새 결과 형식이 검증되는지 확인한다.
- 이름 검색은 필수 등록·조건부 분기·자동 파생·단순 언급을 구분한다. 이번 문서 보완에서는 이름 일관성 시험·통합 등록부를 만들지 않는다(필요성은 벤치 추가 때 판단).
- `configs/load_model_config.py`의 `validate_skip_benches` 설명·오류 안내도 위 측정 제외 정책을 따른다. 허용값·검사 로직은 그대로 유지한다.
- 후속: T 확인·이식 및 동결 `runner_checks.py`의 T 결과 읽기 경계는 별도 범위이며 이번 작업에서는 조사·수정하지 않는다.
- 후속: `jev_test` 관련 확인·변경은 별도 범위다.

## 11. 패키지 구조·import·실행

- `shared/`·`reports/`는 N(`foundation_model_test_non_thinking`) 루트 기준 정식 패키지다. `shared/harness/`와 `scoring/`은 `__init__.py` 없는 네임스페이스 하위 패키지로 import된다. 동결된 harness에는 패키지 파일도 추가하지 않는다.
- 공용 코드는 `shared/<주제>/`에 둔다: `jsonwrite/atomic_json.py`(원자적 JSON 쓰기, 끝 LF 있음), `resultspath/`(`model_dir.py`: 결과 모델 폴더 철자 재사용, `run_dir.py`: 채점 경로·실행 시각), `serving/`(서빙 제약), `publish/`(발행 등급).
- import는 **항상 절대 경로**를 쓴다: `from shared.<트랙>.<모듈> import …`, `from shared.publish.claims import …`, `from reports import report_harness_tracks`. 시험도 같다. `sys.path` 조작·try/except 이중 import·bare 형제 import는 금지한다. 운영 코드 예외는 아래 표, 동결·외부 코드 시험 예외는 §13에 한정한다.
- 같은 본문의 함수가 두 파일에 생기면 세 번째를 만들지 말고 공용 모듈로 올린다. 본문이 다르면(예: agent 채점기의 writer 는 끝 LF 없음·fsync, multimodal sidecar 는 sort_keys) 합치지 말고 주석으로 차이를 적는다.

| 운영 코드 예외 | 유지 이유 |
|---|---|
| `shared/agent/gpustack_custom/*` | Ko-AgentBench에 복사·배치되는 코드이며 외부 `bench.*` 패키지와 배치 위치의 import 계약을 따른다. |
| `shared/agent/scoring/bench_path.py` | `MODEL_TEST_BASE/data/Ko-AgentBench`의 외부 `bench` 패키지를 찾는다. |
| `shared/functionchat/runner/run_functionchat.py`의 `load_shared_adapter`와 전용 파일 로더 | 외부 `bench.*` 인터페이스 위에 배치 어댑터를 연결한다. |
| `shared/multimodal/benches/kreta_output_check.py` | upstream KRETA의 cwd에서 `evaluate`를 불러온다. |
| `shared/multimodal/benches/session_sanity.py` | 인자로 지정한 `benches_dir`의 선택적 `_schema`와 없을 때의 legacy 검사 계약을 유지한다. |
| `shared/multimodal/benches/kreta_resume_context.py`, `kreta_resume_context_check.py` | 인자로 지정한 `benches_dir`의 `metadata`를 사용하는 계약을 유지한다. |
| `shared/serving/__init__.py`의 상대 import(`from .constraints import …`) | 외부 배치된 gpustack_custom 코드가 `shared/`만 검색 경로에 올리고 `serving.constraints`를 import한다. 이때 `shared.serving`은 존재하지 않으므로 이 `__init__.py`만은 절대 import로 바꾸면 안 된다(10-14 조각 7에서 깨짐 재현). `serving/` 안의 다른 모듈도 같은 이유로 `shared.` 접두 import를 쓰지 않는다. |

트랙 셸은 아래처럼 코드 루트를 잡고 **N 파이썬을 부르는 줄에만** `PYTHONPATH`를 붙인다.

```bash
CODE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHONPATH="$CODE_ROOT${PYTHONPATH:+:$PYTHONPATH}" "$PY" -m shared.<트랙>.<모듈>
```

wrapper 전체에 `PYTHONPATH`를 export하지 않고 upstream 호출에도 붙이지 않는다. cwd 변경은 기능상 필요한 곳에만 둔다. 손으로 돌릴 때는 N에서 `python -m …`를 쓰거나, 저장소 밖에서 `PYTHONPATH="$N" python -m …`로 실행한다. 코드 루트 N과 `MODEL_TEST_BASE`(결과·데이터 루트)는 서로 다른 개념이다. 모든 보고서의 `--base`는 결과 위치만 지정하고 채점 코드는 실행 중인 저장소의 패키지를 쓴다. 모듈 이름은 Python 식별자여야 한다(`nlu-gpustack.py` → `nlu_gpustack.py`).

`sys.path`에는 N 루트와 위 예외 폴더만 올린다. **새 최상위 이름은 `shared`·`reports`·`configs`·`data/` 아래 벤치 저장소 최상위 이름·site-packages와 충돌하지 않아야 한다.** 트랙 안의 `common`·`paths`·`score_run`은 패키지로 한정되므로 트랙끼리 이름이 겹쳐도 된다.

역사: 10-13에는 `shared/common/`이 bare import의 `benches/common.py`를 가려 시험이 깨졌고, `jsonwrite`로 개명했다.

## 12. 함수 크기와 분해

- 함수는 **80줄 안**을 목표로 한다. 넘으면 논리 블록을 모듈 수준 함수로 뽑는다: 입력→출력이 분명한 순수 함수 우선, 부작용(파일 쓰기·환경 변수)은 시그니처에 드러내고, 한 줄 docstring. 원래 함수는 순서대로 부르는 조정자가 된다(`main` 은 40줄 안).
- 예외: 긴 dict/list 리터럴 하나를 돌려주는 조립 함수, 분기 없는 직렬 변환, 메시지 표 — 나누면 더 읽기 어려운 것은 그대로 두고 "유지: 리터럴 조립" 처럼 이유를 남긴다. 목표는 줄 수가 아니라 "한 기능만 읽고 고칠 수 있는가" 다.
- 분해는 출력(저장 파일 byte, 반환 dict 의 키 순서, stdout 문구, rc, 예외 종류)을 바꾸지 않는다. **출력 동일성을 맞추려고 `exec(compile(...))`, `sys.excepthook` 교체, `sys.argv[0]` 조작 같은 래퍼를 쓰지 않는다** — 그런 트릭이 필요해 보이면 분해하지 않고 이유를 적는다.
- 셸 스크립트 안의 python heredoc 은 `.py` 파일(함수 + `main`)로 뺀다. 오류 경로의 traceback 본문까지 같을 필요는 없다(rc·stdout·마지막 stderr 줄이 기준).
- 모듈을 import 하는 것만으로 환경(os.environ)·전역 가변 상태가 바뀌면 안 된다. 키 로딩·dotenv·누적 상태는 `main()` 이 만든 객체에 둔다.

| import 부작용 예외 | 유지 이유·조건 |
|---|---|
| `shared/agent/gpustack_custom/openai_compat_adapter.py`의 제약 로더 | 외부 Ko-AgentBench 배치의 제약 선택·경고 및 러너 decoding 메타데이터 import를 보존하기 위해 import 시 `MODEL_TEST_BASE/shared` 검색 경로 등록과 함수 선택을 허용한다. 부모 실행 환경에서 기준 경로를 확정하고 기존 no-op·경고·배치 import 계약을 유지한다. |

## 13. 시험

`bash tests/run_pytests.sh`로 전체 Python 시험을 실행하며, 선택 트랙 이름과 pytest 옵션을 뒤에 붙일 수 있다(셸 시험은 `bash tests/run_shell_tests.sh`로 별도 실행).

- 시험도 정식 패키지의 절대 import를 쓴다. 신선한 모듈이 필요하면 `conftest`의 fresh import fixture를 쓴다(`shared/nlu/tests/conftest.py`, `shared/multimodal/tests/conftest.py`). 대상 모듈 하나만 `sys.modules`에서 빼고 import하며, 종료 시 기존 캐시와 부모 패키지 속성을 복원한다. 형제 모듈 캐시를 함께 지우지 않는다.
- 자식 프로세스는 `PYTHONPATH=N` + `-m`으로 실행한다. 파일 로더는 외부 배치 파일(`gpustack_custom`)·upstream 코드·동결 시험에만 허용한다. 잔여 허용 목록은 다음과 같다(줄 번호는 R6 조각 7 감사 기준).
  - `shared/agent/tests/_agent_fakes.py`: 외부 배치 gpustack_custom 러너 파일 로더·검색 경로.
  - `shared/agent/tests/test_agent_scoring.py:47,53`: 배치 파일 `runner_timeout_config`·`result_observability` 로더.
  - `shared/agent/tests/test_tool_call_parser.py:30`: 배치 파일 `tool_call_parser` 로더.
  - `shared/agent/tests/test_agent_runner_requests.py:320-339`: 배치 parser·adapter 로더와 합성 `bench` 패키지 검색 경로.
  - `shared/multimodal/tests/test_kreta_output_isolation.py:264`: upstream `evaluate`를 자식 프로세스에서 로드.
  - `shared/harness/tests/*`·`configs/tests/*`: 동결 시험의 기존 파일 로더·검색 경로. 수정하거나 `__init__.py`를 추가하지 않는다.
- 운영 코드의 잔여 검색 경로·파일 로더는 §11 표의 목록만 허용한다. bare import 감사에서는 들여쓴 import와 점으로 이어진 이름도 확인한다. `gpustack_custom/*`의 외부·형제 import와 `session_sanity.py`의 `_schema`, `kreta_resume_context.py`·`kreta_resume_context_check.py`의 `metadata`, `kreta_output_check.py`의 upstream `evaluate`는 위 계약에 따른 예외다.
- 모든 시험은 서버·`data/`·`results/` 없이 돈다. 러너는 가짜 어댑터/`subprocess`/`requests` 로 `main()` 을 끝까지 돌리며 **보낸 요청(모델·메시지·파라미터·헤더 키)과 저장 파일(키·byte 규약)·rc** 를 고정한다(`test_*_runner_requests.py`, 공용 가짜는 `multimodal/tests/_runner_fakes.py`). 소켓 `connect` 를 막은 상태에서도 통과해야 한다.

위 원칙 중 **실제 `results/` 읽기 예외**는 아래 함수에 한정한다(파일 전체 허용이 아님). 서버 접근·운영 결과 쓰기는 허용하지 않는다. 실제 결과는 읽기만 하고 변조·재생성은 tmp 복사본에서만 한다. 고정 경로도 자료가 사라지거나 바뀌면 실패할 수 있으며, 전역 탐색은 Git 추적 여부로 제한되지 않아 **미추적 레인 세션도 포함**한다. 읽기 전용이라는 조건은 입력 고정·시험 안정성을 뜻하지 않는다.

아래 `test_publish_*.py`는 모두 `shared/multimodal/tests/` 아래다. 고정 경로는 각 함수·fixture에 적힌 경로를 뜻한다.

| 파일·시험 함수 | 이유·읽는 범위·알려진 취약점 |
|---|---|
| `test_publish_contamination.py` — `test_known_contaminated_kreta_sources_are_rejected` | 실측 오류 응답의 정답 오염 회귀. `fixtures/known_kreta_contamination.json`에 명시한 고정 10경로를 읽고 거부·오염 건수를 검사한다. 자료 누락·변경에 의존한다. |
| `test_publish_contamination.py` — `test_non_error_kreta_sources_survive_independent_response_regrading` | 독립 재채점 회귀. `discover_sources(REPO)`의 KRETA JSONL 전역 탐색; 알려진 clean 경로 포함 여부와 발행 가능으로 선별된 결과를 검사한다. `parser_disagreement_rows >= 1`은 고정 clean 목록에만 요구하며, 새 세션의 잘못된 발행 거부는 검출하지 못한다. |
| `test_publish_dataset_identity.py` — `test_kreta_same_items_and_mode_share_fingerprint_across_repo_commits` | 고정 KRETA 2경로의 문항 digest·protocol 일치와 repository commit 차이를 검사한다. 저장 provenance 변경에 의존한다. |
| `test_publish_dataset_identity.py` — `test_k_dtcbench_different_artifact_item_sets_have_different_digests` | 고정 K-DTC 2경로의 240건/5건 문항집합·digest 차이를 검사한다. 자료 건수·내용 변경에 의존한다. |
| `test_publish_dataset_identity.py` — `test_mtvqa_dataset_identity_uses_all_row_and_qa_pairs` | 고정 MTVQA 경로의 `(row_idx, qa_idx)` 전체 문항 identity 회귀. 558문항·250개 id 등 저장 자료의 구성을 고정한다. |
| `test_publish_dataset_identity.py` — `test_clean_kreta_default_modes_use_final_answer_markers_not_body_letters` | KRETA 최종 답 파서 회귀. `results/*/*/vision/multimodal/kreta/*_default.jsonl` 전역 glob 뒤 basename 2개만 선택한다. 같은 이름의 새 세션에도 과거 기대값을 적용하며, 일치 파일이 없어도 루프가 비어 통과한다. |
| `test_publish_runner_guards.py` — `test_sidecar_artifact_paths_match_git_index_casing` | 실측 sidecar 경로의 Git 철자 회귀. `results/**/_derived/*.json` 전역 탐색 후 추적 경로와 대조한다. sidecar 읽기 자체는 추적 파일로 제한되지 않으며 깨진 JSON·검사 0건이면 실패한다. |
| `shared/agent/tests/test_agent_scoring.py` — `test_seeded_field_recall_uses_seed_in_moe_artifact_or_skip` | 고정 `p0verify_20260816/.../agent_p0verify/L6.json`의 seed/refetch 실측 회귀. 파일이 없으면 print 후 return 하므로 pytest에서는 skip이 아니라 **통과**로 끝난다. |
| `shared/agent/tests/test_agent_scoring.py` — `test_agent_tracks_report_leaves_taubench_to_its_own_layer` | 보고서 트랙 분리 회귀. `report_agent_tracks.collect(TREE_ROOT)`가 `results/*/*/language/*/summary.json`을 전역 탐색해 FunctionChat summary를 읽는다. 수집 결과가 0건이면 실패하며 고정 corpus 검사가 아니다. |
| `shared/harness/tests/runner_checks.py` — `harness_suite`의 C2 real fixture·C4 existing top-level JSON inventory | 동결 셸 시험 드라이버의 실측 구조 검증. `h.lib`가 있으면 C2는 N·T 각 `results/*/*/language/harness/*.json` 중 정렬 첫 파일, C4는 대상 저장소의 해당 glob 전체를 읽는다(미추적 포함). 디렉터리 부재는 INCONCLUSIVE, 존재하지만 비거나 자료가 깨지면 실패 가능. 검사 산출물은 `HARNESS_TEST_WORK`로 지정한 임시 폴더 아래에 둔다; 기본값은 상위 `.codex_work/harness_stop_guard`다. |

`shared/multimodal/tests/test_publish_derive.py`의 예외는 **12개 함수**다. 아래 첫 11개는 `_copy_clean_source`가 고정 `results/qwen_qwen3.5_35b_a3b_fp8/20260711_003523/vision/multimodal/k_dtcbench`를 `_derived` 제외하고 tmp에 복사한 뒤 검사한다. 모두 원본 자료 부재·변경에 의존하지만, 검사 중 쓰기·삭제는 tmp 복사본에만 한다. 이 동작 시험 전부가 합성 fixture로 대체 불가능하다는 뜻은 아니다.

| 시험 함수 | 이유·읽는 범위 |
|---|---|
| `test_write_only_adds_derived_and_preserves_original_hashes` | 고정 K-DTC → tmp; 파생 파일만 추가하고 원본 해시 보존. |
| `test_dry_run_creates_nothing` | 고정 K-DTC → tmp; dry-run 무쓰기. |
| `test_derive_all_preserves_native_status_and_completed_at` | 고정 K-DTC → tmp; NATIVE 상태·완료 시각 보존. |
| `test_derive_refreshes_native_model_identity_without_downgrade` | 고정 K-DTC → tmp; 모델 identity 갱신과 NATIVE 유지. |
| `test_force_overwrites_native_with_legacy_and_reports_loss` | 고정 K-DTC → tmp; 강제 덮어쓰기와 provenance 손실 경고. |
| `test_native_write_can_promote_legacy_or_rejected` | 고정 K-DTC → tmp; LEGACY/REJECTED에서 NATIVE 승격(매개변수 2사례, 함수는 1개). |
| `test_cli_skips_native_by_default_and_force_warns_before_overwrite` | 고정 K-DTC → tmp; CLI 기본 보호·강제 덮어쓰기 경고. |
| `test_tampered_native_artifact_is_not_collected_or_skipped` | 고정 K-DTC → tmp; 변조한 원본의 무결성 거부. |
| `test_native_with_missing_source_artifact_is_not_collected` | 고정 K-DTC → tmp; 원본 파일 삭제 시 수집 거부. |
| `test_concurrent_passive_derive_cannot_overwrite_native` | 고정 K-DTC → tmp; 동시 파생의 NATIVE 덮어쓰기 방지. |
| `test_strict_collection_is_scoped_to_requested_partial_session` | 고정 K-DTC → tmp; 지정 세션만 strict 검사. |
| `test_stale_and_damaged_native_are_not_the_same_condition` | 같은 고정 세션의 `k_mmbench`를 직접 읽어 낡은 지문과 artifact 손상을 구별. 추적 자료를 쓰는 회귀이며 디렉터리 부재·내용 변경 시 실패 가능; 파일 쓰기 없음. |

`results/` 리터럴만 검사하는 가드 시험은 만들지 않는다. tmp 합성 경로는 오탐하고 `collect(TREE_ROOT)` 같은 간접 읽기는 놓친다. 위 목록도 함수별 현재 동작의 기록이며 파일 안의 새 읽기까지 허용하지 않는다.

후속: 탐색 범위 고정·fixture 전환은 별도 작업.

- 기대값은 현재 코드를 실행해 얻은 값을 리터럴로 적는다(특성화). 시각·지연 같은 변동 키는 비교에서 빼고 그 목록을 시험 상단에 적는다.
- 분해로 뽑은 순수 함수마다 단위 시험 1~2개(`test_<모듈>_units.py`, 2차는 `_units2.py`). 기존 시험은 분해 때 수정하지 않는다 — 수정이 필요하면 분해가 동작을 바꾼 것이다.
- 러너를 검증용으로 직접 실행할 때는 `MODEL_TEST_BASE=<임시폴더>` + 더미 `--endpoint` + 저장소 밖 복사본 + `env -i`. 기본값만으로도 실제 엔드포인트에 요청하고 `results/` 에 쓴다.

## 14. 출력 불변 리팩터의 검증 방식

채점·보고·파생 코드를 바꿀 때는 저장된 실제 결과로 전후를 비교한다(읽기만, 쓰기는 임시 폴더): agent 세션 `score_run.py --check`, taubench·functionchat 세션을 `--results-dir` 임시 복사본으로 재채점한 `summary.json` 해시, 보고서 5개의 산출 해시, multimodal `derive_source` 전 세션 해시 — HEAD 복사본(`git archive`)과 작업 트리를 **연속으로** 돌려 전부 같아야 한다(레인이 돌아 `results/` 가 늘면 harness 보고서 해시만 바뀐다). 한 번에 처리하는 양은 Codex 1회 구현 + A 검증으로 끝나는 크기(함수 10~20개)로 나눈다.
