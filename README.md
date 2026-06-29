# model_test

한국어 LLM / 멀티모달 / 검색(임베딩·리랭커) 모델의 **재현 가능한 비교 평가 프레임워크**.
공개 벤치마크 + 자체 트랙을 통합해 모델별 결과를 `results/<safe_model>/<timestamp>/...` (또는 각 하니스 결과 트리)로 일관되게 누적한다.

이 리포는 **4개의 평가 하니스**를 담는다 — 기반 모델 평가(추론 모드별 2종)와 검색 모델 평가(임베딩·리랭커):

| 분류 | 하니스 | 폴더 | 용도 |
|---|---|---|---|
| **기반 모델** | non-thinking (기준) | [`foundation_model_test_non_thinking/`](foundation_model_test_non_thinking/) | 추론 비활성(greedy) 통일 평가 — 원본 |
| **기반 모델** | thinking (신규) | [`foundation_model_test_thinking/`](foundation_model_test_thinking/) | **추론(thinking) 모델 전용 평가** |
| **검색** | embedding | [`embedding_test/`](embedding_test/) | **임베딩 모델 비교 평가** (MTEB 한국어/금융) |
| **검색** | reranker | [`reranker_test/`](reranker_test/) | **리랭커 모델 비교 평가** (2-stage A/B + native) |

> 처음 `model_test` 는 non-thinking 기반 모델 평가 코드였고, 이후 **thinking 파이프라인**, 그리고
> **임베딩·리랭커 하니스**가 차례로 추가되면서 각 평가를 하위 폴더로 나란히 두는 구조로 정리했다(커밋 히스토리 보존).

---

## 1. 기반 모델 — 두 파이프라인은 무엇이 다른가

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

### 기반 모델 — 무엇을 평가하나

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

## 2. 검색 모델 — 임베딩 · 리랭커

기반 모델과 별개로, RAG 검색 품질의 두 축(임베딩 1차 검색, 리랭커 재정렬)을 독립 하니스로 평가한다.
두 하니스는 **MTEB 기반 + 데이터셋 실재성 게이트 + 재시작(이어서 실행) + GPU 불필요 단위 테스트**라는 설계를 공유한다.

### 2-1. embedding_test — 임베딩 모델 평가

- **대상 모델**: Qwen3-Embedding-8B / kanana-nano-2.1b-embedding / bge-m3-korean (메인 트랙) + bge-m3(`repr` 표현 비교 전용) (`configs/models/*.yaml`)
- **트랙**: 스모크(파이프라인 검증) → 범용 한국어 → 금융, MTEB 네이티브 번들/공식 벤치마크, `repr`(BGE-M3 dense/sparse/hybrid 표현 비교)
- **prompt 모드**: `recommended`(모델 권장) vs `controlled`(통제) 분리 평가
- **결과**: `results/scores_long.csv`(long-format) + `results/summary.md`(모델×태스크 매트릭스) + `results/cost.json`(운영 비용)
- 상세: **[`embedding_test/README.md`](embedding_test/README.md)**

### 2-2. reranker_test — 리랭커 모델 평가

- **대상 모델**: bge-reranker-v2-m3 / jina-reranker-v2 / ko-reranker / Qwen3-Reranker-0.6B(native 비호환 → `rerank`/`latency` 트랙만) (`configs/models/*.yaml`)
- **2-stage A/B**: 임베딩으로 frozen 1차 후보(top-N) 생성 → 리랭커 재채점 → `baseline` vs `reranked` 비교
  (임베딩 모델을 `--embedder` 실행 인자로 받음)
- **native vs 변환**: `MIRACLReranking`은 MTEB native reranking 경로, retrieval 데이터셋(Ko-StrategyQA / AutoRAGRetrieval / MultiLongDocRetrieval)은 2-stage 변환 경로
- **민감도/효율**: candidate top-N(20/50/100)별 품질·latency(P50/95/99·throughput·VRAM) 곡선
- **결과**: `results/rerank/*.json`(A/B + Δ) · `results/native/...` · `results/rerank_long.csv` · `results/latency.json` · `results/summary.md` + `cache/*.json`(1차 후보 동결)
- 상세: **[`reranker_test/README.md`](reranker_test/README.md)**

---

## 3. 리포 구조

```
model_test/                              # 리포 루트
├── foundation_model_test_non_thinking/  # 기반 모델 — non-thinking 평가 (원본)
│   ├── shared/{harness,nlu,agent,multimodal}/   # 공통 코드 (단일 소스)
│   │   └── multimodal/benches/          # paths/client/cli/metadata/textnorm + 벤치 (common.py = facade)
│   ├── configs/models/*.yaml            # 모델별 설정
│   ├── {llm,slm,vlm,vsm}/               # 클래스별 (shared symlink + 메타)
│   ├── results/                         # 평가 결과 (git 추적)
│   ├── README.md / CONVENTIONS.md
│   └── run_full_eval.sh / sync.sh / ...
│
├── foundation_model_test_thinking/      # 기반 모델 — thinking 평가 (신규)
│   ├── shared/multimodal/benches/       # + reasoning.py / answer_parse.py (추론 분리·답 추출)
│   ├── shared/harness/tasks_thinking/   # KMMLU 생성기반 CoT task (템플릿 + 45 과목)
│   ├── configs/models/*.yaml            # + sampling: 블록
│   ├── THINKING.md                      # thinking 설계 노트
│   └── ... (non-thinking 과 동일 레이아웃)
│
├── embedding_test/                      # 검색 — 임베딩 모델 평가
│   ├── run.py                           # CLI (env/verify/list-ko/list-benchmarks/smoke/korean/financial/task/bundle/official/repr/cost/aggregate)
│   ├── embeval/                         # config·models·datasets·mteb_runner·benchmarks·cost·aggregate
│   ├── evalcommon/                      # 공통 (mteb 호환·결과 스키마·torch 유틸)
│   ├── configs/models/*.yaml            # 모델별 설정
│   └── tests/                           # GPU 불필요 단위 테스트
│
└── reranker_test/                       # 검색 — 리랭커 모델 평가
    ├── run.py                           # CLI (env/verify/smoke/native/rerank/task/latency/aggregate)
    ├── rerankeval/                      # config·metrics·rerankers·embedders·firststage·rerank_runner·native_runner·latency
    ├── evalcommon/                      # 공통 (embedding_test 와 동일 계열)
    ├── configs/{models,embedders}/*.yaml
    └── tests/                           # GPU 불필요 단위 테스트
```

> **외부 벤치마크 repo(`data/`)·`.venv`·`.env`** 는 `.gitignore` 로 제외된다 — 기반 모델 하니스는 각 트랙 `install.sh` 가 SHA 핀으로 외부 repo 를 재현하고, 검색 하니스(embedding/reranker)는 `requirements.txt` 로 설치한다(별도 `install.sh` 없음). 기반 모델 하니스의 `results/` 는 추적된다.

---

## 4. 빠른 시작

각 하니스 폴더 안에서 독립적으로 실행한다.

### 기반 모델 (thinking / non-thinking)

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

### 임베딩 (embedding_test)

```bash
cd embedding_test
pip install -r requirements.txt            # torch 라인은 사내 CUDA 빌드에 맞춰 조정

python run.py verify                        # ① 데이터셋 실재성 게이트(가장 중요)
python run.py smoke                         # 3개 모델 파이프라인 검증
python run.py korean && python run.py financial
python run.py cost && python run.py aggregate   # results/summary.md 생성
```

### 리랭커 (reranker_test)

```bash
cd reranker_test
pip install -r requirements.txt            # transformers>=4.51.0 필수(Qwen3-Reranker)

python run.py verify                        # ① 데이터셋 실재성/native·retrieval 성격 게이트
python run.py smoke                         # native reranking 스모크
python run.py native                        # MIRACLReranking 등
python run.py rerank --embedder bge-m3-ko   # retrieval 3종 2-stage A/B
python run.py latency && python run.py aggregate
```

> **Windows(cmd/PowerShell, CP949) 주의**: 검색 하니스의 config 로더가 UTF-8 yaml 을 명시 인코딩 없이 읽으므로,
> `python run.py --help` 부터 인코딩 에러가 날 수 있다. 실행 전 `set PYTHONUTF8=1`(cmd) /
> `$env:PYTHONUTF8=1`(PowerShell) 로 UTF-8 모드를 켜 둘 것.

---

## 5. 문서

- [`foundation_model_test_non_thinking/README.md`](foundation_model_test_non_thinking/README.md) — 기반 모델 프레임워크 상세(데이터셋·사용법·운영 노트)
- [`foundation_model_test_thinking/README.md`](foundation_model_test_thinking/README.md) — thinking 변형 사용법
- [`foundation_model_test_thinking/THINKING.md`](foundation_model_test_thinking/THINKING.md) — **thinking 설계·변경점·환경변수**
- [`embedding_test/README.md`](embedding_test/README.md) — 임베딩 평가 하니스 사용법
- [`reranker_test/README.md`](reranker_test/README.md) — 리랭커 평가 하니스 사용법
- 기반 모델 각 폴더 `CONVENTIONS.md` — 코드 작성 규칙(트랙 self-containment, 추론 처리 규칙 등)

---

## 6. License

MIT — 각 폴더 `LICENSE` 참고. 외부 벤치마크/도구는 각자 원 라이선스를 따른다
(KRETA, KOFFVQA, Ko-AgentBench, lm-evaluation-harness, KO-VLM-Benchmark, K-DTCBench, K-MMBench, MTVQA, MTEB;
리랭커의 jina-reranker-v2 는 CC-BY-NC-4.0 비상업 라이선스 — 운영 후보 가부 별도 확인).
