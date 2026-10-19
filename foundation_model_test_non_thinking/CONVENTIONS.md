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

1. `shared/<track>/run_<bench>.sh` 작성 (다른 run_*.sh 패턴 따름)
2. `shared/<track>/run_all.sh` (multimodal 의 경우) 에 호출 추가
3. bench 본체 (`.py`) 가 결과 JSON 을 표준 schema 로 출력
4. 필요 시 `configs/models/*.yaml` 의 `tracks` 에 추가

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
- 기대값은 현재 코드를 실행해 얻은 값을 리터럴로 적는다(특성화). 시각·지연 같은 변동 키는 비교에서 빼고 그 목록을 시험 상단에 적는다.
- 분해로 뽑은 순수 함수마다 단위 시험 1~2개(`test_<모듈>_units.py`, 2차는 `_units2.py`). 기존 시험은 분해 때 수정하지 않는다 — 수정이 필요하면 분해가 동작을 바꾼 것이다.
- 러너를 검증용으로 직접 실행할 때는 `MODEL_TEST_BASE=<임시폴더>` + 더미 `--endpoint` + 저장소 밖 복사본 + `env -i`. 기본값만으로도 실제 엔드포인트에 요청하고 `results/` 에 쓴다.

## 14. 출력 불변 리팩터의 검증 방식

채점·보고·파생 코드를 바꿀 때는 저장된 실제 결과로 전후를 비교한다(읽기만, 쓰기는 임시 폴더): agent 세션 `score_run.py --check`, taubench·functionchat 세션을 `--results-dir` 임시 복사본으로 재채점한 `summary.json` 해시, 보고서 5개의 산출 해시, multimodal `derive_source` 전 세션 해시 — HEAD 복사본(`git archive`)과 작업 트리를 **연속으로** 돌려 전부 같아야 한다(레인이 돌아 `results/` 가 늘면 harness 보고서 해시만 바뀐다). 한 번에 처리하는 양은 Codex 1회 구현 + A 검증으로 끝나는 크기(함수 10~20개)로 나눈다.
