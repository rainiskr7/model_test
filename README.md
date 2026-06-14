# model_test

한국어 LLM / 멀티모달 모델의 **재현 가능한 비교 평가 프레임워크**.
공개 벤치마크 + 자체 트랙을 통합해 모델별 결과를 `results/<safe_model>/<timestamp>/...` 트리로 일관되게 누적한다.

---

## 1. 무엇을 테스트하는가

평가 대상을 모델 크기/특성에 따라 **4개 클래스**로 분리해서 자급자족 구조로 운영한다.

| 클래스 | 대상 | 주요 트랙 |
|---|---|---|
| `llm/` | 대형 텍스트 전용 LLM (예: Qwen3-235B) | harness · nlu · agent |
| `slm/` | 소형 텍스트 LLM | harness · nlu · agent |
| `vlm/` | 대형 멀티모달 (vision+text) | harness · nlu · agent · multimodal |
| `vsm/` | **소형 멀티모달 6종 (메인 트랙)** | harness · nlu · agent · multimodal |

각 클래스 폴더는 동일한 트랙 레이아웃을 가진다.

### 1.1 평가 트랙

| 트랙 | 측정 항목 | 사용 도구 |
|---|---|---|
| **harness** | 한국어 일반 지식 / 추론 (KMMLU 45 sub-task) | EleutherAI `lm-evaluation-harness` |
| **nlu** | 짧은 NLU smoke test (도메인 프롬프트 YAML) | 자체 runner (`nlu-gpustack.py`) |
| **agent** | Tool calling · multi-step agent (L1~L7) | `Ko-AgentBench` (HF-KREW) |
| **multimodal** | OCR · 문서/표/차트 이해 · 실세계 장면 텍스트 · 자유 서술형 VQA | KRETA, KOFFVQA, K-DTCBench, K-MMBench, MTVQA(KR), KO-VLM-Benchmark + 자체 B-3/B-4 |

### 1.2 평가 대상 (vsm 메인 트랙, 6종)

| 모델 | 타입 | 활성 파라미터 | 멀티모달 | 컨텍스트 |
|---|---|---|---|---|
| Qwen3.5-35B-A3B | MoE | 3B | ✅ | 262K |
| Qwen3.6-35B-A3B | MoE | 3B | ✅ | 262K |
| Qwen3.5-27B | Dense | 27B | ✅ | 262K |
| Qwen3.6-27B | Dense | 27B | ✅ | 262K |
| Gemma-4-31B-it | Dense | 31B | ✅ | 256K |
| Gemma-4-26B-A4B | MoE | 4B | ✅ | 256K |

**비교 축:** ① 사이즈 효과 (27B vs 31B vs 35B) ② 아키텍처 (Dense vs MoE) ③ 세대 (Qwen3.5 vs Qwen3.6).

### 1.3 런타임 환경 (확정)

- 양자화: **BF16/FP16 (비양자화)**
- 추론 엔진: **gpustack 2.1.3 + vLLM 0.20.0**
- 컨텍스트 캡: **200K**
- 추론 모드: **non-thinking** 통일 (Qwen3.6 thinking은 부록 트랙)
- API: GPUStack OpenAI-compatible

자세한 평가 설계는 [`vsm/마스터평가계획.md`](vsm/마스터평가계획.md) · [`vsm/비전평가계획.md`](vsm/비전평가계획.md) 참고.

---

## 2. 사용 데이터셋

### 2.1 텍스트 / 추론 (harness)

| 벤치마크 | 내용 | 라이선스/출처 |
|---|---|---|
| **KMMLU** (45 sub-task) | 한국어 전공 지식 multiple-choice (회계·법·의학·공학 등 45개 도메인) | HAERAE-HUB / HuggingFace |
| (옵션) KOBEST · CLICK · HAERAE · KBL | 한국어 이해 · 문화 · 법률 | harness 내 task 정의, 주석 처리 상태 |

### 2.2 에이전트 (agent)

| 벤치마크 | 내용 | 출처 |
|---|---|---|
| **Ko-AgentBench** | 한국어 tool calling / multi-step agent, L1~L7 난이도 | [Hugging-Face-KREW/Ko-AgentBench](https://github.com/Hugging-Face-KREW/Ko-AgentBench) |
| 사내 MCP 회귀셋 | 실제 함수 스키마 기반 50~100개 (별도 보강) | 내부 |

### 2.3 멀티모달 / Image-to-Text (multimodal)

| 벤치마크 | 내용 | 출처 |
|---|---|---|
| **KRETA** | 한국어 텍스트-리치 VQA, 15영역 × 26유형 | [tabtoyou/KRETA](https://github.com/tabtoyou/KRETA) |
| **KOFFVQA** | 한국어 free-form VQA, **Rubric judge** 채점 (275 샘플) | [maum-ai/KOFFVQA](https://github.com/maum-ai/KOFFVQA) |
| **K-DTCBench** | 한국어 문서/표/차트 multiple-choice VQA (240 샘플) | NCSOFT (HF: `NCSOFT/K-DTCBench`) |
| **K-MMBench** | 한국어 멀티모달 dev set (4,330 샘플) | NCSOFT |
| **MTVQA (KR)** | 9개 언어 중 한국어 서브셋, 실세계 장면 텍스트 free-form VQA | ByteDance |
| **KO-VLM-Benchmark** | KO-VQA / KO-VDC / KO-OCRAG | [Marker-Inc-Korea/KO-VLM-Benchmark](https://github.com/Marker-Inc-Korea/KO-VLM-Benchmark) (현재 stub) |
| **B-3 Structured Output** (자체) | 이미지 → JSON 변환 정확도 (포맷 준수) | `vsm/multimodal/data/structured_output/` |
| **B-4 Latency Profile** (자체) | 조건별(text-only / 256px / 1024px / multi-image) TTFT · tokens/sec | 자체 측정 스크립트 |

### 2.4 데이터셋 카테고리 매핑 (Plan #2 가중치)

| 카테고리 | 가중치 | 대표 벤치마크 |
|---|---|---|
| 문서 OCR · 구조 이해 | **50%** | KRETA, K-DTCBench, K-MMBench (문서/표/차트 카테고리) |
| 실세계 장면 텍스트 | **30%** | MTVQA(KR), KO-VLM-Benchmark |
| 자유 서술형 VQA | **20%** | KOFFVQA |

---

## 3. 사용법

### 3.1 사전 요구사항

- Linux + Python 3.10+
- GPU + **GPUStack** (OpenAI-compatible 엔드포인트) 또는 vLLM 서버
- 평가 대상 모델은 GPUStack에 등록되어 있어야 함
- 디스크: 외부 벤치마크 clone 합계 ~250MB, 결과 누적 분 별도

### 3.2 설치

```bash
# 1) 가상환경
python -m venv .venv
source .venv/bin/activate

# 2) 클래스/트랙별 install.sh 실행 (필요한 트랙만)
bash vsm/harness/install.sh        # lm-evaluation-harness clone + 설치
bash vsm/multimodal/install.sh     # KRETA + KOFFVQA + KO-VLM-Benchmark clone
bash vsm/agent/install.sh          # Ko-AgentBench clone + 설치
```

외부 repo들은 모두 `data/`에 중앙 집중으로 clone된다. 재현성을 위해 commit SHA를 env로 핀할 수 있다 (`KRETA_SHA`, `KOFFVQA_SHA`, `KOVLM_SHA`).

> **KRETA 로컬 패치:** `vsm/multimodal/install.sh`는 KRETA를 clone·SHA 핀한 뒤 `shared/multimodal/patches/kreta_infer_gpt.patch`를 `git apply`한다. 패치 내용 — ① `OPENAI_BASE_URL` / `KRETA_WORKERS`(기본 2) env 지원, ② 요청 timeout 60→300초(저대역폭 GB10의 큰 비전 prefill 수용), ③ OpenAI 클라이언트를 sample마다 생성하던 것을 단일 인스턴스 재사용으로 변경(커넥션 누수·점진적 열화 수정). 패치 적용이 실패하면 install은 즉시 중단된다(조용히 upstream 기본동작으로 남는 사고 방지).

### 3.3 단일 트랙 실행

```bash
# harness (KMMLU 45 sub-task, chat mode + 5-shot)
bash vsm/harness/run_harness.sh \
  qwen3-vl-8b-instruct \
  Qwen/Qwen3-VL-8B-Instruct \
  http://127.0.0.1:18090/v1/chat/completions

# NLU smoke test (prompt/*.yaml 전부)
bash vsm/nlu/run_nlu.sh \
  --model qwen3-vl-8b-instruct \
  --endpoint http://127.0.0.1:18090/v1/chat/completions

# Ko-AgentBench (L1~L7 전부; 일부만 하려면 "L1,L2" 식)
bash vsm/agent/run_gpustack_custom.sh \
  qwen3-vl-8b-instruct \
  http://127.0.0.1:18090/v1/chat/completions

# 멀티모달 일괄 (KRETA + KOFFVQA + K-DTCBench + K-MMBench + MTVQA + B-3 + B-4)
bash vsm/multimodal/run_all.sh \
  qwen3-vl-8b-instruct \
  http://127.0.0.1:18090/v1
```

개별 벤치마크 실행은 `vsm/multimodal/run_<benchmark>.sh` 직접 호출.

KRETA가 중단된 경우 `vsm/multimodal/run_kreta_resume.sh`로 이어서 진행한다. `run_kreta.sh`와 달리 `./output`의 jsonl을 삭제하지 않아, 이미 처리된 `id`는 skip하고 남은 샘플만 추론한다(idempotent resume). 추론 완료 후 evaluate · 결과 복사 · 키 검증까지 자동 수행.

### 3.4 전체 평가 (한 모델 4트랙 일괄)

`run_full_eval.sh`가 vsm 클래스의 4개 트랙(harness → nlu → agent → multimodal)을 순차 실행한다.

```bash
# 모델/엔드포인트는 스크립트 상단 변수 수정 후 실행
bash run_full_eval.sh
```

특징:

- 부모 프로세스 종료 시 자식 프로세스까지 일괄 cleanup (process group kill)
- 트랙별 로그: `logs/<EVAL_TIMESTAMP>/<track>.log`
- 한 트랙 실패해도 나머지는 계속 진행 (실패 트랙은 마지막에 정리해서 출력)

### 3.5 평가 세션 관리

여러 트랙이 **같은 timestamp 폴더**에 결과를 누적하도록 세션 파일(`.eval_session`)로 timestamp를 공유한다.

```bash
./start_eval_session.sh              # 현재 시각으로 세션 시작
./start_eval_session.sh 20260504_153000  # 명시 timestamp

# ... 평가 트랙들 실행 ...

./end_eval_session.sh                # 세션 종료 (다음 평가는 새 폴더)
```

우선순위: `EVAL_TIMESTAMP` env > `.eval_session` 파일 > 현재 시각.

### 3.6 결과 위치

```
results/<safe_model_name>/<timestamp>/
├── language/
│   ├── harness/<task>_<isotime>.json     # lm_eval 출력
│   ├── nlu/<prompt>.json
│   └── agent/...
└── vision/
    ├── multimodal/
    │   ├── kreta/
    │   ├── koffvqa/
    │   ├── k_dtcbench/
    │   ├── k_mmbench/
    │   └── mtvqa_kr/
    └── customB/
        ├── b3_structured_output/
        └── b4_latency_profile/
```

`safe_model_name`은 모델 이름의 `/`, `-`, `:`을 `_`로 치환한 값 (예: `Qwen/Qwen3.5-35B-A3B` → `Qwen_Qwen3.5_35B_A3B`).

### 3.7 두 머신 간 동기화

DGX Spark 2대 (192.168.0.7 ↔ .8) 사이 rsync 래퍼:

```bash
./sync.sh                # push (here → other)
./sync.sh pull           # pull (other → here)
./sync.sh push --delete  # mirror (위험: 원격에서 삭제까지)
./sync.sh --dry-run      # 시뮬레이션
```

`.venv/`, `__pycache__/`, `.eval_session` 등은 자동 제외. `data/`(외부 clone)와 `results/`는 동기화 대상.

### 3.8 운영 노트 — 대형 Dense 모델 / GB10 (DGX Spark)

GB10은 통합 메모리(LPDDR5X, 대역폭 ~273 GB/s)라 dense 대형 모델의 디코딩이 대역폭 바운드다 (예: BF16 27B ≈ 단일 스트림 ~5 tok/s). KRETA처럼 고해상도 이미지(비전 토큰 최대 ~16K)를 다루는 트랙에서 특히 느려, 다음을 권장:

- **vLLM `--max-model-len`**: KRETA 요청 최대 컨텍스트 ≈ 비전(~16K) + 텍스트 + 출력(4096) ≈ 20.5K. **24576 이상** 필요 (16384는 ~1.3% 요청이 길이 초과로 거부됨).
- **`KRETA_WORKERS`**: 메모리 압박 완화를 위해 dense 대형 모델은 **2** 권장. (`run_kreta.sh`는 기본 4로 실행하므로 `KRETA_WORKERS=2`를 명시하거나, 기본 2인 `run_kreta_resume.sh`를 사용.)
- **요청 timeout**: 300초 (install 패치 기본값). 큰 비전 prefill이 60초를 넘겨 타임아웃→오답으로 기록되는 것을 방지.
- vLLM 엔진이 장시간/메모리 압박으로 deadlock되면(`/v1/models`는 응답하나 `/v1/chat`만 hang) 모델 컨테이너 재시작으로 해소.

---

## 4. 디렉토리 구조

```
model_test/
├── llm/  slm/  vlm/  vsm/        # 4 클래스 (자급자족)
│   └── <class>/
│       ├── harness/              # lm-evaluation-harness 래퍼
│       ├── nlu/                  # NLU smoke test
│       ├── agent/                # Ko-AgentBench 래퍼 + GPUStack 어댑터
│       ├── multimodal/           # vlm/vsm 에만 존재
│       │   ├── benches/          # 개별 벤치마크 runner
│       │   ├── patches/          # 외부 repo 로컬 패치 (kreta_infer_gpt.patch)
│       │   ├── run_<bench>.sh
│       │   ├── run_kreta_resume.sh  # KRETA 중단-재개 (jsonl 보존)
│       │   ├── run_all.sh
│       │   └── install.sh
│       ├── recommended_models.md
│       └── (평가계획.md)
├── data/                          # 외부 repo 중앙 clone (.gitignore)
│   ├── KRETA/  KOFFVQA/  KO-VLM-Benchmark/
│   ├── Ko-AgentBench/
│   └── lm-evaluation-harness/
├── results/                       # 평가 결과 (git 추적 — 모델별 결과 누적)
├── logs/                          # 트랙별 실행 로그 (.gitignore)
├── run_full_eval.sh               # 한 모델 4트랙 일괄
├── start_eval_session.sh / end_eval_session.sh
├── sync.sh                        # 머신 간 rsync
├── REFACTORING_PLAN.md            # 향후 정비 계획
└── README.md
```

---

## 5. 산출물

평가 종료 후 다음을 생성하는 것이 목표:

1. **글로벌 랭킹** (Bradley-Terry, 텍스트/비전/에이전트 3개 별도)
2. **카테고리 × 모델 히트맵**
3. **용도별 추천 매트릭스** (한국어 요약 / OCR / 차트·표 / 툴 호출 / 저 VRAM 등)
4. **Gemma visual token budget 파레토 프론트** (Gemma 4는 이미지당 70/140/280/560/1120 토큰 선택 가능)
5. **3축 트렌드 분석** (사이즈 / Dense vs MoE / Qwen3.5 → 3.6 세대)

자세한 산출물 정의는 [`vsm/마스터평가계획.md`](vsm/마스터평가계획.md) 10장 참고.

---

## 6. License

MIT — `LICENSE` 파일 참고.

외부 벤치마크/도구는 각자 원 라이선스를 따른다 (KRETA, KOFFVQA, Ko-AgentBench, lm-evaluation-harness, KO-VLM-Benchmark, K-DTCBench, K-MMBench, MTVQA).
