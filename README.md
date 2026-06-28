# model_test

한국어 LLM / 멀티모달 모델의 **재현 가능한 비교 평가 프레임워크**.
공개 벤치마크 + 자체 트랙을 통합해 모델별 결과를 `results/<safe_model>/<timestamp>/...` 트리로 일관되게 누적한다.

이 리포는 **추론 모드별 두 개의 평가 파이프라인**을 담는다:

| 파이프라인 | 폴더 | 용도 |
|---|---|---|
| **non-thinking** (기준) | [`foundation_model_test_non_thinking/`](foundation_model_test_non_thinking/) | 추론 비활성(greedy) 통일 평가 — 원본 |
| **thinking** (신규) | [`foundation_model_test_thinking/`](foundation_model_test_thinking/) | **추론(thinking) 모델 전용 평가** |

> 처음 `model_test` 는 non-thinking 평가 코드였고, 이후 **thinking 파이프라인이 추가**되면서
> 두 파이프라인을 하위 폴더로 나란히 두는 구조로 정리했다(기존 커밋 히스토리 보존).

---

## 1. 두 파이프라인 — 무엇이 다른가

두 파이프라인은 **같은 벤치마크·트랙·결과 구조**를 공유하되, 추론 모델의 동작 차이에 맞춰 평가 방식이 다르다.

| 항목 | non-thinking | thinking |
|---|---|---|
| 추론 모드 | OFF (서버 `enable_thinking=false`) | **ON** (`enable_thinking=true`, Qwen 계열 `--reasoning-parser qwen3` 권장) |
| sampling | greedy (temp 0.0) | **모델 권장값** (temp 0.6 / top_p 0.95 / top_k 20 + 고정 seed), 모델 yaml `sampling:` → `THINK_*` env |
| 생성 상한 / timeout | 작게 (max_tokens 512, timeout 60) | **크게** (추론 트레이스 수용; `THINK_MAX_TOKENS` 8192, `THINK_TIMEOUT` 600) |
| 응답 파싱 | content 그대로 | **추론 분리** — `reasoning_content` 또는 `<think>...</think>` strip 후 **최종 답만** 채점 |
| 객관식/단답 프롬프트 | "바로 답하세요" | "추론 후 마지막 줄에 `정답: X`" + 마커 마지막 매치 추출 |
| harness(KMMLU) | logprob multiple-choice | **생성기반 CoT** (`local-chat-completions` + 커스텀 task + 답 추출 filter) |
| KRETA | `direct`(1토큰) 가능 | `direct` 비호환 → `default`(추론 후 `Answer: X`) + 패치가 `<think>` strip |
| agent(tool-call) | content 파싱 | 추론 strip 후 tool-call 파싱(추론 속 JSON 오인 방지) |

thinking 파이프라인의 설계 전반·환경변수·트랙별 변경점은 **[`foundation_model_test_thinking/THINKING.md`](foundation_model_test_thinking/THINKING.md)** 참고.

---

## 2. 공통: 무엇을 평가하나

(상세는 각 폴더 README 참고 — [non-thinking](foundation_model_test_non_thinking/README.md) · [thinking](foundation_model_test_thinking/README.md))

- **평가 클래스 (4종)**: `llm`(대형 텍스트) · `slm`(소형 텍스트) · `vlm`(대형 멀티모달) · `vsm`(소형 멀티모달, 메인 트랙)
- **평가 트랙 (4종)**:
  - **harness** — 한국어 지식/추론 (KMMLU 45 sub-task, `lm-evaluation-harness`)
  - **nlu** — 짧은 NLU smoke test (도메인 프롬프트 YAML)
  - **agent** — tool calling / multi-step (Ko-AgentBench L1~L7)
  - **multimodal** — OCR·문서/표/차트·장면텍스트·자유서술 VQA (KRETA, KOFFVQA, K-DTCBench, K-MMBench, MTVQA-KR, KO-VLM-Benchmark + 자체 B-3/B-4)
- **런타임**: gpustack + vLLM (OpenAI-compatible), BF16/FP16, DGX Spark(GB10) 운영 노트 포함
- **결과 누적**: `results/<safe_model>/<timestamp>/{language,vision}/<track>/...` (git 추적)

---

## 3. 리포 구조

```
model_test/                              # 리포 루트
├── foundation_model_test_non_thinking/  # non-thinking 평가 (원본)
│   ├── shared/{harness,nlu,agent,multimodal}/   # 공통 코드 (단일 소스)
│   │   └── multimodal/benches/          # paths/client/cli/metadata/textnorm + 벤치 (common.py = facade)
│   ├── configs/models/*.yaml            # 모델별 설정
│   ├── {llm,slm,vlm,vsm}/               # 클래스별 (shared symlink + 메타)
│   ├── results/                         # 평가 결과 (git 추적)
│   ├── README.md / CONVENTIONS.md
│   └── run_full_eval.sh / sync.sh / ...
│
└── foundation_model_test_thinking/      # thinking 평가 (신규)
    ├── shared/multimodal/benches/       # + reasoning.py / answer_parse.py (추론 분리·답 추출)
    ├── shared/harness/tasks_thinking/   # KMMLU 생성기반 CoT task (템플릿 + 45 과목)
    ├── configs/models/*.yaml            # + sampling: 블록
    ├── THINKING.md                      # thinking 설계 노트
    └── ... (non-thinking 과 동일 레이아웃)
```

> **외부 벤치마크 repo(`data/`)·`.venv`·`.env`** 는 `.gitignore` 로 제외된다(각 `install.sh` 가 SHA 핀으로 재현). `results/` 는 추적된다.

---

## 4. 빠른 시작

각 파이프라인 폴더 안에서 독립적으로 실행한다.

```bash
cd foundation_model_test_thinking          # 또는 foundation_model_test_non_thinking

# 1) 환경
python -m venv .venv && source .venv/bin/activate

# 2) 트랙별 외부 repo 설치 (SHA 핀 clone + 패치)
bash vsm/harness/install.sh
bash vsm/multimodal/install.sh             # KRETA(+thinking 패치)/KOFFVQA/...
bash vsm/agent/install.sh                  # Ko-AgentBench

# 3) .env 작성 (gpustack 토큰)
cp .env.example .env && $EDITOR .env        # OPENAI_API_KEY=...

# 4) 한 모델 전체 트랙 평가 (yaml 의 sampling → thinking 은 THINK_* 자동 export)
./run_full_eval.sh <model_config_name>      # 예: Qwen_Qwen3.5_35B_A3B
```

> **thinking 서버 등록(중요)**: Qwen 계열은 `--default-chat-template-kwargs '{"enable_thinking": true}'`
> `--reasoning-parser qwen3` `--max-model-len 24576+` 로 띄울 것 (각 모델 yaml `backend_reference` 참고).

---

## 5. 문서

- [`foundation_model_test_non_thinking/README.md`](foundation_model_test_non_thinking/README.md) — 프레임워크 상세(데이터셋·사용법·운영 노트)
- [`foundation_model_test_thinking/README.md`](foundation_model_test_thinking/README.md) — thinking 변형 사용법
- [`foundation_model_test_thinking/THINKING.md`](foundation_model_test_thinking/THINKING.md) — **thinking 설계·변경점·환경변수**
- 각 폴더 `CONVENTIONS.md` — 코드 작성 규칙(트랙 self-containment, 추론 처리 규칙 등)

---

## 6. License

MIT — 각 폴더 `LICENSE` 참고. 외부 벤치마크/도구는 각자 원 라이선스를 따른다
(KRETA, KOFFVQA, Ko-AgentBench, lm-evaluation-harness, KO-VLM-Benchmark, K-DTCBench, K-MMBench, MTVQA).
