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

외부 repo들은 모두 `data/`에 중앙 집중으로 clone된다. 재현성을 위해 commit SHA를 env로 핀할 수 있다 (`KRETA_SHA`, `KOFFVQA_SHA`, `KOVLM_SHA`, `KO_AGENTBENCH_SHA`).

> **KRETA 로컬 패치:** `vsm/multimodal/install.sh`는 KRETA를 clone·SHA 핀한 뒤 `shared/multimodal/patches/kreta_infer_gpt.patch`를 `git apply`한다. 패치 내용 — ① `OPENAI_BASE_URL` / `KRETA_WORKERS`(기본 2) / `KRETA_MAX_TOKENS`(기본 4096) / `KRETA_TIMEOUT`(기본 600초) env 지원, ② OpenAI 클라이언트를 sample마다 생성하던 것을 단일 인스턴스 재사용으로 변경(커넥션 누수·점진적 열화 수정), ③ streaming append(jsonl)+fsync 와 id 기반 idempotent resume(에러/타임아웃 행은 드롭 후 재시도), ④ 완주 invariant(기록 고유 id 수 != 2577 시 fail). 생성 상한·타임아웃 튜닝은 §3.8 참고. 패치 적용이 실패하면 install은 즉시 중단된다(조용히 upstream 기본동작으로 남는 사고 방지).

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

KRETA 러너는 3번째 인자로 프롬프트 모드(`SETTING`)를 받는다 — `direct`(글자만 답, 빠름·DGX Spark 권장) / `default`(추론 후 답). 모드별 생성 상한은 자동 설정되며 자세한 내용은 아래 §3.8 운영 노트 참고. 예: `bash vsm/multimodal/run_kreta_resume.sh <model> direct <url>`.

KOFFVQA도 idempotent resume를 지원한다(`koffvqa_run.py`). 같은 `EVAL_TIMESTAMP`로 재실행하면 `out_dir/results.json`의 **유효 응답**(error 없음 + 비어있지 않은 prediction)은 `index` 기준으로 재사용하고, **에러·타임아웃·누락 항목만 다시 호출**한 뒤 results.json·xlsx·summary를 머지해 재생성한다. 따라서 일부 샘플이 타임아웃으로 실패하면 **같은 명령을 재실행하는 것만으로 복구**된다 — 별도 retry 스크립트 불필요. `run_koffvqa.sh`는 `KOFFVQA_TIMEOUT` env(기본 600초, kreta `KRETA_TIMEOUT`과 일관)를 받으며, 게이트웨이 200초 컷을 피하려면 직접 vLLM 포트를 `<url>`로 준다. 예: `KOFFVQA_TIMEOUT=600 bash vsm/multimodal/run_koffvqa.sh <model> http://<host>:<vllm_port>/v1`. 처음부터 다시 돌리려면 `koffvqa_run.py --no-resume`.

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

#### 3.6.1 Agent 트랙 채점·검증

최신 headline은 `agent_det_v4`의 `scoring_v4.agent_score`이며 분모는 정확히 `("L1","L2","L3","L5","L6")`인 레벨 점수의 동일 가중 평균이다. 다섯 레벨이 모두 채점 가능할 때만 숫자를 기록하고 하나라도 빠지거나 채점 불가이면 `null`(`incomplete`)이다. L4가 `null`이어도 v4를 막지 않지만, L4 자체는 계속 실행·채점되어 `by_level`과 출력 matrix에 남는다. 각 레벨 점수도 그 레벨에서 적용 가능한 `in_score=true` 지표의 동일 가중 평균이다.

scorer는 매번 세 version을 함께 낸다: `agent_det_v2=("L1","L2","L3","L4","L5","L6")`, `agent_det_v3=("L1","L2","L3","L4","L5","L6")`, `agent_det_v4=("L1","L2","L3","L5","L6")`. v2와 v3 정의·블록은 동결돼 그대로 유지된다. 터미널에는 세 headline과 정확한 분모, v2/v3/v4의 전체 L1~L7 matrix가 함께 나오며 scalar headline만 단독으로 출력하지 않는다. summary의 `headline_denominators`, 세 `by_level` matrix, `l4_fixture_coverage`에도 같은 정보를 기록한다. L7은 실행하지만 기록 전용이고, `ContextRetention_det`·`ResultFieldCoverage_det` 두 결정론 지표와 L7 레벨 자체는 어느 headline에도 들어가지 않는다. 다섯 judge 지표는 현재 측정하지 않아 `judge_missing`으로 남으므로, 이 점수는 결정론적 부분집합만 나타낸다.

`metadata.success_rate`는 정확도가 아니라 **생존 신호**(`final_response` 존재 AND `steps >= 1`)다. 측정된 두 모델의 모든 레벨에서 100%였지만 결정론 점수와 무관하므로 점수로 인용하지 않는다.

현재 다음 레벨은 모델 간 깨끗한 비교 자료로 사용할 수 없다.

| 레벨 | 알려진 결함 |
|---|---|
| L2 | runner의 task 변환이 원본 `available_tools`를 누락해 정답 tool만 노출한다. 4/4 모델이 1.000으로, 선택 정확도가 자명하다. |
| L3 | 4개 완주 런에서 202 call 중 130 miss(64.4%; 모델별 52~71%)였지만 FSM/PSM/ΔSteps는 response outcome이 아니라 call shape만 읽으므로 miss가 점수 실패로 들어가지 않는다. |
| L4 | 4개 완주 런에서 78 call 중 30 miss(38.5%: presentation sibling 0, semantic mismatch 7, query absent 23)였다. Coverage/SourceEPR는 cache miss를 `success=False`로 취급해 fixture coverage와 모델 실패를 분리할 수 없으므로 v4 headline에서 제외한다. L4 점수와 miss count/rate/bucket은 matrix에서 나란히 보고한다. |
| L6 | v3에서 수정됐다. v2 L6는 방향이 뒤집힌 known-invalid 점수이므로 v2의 6레벨 평균을 순위에 쓰지 않는다. |

- **v4 고정 제외 규칙:** 다음 네 조건을 모두 만족한다고 frozen benchmark evidence로 확정된 레벨만 새 version의 headline에서 제외한다. (1) 모든 in-scope metric의 success/count가 call shape가 아니라 tool-response outcome에서 나온다. (2) pinned fixture set에서 그 outcome label 중 material share가 cache miss다. (3) level score를 miss process와 분리할 수 없다. (4) freeze 아래에서 miss를 수리할 수 없다. L4는 두 지표가 모두 성공한 distinct tool/required distinct tool이고 miss가 `success=False`이며, 측정 miss 177건 중 key-matching rule로 수리 가능한 것이 0건이어서 네 조건을 모두 만족한다. 반면 L3는 call shape만 읽어 (1)에 실패하고, L5는 측정 miss rate 2~12%에서 (2)와 (4)에 실패하고, L6 v3는 response payload가 아니라 refetch 발생 여부를 읽는다. 이 규칙은 `V4_HEADLINE_LEVELS` 상수의 문서화된 근거일 뿐 runtime auto-exclusion이 아니다. 채점 데이터에 따라 version 분모가 바뀌는 일은 없다.
- **cache miss는 annotate-only:** 저장 결과의 모든 실행 call을 `exact`/`presentation_sibling`/`semantic_mismatch`/`query_absent`/`signature_mismatch`/`tool_absent`/`unclassified`의 ordered partition으로 분류해 summary와 scorer 표에 표시하지만 relaxed fixture를 응답으로 주지 않는다. 결과 수·페이지·정렬은 반환 entity나 cardinality를 바꿀 수 있어 semantic이며, presentation으로 남은 것은 Aladin의 `cover`(표지 이미지 크기), `output`(XML/JSON 인코딩), `opt_result`(동일 상품의 부가 응답 필드)뿐이다. 수정된 4개 완주 런의 miss 177건은 presentation sibling 0건(0%), semantic mismatch 97건, query absent 80건이었다. 따라서 이전의 복구 가능 추정 69건(39.0%)은 0건으로 붕괴한다. 이 진단은 점수와 version을 바꾸지 않는다.
- **fixture schema drift 위험(별도):** pinned catalog에 있는 fixture 4,543개 중 828개가 현재 signature hash와 달라 도달 불가다. `StockPrice_kis`는 6개 전부 도달 불가(0/6)다. 이는 miss 분류와 별개의 fixture 유지보수 위험이다.
- **동일 가중 동결:** L2 포화를 근거로 현재 코호트에서 가중치를 역산하지 않는다. 이후 약한 모델은 여전히 L2에 실패할 수 있다. 레벨 동일 가중은 의도적으로 동결된 점수 정의이며 변경에는 version bump가 필요하다. L2의 실제 결함인 `available_tools` 누락은 별도 수정 사항이다.
- **L7 승격 보류:** 결정 당시 `ResultFieldCoverage_det`는 모델별 10 task 중 2~3개에만 적용됐다. 2/10인 모델 4개는 8/10인 모델 3개보다 강한 근거가 아니다. seed-only 분모 수정만으로 자동 승격하지 않으며, 두 L7 지표가 모델 전반의 대부분 task에 적용되고 tool-call rate도 coverage가 성공 조건부가 아닐 만큼 높을 때 재검토한다.

또한 L2는 `in_score` 지표가 1개뿐이고 L5는 20 task인 반면 L3/L4는 각 10 task이므로, `agent_score`를 표본 수나 정밀도로 가중한 평균으로 해석하면 안 된다.

기존 `L*.json`은 평가를 다시 실행하지 않고 재채점할 수 있다. `--results-dir`을 써도 vendored metric을 불러오려면 `MODEL_TEST_BASE`가 반드시 필요하다.

```bash
MODEL_TEST_BASE="$PWD" .venv/bin/python shared/agent/scoring/score_run.py \
  --results-dir results/<model>/<timestamp>/language/<agent-track>
MODEL_TEST_BASE="$PWD" .venv/bin/python shared/agent/scoring/validate_run.py \
  --results-dir results/<model>/<timestamp>/language/<agent-track>
```

validator는 scoring version·요약 구조·점수 범위, judge/L7의 기록 전용 계약, raw/summary의 native-tool 모드 일치, v2/v3의 6레벨 및 v4의 고정 5레벨 완전성·평균 불변식을 검사하고 포화/바닥·생존 신호 차이는 경고한다. v4의 level set은 정확히 `("L1","L2","L3","L5","L6")`이어야 하며 stated denominator에서 headline을 재구성한다. 채점된 레벨의 cache miss rate가 20%를 넘으면 실행 call 5개 중 1개보다 많은 도구 증거가 빠진 것으로 보고 임계값과 실측 분수를 명시한 경고를 내되 실패시키지 않는다. 종료 코드는 `0`=유효(경고 허용), `1`=검증 실패, `2`=호출·설정·입력 읽기·내부 오류다. `run_full_eval.sh`에서는 agent 트랙이 성공하면 validator가 자동 실행된다.

변형 런은 `AGENT_TRACK_NAME=<variant>`로 별도 폴더에 기록한다. 변형 결과와 canonical `agent` 트랙 결과를 한 트랙에 섞지 않는다.

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

GB10은 통합 메모리(LPDDR5X, 대역폭 ~273 GB/s)라 dense 대형 모델의 디코딩이 대역폭 바운드다 (예: BF16 27B ≈ 단일 스트림 ~5 tok/s). KRETA처럼 고해상도 이미지(비전 토큰 최대 ~16K)를 다루는 트랙에서 특히 느리다.

> **⚠️ KRETA `default` 모드는 Spark에서 비실용적.** `default` 프롬프트는 모델이 추론을 길게 쓴 뒤 마지막 줄에 답하게 한다 → 응답이 수백~3400토큰까지 나오고, 대역폭 바운드 디코딩 + 큰 비전 prefill이 겹쳐 **샘플당 100~350초, 전체 2577개에 수일**이 걸리며 일부는 timeout→오답으로 오염된다. **Spark를 시험대로 쓰는 모델 랭킹 목적이면 KRETA는 `direct` 모드로 돌릴 것.**

**KRETA 프롬프트 모드** (러너 3번째 인자 `SETTING`):

- **`direct`** (Spark 권장): "보기 글자 하나로 바로 답해" → 응답 **1토큰**. **타임아웃·절단 0, ~10배 빠름**(샘플당 비전 prefill 시간만 듦). 모든 모델에 동일 적용 시 랭킹 비교는 공정하다. 점수의 절대값은 추론 모드보다 낮을 수 있으나 상대 순위 측정엔 충분. 예: `run_kreta_resume.sh <model> direct <url>`.
- **`default`**: 추론 후 답. 점수 상한은 높을 수 있으나 Spark에선 위 사유로 비실용적 — 추론 트레이스가 필요하고 충분히 빠른 HW일 때만.

**튜닝 env / 권장값:**

- **`KRETA_MAX_TOKENS`** (생성 상한): 러너가 모드별 기본값을 자동 export — `direct`→**32**, 그 외→**4096**. env로 override 가능.
  - ⚠️ `default` 모드를 1024 등으로 낮추지 말 것: 응답의 ~13%(가장 긴 = 가장 어려운 문항)가 잘려 답이 유실되고, 손실이 난이도 쪽으로 **편향**되어 랭킹을 왜곡한다. `default`는 4096 유지, 속도가 필요하면 `direct` 사용.
- **`KRETA_TIMEOUT`** (요청 timeout, 기본 **600초**): 큰 비전 prefill/긴 생성이 timeout→오답으로 기록되는 것을 방지.
- **vLLM `--max-model-len`**: KRETA 요청 최대 컨텍스트 ≈ 비전(~16K) + 텍스트 + 출력 ≈ 20.5K. **24576 이상** 필요 (16384는 ~1.3% 요청이 길이 초과로 거부됨).
- **`KRETA_WORKERS`**: 메모리 압박 완화를 위해 dense 대형 모델은 **2** 권장 (4 이상은 모델 인스턴스 hang 사례 있음). 러너 기본 2.
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
