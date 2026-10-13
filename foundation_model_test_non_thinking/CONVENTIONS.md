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
orchestration/                   # 레인 실행·감시 (run_lane.sh + lanes/<이름>.conf, lane_guard.sh)
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

## 11. 공용 모듈과 새 최상위 이름

- 공용 코드는 `shared/<주제>/` 패키지 하나로 둔다. 지금 있는 것: `jsonwrite/atomic_json.py`(원자적 JSON 쓰기, 끝 LF 있음), `resultspath/`(`results/` 모델 폴더 철자 재사용 `model_dir.py`, 채점 경로·실행 시각 `run_dir.py`). 단독 CLI 파일에서는 `sys.path.insert(0, <shared 경로>)` 뒤 `from jsonwrite.atomic_json import …` 로 가져온다(기존 규약).
- 같은 본문의 함수가 두 파일에 생기면 세 번째를 만들지 말고 공용 모듈로 올린다. 본문이 다르면(예: agent 채점기의 writer 는 끝 LF 없음·fsync, multimodal sidecar 는 sort_keys) 합치지 말고 주석으로 차이를 적는다.
- **새 최상위 모듈·패키지 이름은 sys.path 에 오르는 모든 폴더(`shared/`, 각 트랙의 `scoring/`·`runner/`, `multimodal/benches`, `agent/gpustack_custom`)와 `data/` 아래 벤치 저장소 최상위의 `.py`·디렉터리 이름과 겹치면 안 된다.** 10-13 에 `shared/common/` 이 `benches/common.py` 를 가려 시험이 깨진 적이 있다(→ `jsonwrite` 로 개명).

## 12. 함수 크기와 분해

- 함수는 **80줄 안**을 목표로 한다. 넘으면 논리 블록을 모듈 수준 함수로 뽑는다: 입력→출력이 분명한 순수 함수 우선, 부작용(파일 쓰기·환경 변수)은 시그니처에 드러내고, 한 줄 docstring. 원래 함수는 순서대로 부르는 조정자가 된다(`main` 은 40줄 안).
- 예외: 긴 dict/list 리터럴 하나를 돌려주는 조립 함수, 분기 없는 직렬 변환, 메시지 표 — 나누면 더 읽기 어려운 것은 그대로 두고 "유지: 리터럴 조립" 처럼 이유를 남긴다. 목표는 줄 수가 아니라 "한 기능만 읽고 고칠 수 있는가" 다.
- 분해는 출력(저장 파일 byte, 반환 dict 의 키 순서, stdout 문구, rc, 예외 종류)을 바꾸지 않는다. **출력 동일성을 맞추려고 `exec(compile(...))`, `sys.excepthook` 교체, `sys.argv[0]` 조작 같은 래퍼를 쓰지 않는다** — 그런 트릭이 필요해 보이면 분해하지 않고 이유를 적는다.
- 셸 스크립트 안의 python heredoc 은 `.py` 파일(함수 + `main`)로 뺀다. 오류 경로의 traceback 본문까지 같을 필요는 없다(rc·stdout·마지막 stderr 줄이 기준).
- 모듈을 import 하는 것만으로 환경(os.environ)·전역 가변 상태가 바뀌면 안 된다. 키 로딩·dotenv·누적 상태는 `main()` 이 만든 객체에 둔다(단독 CLI 의 자기 폴더 `sys.path.insert` 는 허용).

## 13. 시험

- 모든 시험은 서버·`data/`·`results/` 없이 돈다. 러너는 가짜 어댑터/`subprocess`/`requests` 로 `main()` 을 끝까지 돌리며 **보낸 요청(모델·메시지·파라미터·헤더 키)과 저장 파일(키·byte 규약)·rc** 를 고정한다(`test_*_runner_requests.py`, 공용 가짜는 `multimodal/tests/_runner_fakes.py`). 소켓 `connect` 를 막은 상태에서도 통과해야 한다.
- 기대값은 현재 코드를 실행해 얻은 값을 리터럴로 적는다(특성화). 시각·지연 같은 변동 키는 비교에서 빼고 그 목록을 시험 상단에 적는다.
- 분해로 뽑은 순수 함수마다 단위 시험 1~2개(`test_<모듈>_units.py`, 2차는 `_units2.py`). 기존 시험은 분해 때 수정하지 않는다 — 수정이 필요하면 분해가 동작을 바꾼 것이다.
- 러너를 검증용으로 직접 실행할 때는 `MODEL_TEST_BASE=<임시폴더>` + 더미 `--endpoint` + 저장소 밖 복사본 + `env -i`. 기본값만으로도 실제 엔드포인트에 요청하고 `results/` 에 쓴다.

## 14. 출력 불변 리팩터의 검증 방식

채점·보고·파생 코드를 바꿀 때는 저장된 실제 결과로 전후를 비교한다(읽기만, 쓰기는 임시 폴더): agent 세션 `score_run.py --check`, taubench·functionchat 세션을 `--results-dir` 임시 복사본으로 재채점한 `summary.json` 해시, 보고서 5개의 산출 해시, multimodal `derive_source` 전 세션 해시 — HEAD 복사본(`git archive`)과 작업 트리를 **연속으로** 돌려 전부 같아야 한다(레인이 돌아 `results/` 가 늘면 harness 보고서 해시만 바뀐다). 한 번에 처리하는 양은 Codex 1회 구현 + A 검증으로 끝나는 크기(함수 10~20개)로 나눈다.
