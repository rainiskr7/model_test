# Conventions — model_test 코드 작성 규칙

LLM (Claude Code 등) 으로 유지보수할 때 일관성 유지를 위한 가이드.

## 1. 디렉토리 구조

```
shared/                          # 단일 소스 — 공통 코드
├── agent/, nlu/, harness/      # 4 클래스 (llm/slm/vsm/vlm) 공통
└── multimodal/                  # vsm/vlm 공통 (텍스트 전용 클래스 없음)

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

## 5. 결과 JSON 표준 (새 bench)

`shared/multimodal/benches/_schema.py` 의 Pydantic 모델 상속 또는 같은 키 구조:

```python
# accuracy 기반 bench
{
  "benchmark": "K-MMBench",
  "model": "google_gemma_4_31B_it",
  "total": 4330,
  "correct": 3812,
  "accuracy": 0.880,
  "by_category": {...}
}
```

`total`, `count`, `accuracy` 같은 표준 필드를 두면 `run_all.sh` 의 sanity check 가 자동 검증 (0건 결과 / 비정상 낮은 accuracy 탐지).

## 6. 에러 처리 정책

- **트랙 wrapper** (`run_full_eval.sh`, `run_all.sh`): 트랙 하나 실패해도 다음 진행. `|| echo "..."` 패턴.
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
