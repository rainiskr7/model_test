# model_test

한국어 LLM / 멀티모달 모델의 **재현 가능한 비교 평가 프레임워크**.
공개 벤치마크 + 자체 트랙을 통합해 모델별 결과를 `results/<safe_model>/<timestamp>/...` 트리로 일관되게 누적한다.

## 실행 진입점

아래 `N`은 코드 루트에서 `N="$(pwd -P)"`로 설정한 정규 절대경로다. 레인 진입 링크 자체는 resolve하지 않는다([orchestration/README.md:5](orchestration/README.md#L5)). config 일괄 실행의 인자는 모델 YAML 이름, 레인·스모크의 인자는 모델 conf 이름이다([run_full_eval.sh:81](run_full_eval.sh#L81), [레인 README:29](orchestration/README.md#L29), [smoke README:10](orchestration/smoke/README.md#L10)).

| 용도 | 명령 | 포함 단계 | 재개 | 실패 정책 | 자세한 문서·코드 근거 |
|---|---|---|---|---|---|
| config 일괄 | `bash "$N/run_full_eval.sh" <model_config_name>` | YAML tracks 순서: harness·nlu·functionchat·taubench·multimodal. agent 비활성 | 최상위 단계 재개 옵션 없음. 같은 timestamp와 하위 러너별 재개 기능을 구별 | 일반 실패·모르는 트랙은 계속 후 최종 rc 1; 유효한 config의 agent는 경고만; rc 3 또는 ≥129는 즉시 중단 | [§3.4](#34-전체-평가-한-모델-전-트랙-일괄), [run_full_eval.sh:81,142,187,200,242](run_full_eval.sh#L81) |
| 반복 | `bash "$N/run_repeated_eval.sh" <model_config> [횟수]` | config 일괄을 기본 3회 | 매번 새 `<시각>_rN`; 기존 결과 세션 충돌은 rc 1. 재개용 아님 | 하위 full의 nonzero는 기록하고 다음 반복 진행; 실패 있으면 최종 rc 1 | [run_repeated_eval.sh:14,23,43,56,76](run_repeated_eval.sh#L14) |
| KMMLU 레인 | `bash "$N/orchestration/lanes/kmmlu.sh" <model_conf>` | harness를 `${SESSION}_rN`으로 REPS회 | 같은 세션 재실행 시 harness의 기존 과목 결과 skip. full의 RESUME_FROM 의미 없음 | harness nonzero면 해당 rc로 즉시 중단 | [레인 README:122](orchestration/README.md#L122), [kmmlu.sh:32](orchestration/tracks/kmmlu.sh#L32), [run_harness.sh:167](shared/harness/run_harness.sh#L167) |
| tau standard 레인 | `bash "$N/orchestration/lanes/taubench_std4.sh" <model_conf>` | 단일 SESSION, standard 모드, 기본 trials 4 | full의 단계 재개 기능 없음 | taubench rc 그대로 반환 | [레인 README:100,122](orchestration/README.md#L100), [taubench_std4.sh:27](orchestration/tracks/taubench_std4.sh#L27) |
| full 레인 | `bash "$N/orchestration/lanes/full.sh" <model_conf>` | 반복마다 nlu→functionchat→tau solo→multimodal→조건부 judge 2종→derive. r1 끝에 별도 세션 tau standard 1회; harness 제외 | `FULL_RESUME_FROM=rN:stage`; KRETA 재개·derive 저장 산출 조건 별도 | rc 3/≥129와 nlu·functionchat·multimodal 실패는 즉시 중단. solo tau 일반 실패는 계속(최종 0 가능); judge/derive·standard 일반 실패와 기존 standard 세션 충돌은 누적 후 rc 1 | [README_full.md:13,53,72,76](orchestration/README_full.md#L13) |
| 실서버 스모크 | `bash "$N/orchestration/smoke/run_smoke.sh" <model_conf> [track…]` | 최소 요청: harness·tau preflight, nlu·functionchat·K-DTC 제한 입력. 정식 벤치 완주 아님 | 매 실행 새 임시 BASE; 이어 달리기 없음 | FAIL=1, 그 외 INCONCLUSIVE=77, PASS=0; CLI·설정 오류=2 | [smoke README:23,39,64](orchestration/smoke/README.md#L23) |
| 단일 트랙 | 예: `bash "$N/shared/functionchat/run_functionchat.sh" <model> <chat_url>` | 해당 트랙만. 예시는 추론→exact 채점 | 트랙별 계약 확인; 공통 재개 보장 없음 | 예시 FunctionChat은 set -e로 실패 중단. 다른 트랙은 각 usage·구현 확인 | [§3.3](#33-단일-트랙-실행), [run_functionchat.sh:3,5,62](shared/functionchat/run_functionchat.sh#L3) |

Timeout 정책: config 일괄(`run_full_eval.sh`)과 이를 호출하는 반복 실행은 FunctionChat·taubench에만 REQUEST/TASK 기본 **300/900초**를 적용한다. `AGENT_REQUEST_TIMEOUT`·`AGENT_TASK_TIMEOUT`의 비어 있지 않은 호출자 환경값이 우선하며, 미설정·빈 값은 기본값을 쓴다. 두 값은 양의 정수이고 TASK > REQUEST여야 한다. 단독 wrapper 기본값은 FunctionChat 60/120초, taubench 60/600초로 그대로다([run_full_eval.sh:9](run_full_eval.sh#L9), [run_functionchat.sh:40](shared/functionchat/run_functionchat.sh#L40), [run_functionchat.py:353](shared/functionchat/runner/run_functionchat.py#L353), [run_taubench.sh:65](shared/taubench/run_taubench.sh#L65)). 2026-10-20 이전 공식 r1~r3은 request 60초로 측정했으며, 해당 조건은 기존 결과 metadata에 기록되어 있다.

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
| **nlu** | 짧은 NLU smoke test (도메인 프롬프트 YAML) | 자체 runner (`nlu_gpustack.py`) |
| **functionchat** | 한국어 첫 호출 정확도 (exact 670 + 판정 636) | `FunctionChat-Bench` (kakao) |
| **taubench** | 다단계 실행 (telecom/retail/airline test 분할) | `tau2-bench` (sierra-research) |
| ~~agent~~ | ~~Tool calling · multi-step (L1~L7)~~ — **중단됨** | ~~`Ko-AgentBench`~~ |

> **agent 트랙 종료 보고: [`AGENT_TRACK_CLOSEOUT.md`](../AGENT_TRACK_CLOSEOUT.md)**
> 어떤 수치가 발행 가능한지는 그 문서가 유일한 기준이다. 결과 디렉토리에는
> 게이트가 거부한 런과 진단용 런이 섞여 있다.
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
| **K-MMBench** | 한국어 멀티모달 dev set (4,329 샘플) | NCSOFT |
| **MTVQA (KR)** | 9개 언어 중 한국어 서브셋, 실세계 장면 텍스트 free-form VQA | ByteDance |
| **KO-VLM-Benchmark** | KO-VQA / KO-VDC / KO-OCRAG | [Marker-Inc-Korea/KO-VLM-Benchmark](https://github.com/Marker-Inc-Korea/KO-VLM-Benchmark) (현재 stub) |
| **B-3 Structured Output** (자체) | 이미지 → JSON 변환 정확도 (포맷 준수) | `vsm/multimodal/data/structured_output/` |
| **B-4 Latency Profile** (자체) | 조건별(text-only / 256px / 1024px / multi-image) TTFT · tokens/sec | 자체 측정 스크립트 |

### 2.4 데이터셋 카테고리 매핑 (합산 금지)

| 카테고리 | 대표 벤치마크 | 발행 단위 |
|---|---|---|
| 문서 OCR · 구조 이해 | KRETA, K-DTCBench, K-MMBench (문서/표/차트 카테고리) | 벤치별 accuracy와 분자/분모 |
| 실세계 장면 텍스트 | MTVQA(KR), KO-VLM-Benchmark | 벤치별 native metric |
| 자유 서술형 VQA | KOFFVQA | 0–10 rubric score, 인간 검증 전 PROVISIONAL |

서로 다른 데이터셋과 판정 축은 척도가 같지 않으므로 종합 점수로 합산하거나 평균하지 않는다.
발행 가능 여부와 대표 런 선정은 `MULTIMODAL_PUBLISH_CONTRACT.md`를 따른다.

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

재개 시 이미 끝난 벤치를 건너뛰려면 같은 `EVAL_TIMESTAMP`를 지정하고 `run_all.sh`를 직접 호출하면서 `SKIP_BENCHES`에 공백으로 구분한 이름을 전달한다. 허용 이름은 `kreta k_dtcbench koffvqa mtvqa_kr k_mmbench b4_latency_profile`이다. 미설정·빈 값·공백만 있는 값은 제외하지 않으며, 모르는 이름은 세션 파일 생성과 벤치 실행 전에 stderr 두 줄을 출력하고 rc 2로 종료한다. 이때 직접 호출한 스크립트 자체는 파일을 만들거나 바꾸지 않는다(호출자의 리다이렉션·로그는 별개). 마지막 sanity 검사는 건너뛴 벤치의 기존 결과도 검사한다.

모델 YAML·serving profile의 `skip_benches`는 해당 모델에서 숫자가 의미 없는 벤치를 아예 재지 않는 측정 제외 정책이며 현재 `b4_latency_profile`만 허용한다. `run_full_eval.sh`와 레인은 로더가 `SKIP_BENCHES`를 unset하거나 YAML 값으로 설정하므로, 최상위 명령 앞에 지정한 재개용 값은 유지되지 않는다. `run_full_eval.sh`에서는 로더 뒤 source되는 `.env`에서 export하면 전달될 수 있으나, 재개용 사용법으로 권장하지 않는다.

발행 `--strict --run <세션>`은 기대 벤치의 완주 여부를 검사하지 않는다. 결과 원천이 전혀 없는 벤치의 부재와, 존재하는 결과의 게이트 기록 누락·손상은 구별해야 한다.

발행 보고서: N 루트에서 `python3 -m reports.report_multimodal_tracks --base .`. 저장소 밖 cwd에서는 `PYTHONPATH="$N${PYTHONPATH:+:$PYTHONPATH}"`를 명령 앞에 붙인다.

개별 벤치마크 실행은 `vsm/multimodal/run_<benchmark>.sh` 직접 호출.

KRETA가 중단된 경우 `vsm/multimodal/run_kreta_resume.sh`로 이어서 진행한다. 최초 실행이 기록한 checkpoint context(세션·모델·모드·endpoint·max tokens)가 현재 실행과 정확히 같을 때만 기존 jsonl을 허용하며, 다른 모델의 jsonl은 evaluate 전에 제거한다. context가 없거나 다르면 stale checkpoint 재발행을 막기 위해 중단하고 `run_kreta.sh`로 새로 시작해야 한다. 일치할 때는 이미 처리된 `id`를 skip하고 남은 샘플만 추론한다.

KRETA 러너는 3번째 인자로 프롬프트 모드(`SETTING`)를 받는다 — `direct`(글자만 답, 빠름·DGX Spark 권장) / `default`(추론 후 답). 모드별 생성 상한은 자동 설정되며 자세한 내용은 아래 §3.8 운영 노트 참고. 예: `bash vsm/multimodal/run_kreta_resume.sh <model> direct <url>`.

KOFFVQA도 idempotent resume를 지원한다(`koffvqa_run.py`). 같은 `EVAL_TIMESTAMP`로 재실행하면 `out_dir/results.json`의 **유효 응답**(error 없음 + 비어있지 않은 prediction)은 `index` 기준으로 재사용하고, **에러·타임아웃·누락 항목만 다시 호출**한 뒤 results.json·xlsx·summary를 머지해 재생성한다. 따라서 일부 샘플이 타임아웃으로 실패하면 **같은 명령을 재실행하는 것만으로 복구**된다 — 별도 retry 스크립트 불필요. `run_koffvqa.sh`는 `KOFFVQA_TIMEOUT` env(기본 600초, kreta `KRETA_TIMEOUT`과 일관)를 받으며, 게이트웨이 200초 컷을 피하려면 직접 vLLM 포트를 `<url>`로 준다. 예: `KOFFVQA_TIMEOUT=600 bash vsm/multimodal/run_koffvqa.sh <model> http://<host>:<vllm_port>/v1`. 처음부터 다시 돌리려면 `koffvqa_run.py --no-resume`.

멀티모달 발행 계층 회귀 테스트:

```bash
.venv/bin/python -m pytest shared/multimodal/tests/ -q
```

### 3.4 전체 평가 (한 모델 전 트랙 일괄)

`run_full_eval.sh`가 모델 config(`configs/models/<NAME>.yaml`)의 `tracks` 목록 순서대로 트랙(harness · nlu · functionchat · taubench · multimodal)을 실행한다. agent(Ko-AgentBench)는 fixture-cache miss 율 때문에 dispatch가 비활성이며, 유효한 config가 dispatch에 도달했을 때 목록에 있으면 unknown track 경고만 낸다. agent 외 모르는 트랙은 실패로 누적해 최종 rc 1로 끝낸다. 로더의 agent.native_tool_calling 명시 조건은 그대로다([run_full_eval.sh:200](run_full_eval.sh#L200)). full 레인의 단계 구성과는 다르므로 위 [진입점 표](#실행-진입점)를 확인한다.

```bash
# configs/models/<model_config_name>.yaml의 모델·엔드포인트·tracks를 사용
bash run_full_eval.sh <model_config_name>
```

특징:

- INT·TERM·EXIT trap의 cleanup은 그룹 리더일 때 같은 그룹의 다른 PID를, 아니면 추적 중인 TRACK_PID와 자손을 정리한다. setsid가 없는 환경에서는 그룹 리더 재실행을 건너뛴다([run_full_eval.sh:32,46,56,72](run_full_eval.sh#L32)).
- FunctionChat·taubench에만 REQUEST/TASK 300/900초(비어 있지 않은 호출자 환경값 우선)를 주입하고, 다른 트랙에서는 두 상속값을 제거한다. 유효값은 `_master.log` 머리와 `CMD:`에 기록한다. 잘못된 값은 venv 활성화·키 읽기·HTTP preflight 전에 rc 2로 거절한다. 반복 실행은 이 rc 2도 실패로 기록하고 나머지 반복을 계속한 뒤 최종 rc 1로 끝낸다([run_full_eval.sh:9,173,195,218](run_full_eval.sh#L9), [run_repeated_eval.sh:56,76](run_repeated_eval.sh#L56)).
- 트랙별 로그: `logs/<EVAL_TIMESTAMP>/<track>.log`. timestamp 우선순위는 환경변수 → 세션 파일 → 새 시각이다([run_full_eval.sh:142,159,169](run_full_eval.sh#L142)).
- 일반 트랙 실패와 모르는 트랙(agent 제외)은 누적하고 다음 트랙을 실행한 뒤 최종 rc 1로 끝낸다. 유효한 config의 agent는 경고만 낸다. 단, rc 3 또는 ≥129는 그 rc로 즉시 중단한다([run_full_eval.sh:180,187,224,242](run_full_eval.sh#L180)). 이미지 결과 JSON 읽기·디코딩·파싱 오류도 sanity 실패로 처리하며 기존 측정 artifact는 다시 쓰지 않는다. run_all의 rc 1은 config full에서 누적·계속하지만 full 레인에서는 해당 반복을 중단한다([run_all.sh:199](shared/multimodal/run_all.sh#L199), [full.sh:199](orchestration/tracks/full.sh#L199)). run_repeated_eval은 실패를 기록하고 다음 반복을 진행한다([run_repeated_eval.sh:56](run_repeated_eval.sh#L56)).

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

scorer는 매번 세 version을 함께 낸다: `agent_det_v2=("L1","L2","L3","L4","L5","L6")`, `agent_det_v3=("L1","L2","L3","L4","L5","L6")`, `agent_det_v4=("L1","L2","L3","L5","L6")`. v2와 v3 정의·블록은 동결돼 그대로 유지된다. 터미널에는 세 headline과 정확한 분모, v2/v3/v4의 전체 L1~L7 matrix가 함께 나오며 scalar headline만 단독으로 출력하지 않는다. summary의 `headline_denominators`, 세 `by_level` matrix, `l3_retry_inflation`, `l4_fixture_coverage`, `l5_ceiling`에도 같은 정보를 기록한다. `possible_absorbed_request_timeout_diagnostics`와 `l7_partial_coverage_diagnostics`는 저장 필드만 읽는 annotate-only 블록이다. L7은 실행하지만 기록 전용이고, `ContextRetention_det`·`ResultFieldCoverage_det` 두 결정론 지표와 L7 레벨 자체는 어느 headline에도 들어가지 않는다. 다섯 judge 지표는 현재 측정하지 않아 `judge_missing`으로 남으므로, 이 점수는 결정론적 부분집합만 나타낸다.

##### 결과 보고 단위: 레벨 점수

코드와 저장 schema는 위의 `agent_det_v2`/`agent_det_v3`/`agent_det_v4` composite를 계속 계산·보존하지만, **모델 비교에서 composite를 결과로 보고하지 않는다.** 결과는 L1~L6 레벨 점수를 각각 제시한다. 현재 대표 run 수, 레벨별 raw task 수, `in_score` metric 수, 최소·최대·spread, headline 분산 점유율, L2 분포, 반복 실험 spread, L5 상한, L7 상태와 모든 annotation 진단은 저장 산출물만 읽는 루트의 `./report_agent_levels.sh`가 계산한다. README에는 그 실측값을 복사하지 않는다.

동일 가중은 동일 영향력을 만들지 않는다. 같은 계수로 평균해도 각 레벨이 composite 변동에 주는 영향은 그 레벨의 모델 간 분산에 비례하며, 현재 코호트의 분산 점유율은 report가 매번 다시 계산한다. 레벨의 척도도 서로 같지 않다. 구조적으로 압축된 상한, 포화한 선택 문제, 일반적인 정확도 범위, fixture coverage가 한 평균 안에 섞여 있으므로 수치가 같은 레벨끼리도 같은 능력 차이를 뜻하지 않는다. L4는 모델 능력과 분리되지 않는 fixture coverage를 측정하므로 v4 분모에서 제외됐다. 따라서 레벨 점수를 다시 평균해 단일 모델 점수나 순위를 만들지 않는다.

composite의 허용 용도는 **같은 저장 run을 재채점했을 때 값이 바뀌었는지 확인하는 drift detection**뿐이다. `check_results_fresh.sh`가 이 계약을 보호한다. 서로 다른 모델의 비교·정렬·ranking에는 사용하지 않는다. report는 완전한 L1~L6 run 중 task `error`가 없는 최신 run을 우선하고, clean run이 없는 모델도 가장 최근 run의 모든 레벨 점수를 유지하되 오염된 task와 레벨을 note에 표시한다. 동일 harness 조건의 완전 run 반복군을 자동 검출하며, L4·L6 각 셀에 단일 관측인지 반복군이 있는지를 표시한다.

`metadata.success_rate`는 정확도가 아니라 **생존 신호**(`final_response` 존재 AND `steps >= 1`)다. 결정론 점수와 무관하므로 모델 점수로 인용하지 않는다.

현재 다음 레벨은 모델 간 깨끗한 비교 자료로 사용할 수 없다.

| 레벨 | 알려진 결함 |
|---|---|
| L2 | runner의 task 변환이 원본 `available_tools`를 누락해 정답 tool만 노출하므로 선택 정확도가 자명해질 수 있다. |
| L3 | miss는 response outcome으로 직접 점수화되지 않지만 retry-inflated call sequence로 전파된다. `no_tool_calls_emitted`, `no_cache_miss`, `cache_miss_only_at_final_call`, `cache_miss_before_final_call`을 분리해 진단한다. |
| L4 | Coverage/SourceEPR는 cache miss를 `success=False`로 취급해 fixture coverage와 모델 실패를 분리할 수 없다. 따라서 v4 headline에서 제외하고 점수와 miss bucket을 함께 본다. |
| L5 | runner가 첫 pass에서 fallback tool을 숨기고 실패 call 뒤 reset한 다음 pass에서만 노출하며, 필수 주입 실패가 total-call 분모에 남는다. 그 결과 일부 metric의 구조적 상한이 압축된다. |
| L6 | v3에서 polarity를 수정했다. v2 L6는 방향이 뒤집힌 known-invalid 점수이므로 v2 평균을 순위에 쓰지 않는다. |

- **v4 고정 제외 규칙:** 모든 in-scope metric의 success/count가 call shape가 아니라 tool-response outcome에서 나오고, pinned fixture의 outcome label에서 cache miss가 material하며, level score를 miss process와 분리할 수 없고, freeze 아래에서 miss를 수리할 수 없는 레벨만 새 version의 headline에서 제외한다. L4는 이 조건을 만족한다. L3는 call-shape metric이라 첫 조건을 만족하지 않고, L5는 fixture 문제와 구조적 상한 문제를 분리할 수 있으며, L6 v3는 response payload가 아니라 refetch 발생 여부를 읽는다. 이 규칙은 `V4_HEADLINE_LEVELS`의 문서화된 근거이며 runtime auto-exclusion이 아니다.
- **L5 상한은 annotate-only:** `AdaptiveRoutingScore`는 모델이 스스로 선택한 routing 속도가 아니라 harness가 강제한 reset second pass의 위치를 측정한다. L5는 변별 신호를 가지되 scale이 압축돼 있다. summary와 report는 task별 실측 최댓값과 구조적 상한을 병기하고 점수를 rescale·clamp하지 않는다.
- **cache miss는 annotate-only:** 저장 결과의 모든 실행 call을 `exact`/`presentation_sibling`/`semantic_mismatch`/`query_absent`/`signature_mismatch`/`tool_absent`/`unclassified`의 ordered partition으로 분류하지만 relaxed fixture를 응답으로 주지 않는다. 결과 수·페이지·정렬은 반환 entity나 cardinality를 바꿀 수 있어 semantic이며, presentation 차이는 응답 표현만 달라지는 경우로 제한한다. 현재 miss 수·비율·bucket은 report가 산출물에서 계산한다.
- **fixture schema drift 위험(별도):** pinned catalog와 현재 signature hash가 다른 fixture는 도달 불가다. 이는 miss 분류와 별개의 fixture 유지보수 위험이며 catalog 크기와 영향 범위는 정적 README 수치로 관리하지 않는다.
- **동일 가중 동결:** L2 포화를 근거로 현재 코호트에서 가중치를 역산하지 않는다. 이후 약한 모델은 여전히 L2에 실패할 수 있다. 레벨 동일 가중은 의도적으로 동결된 점수 정의이며 변경에는 version bump가 필요하다. L2의 실제 결함인 `available_tools` 누락은 별도 수정 사항이다.
- **L7은 승격하지 않는다:** 승격에는 모든 대표 run이 metric을 제공하고, 각 raw task가 metric에 적용 가능하며, 모델 간 분리 신호도 있어야 한다. `./report_agent_levels.sh`가 현재 산출물에서 이 조건과 결론을 계산한다. metric·`in_score`·분모는 그대로 두고 partial distribution만 annotate-only로 기록한다.

##### L7 `ResultFieldCoverage_det` 해석

`ResultFieldCoverage_det`는 golden-fields entry의 required field를 모두 덮었을 때만 그 entry를 성공으로 센다. 따라서 partial field hit가 있어도 entry 점수는 실패일 수 있으며, **no coverage와 not complete coverage는 다르다.** 현재 대표 run에는 complete entry가 있는 관측도 있어 과거의 전 모델 동일값 주장은 더 이상 성립하지 않는다. 정확한 score 분포·spread·적용 가능 task 분포와 승격 판정은 report의 L7 블록이 매번 계산한다.

metric은 seed payload만 해석하고 normalization/value matcher를 적용하며, 긴 free text와 unresolved field는 적용 대상에서 제외한다. `l7_partial_coverage_diagnostics`는 entry별 `(required, present)` 분포와 field hit를 보존하지만 기존 all-or-nothing 점수를 바꾸지 않는다. 장문 secondary field를 요약한 답이 entry 전체 실패로 접힐 수 있다는 구조적 한계 때문에, 완전 적용 가능성이 확보되기 전에는 모델 간 spread만으로 승격하지 않는다.

레벨마다 `in_score` metric 수와 raw task 수가 다르므로 `agent_score`를 표본 수나 정밀도로 가중한 평균으로 해석하면 안 된다. 현재 수는 report에서 확인한다.

기존 `L*.json`은 평가를 다시 실행하지 않고 재채점할 수 있다. `--results-dir`을 써도 vendored metric을 불러오려면 `MODEL_TEST_BASE`가 반드시 필요하다.

```bash
MODEL_TEST_BASE="$PWD" .venv/bin/python -m shared.agent.scoring.score_run \
  --results-dir results/<model>/<timestamp>/language/<agent-track>
MODEL_TEST_BASE="$PWD" .venv/bin/python -m shared.agent.scoring.validate_run \
  --results-dir results/<model>/<timestamp>/language/<agent-track>
```

validator는 scoring version·요약 구조·점수 범위, judge/L7의 기록 전용 계약, raw/summary의 native-tool 모드 일치, v2/v3의 6레벨 및 v4의 고정 5레벨 완전성·평균 불변식을 검사하고 포화/바닥·생존 신호 차이는 경고한다. v4의 level set은 정확히 `("L1","L2","L3","L5","L6")`이어야 하며 stated denominator에서 headline을 재구성한다. 채점된 레벨의 cache miss rate가 20%를 넘으면 실행 call 5개 중 1개보다 많은 도구 증거가 빠진 것으로 보고 임계값과 실측 분수를 명시한 경고를 내되 실패시키지 않는다. 종료 코드는 `0`=유효(경고 허용), `1`=검증 실패, `2`=호출·설정·입력 읽기·내부 오류다. `run_full_eval.sh` 의 agent 트랙과 validator 자동 실행은 현재 비활성이다(스크립트 주석 참조). validator 는 `.venv/bin/python -m shared.agent.scoring.validate_run` 으로 실행한다.

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

- **`KRETA_MAX_TOKENS`** (생성 상한): 러너가 모드별 기본값을 자동 export — `direct`→**32**, 그 외→**4096**. env로 override 가능하며, wrapper가 실제 최종값을 `run_config.json`과 NATIVE sidecar protocol에 기록한다.
  - ⚠️ `default` 모드를 1024 등으로 낮추지 말 것: 응답의 ~13%(가장 긴 = 가장 어려운 문항)가 잘려 답이 유실되고, 손실이 난이도 쪽으로 **편향**되어 랭킹을 왜곡한다. `default`는 4096 유지, 속도가 필요하면 `direct` 사용.
- **`KRETA_TIMEOUT`** (요청 timeout, 기본 **600초**): 큰 비전 prefill/긴 생성이 timeout→오답으로 기록되는 것을 방지.
- **vLLM `--max-model-len`**: KRETA 요청 최대 컨텍스트 ≈ 비전(~16K) + 텍스트 + 출력 ≈ 20.5K. **24576 이상** 필요 (16384는 ~1.3% 요청이 길이 초과로 거부됨).
- **`KRETA_WORKERS`**: 메모리 압박 완화를 위해 dense 대형 모델은 **2** 권장 (4 이상은 모델 인스턴스 hang 사례 있음). 러너 기본 2.
- vLLM 엔진이 장시간/메모리 압박으로 deadlock되면(`/v1/models`는 응답하나 `/v1/chat`만 hang) 모델 컨테이너 재시작으로 해소.

---

## 4. 디렉토리 구조

```
foundation_model_test_non_thinking/
├── shared/                        # 트랙 구현의 단일 소스 — 각 트랙은 run_*.sh(진입) · runner/ · scoring/ · tests/
│   ├── harness/                   # KMMLU (lm-evaluation-harness 래퍼, harness_lib.sh 가 정지·검증·잠금)
│   ├── nlu/                       # NLU (nlu_gpustack.py + scoring/)
│   ├── functionchat/              # FunctionChat (runner/ · scoring/ · judge/)
│   ├── taubench/                  # tau2-bench (runner/ · scoring/)
│   ├── agent/                     # Ko-AgentBench (gpustack_custom/ · scoring/; run_full_eval 에서는 비활성)
│   ├── multimodal/                # 이미지 벤치 (benches/ · publish/ · run_<bench>.sh · run_all.sh)
│   ├── publish/                   # 발행 등급 (claims.py)
│   ├── serving/                   # 서빙 제약 (constraints.py)
│   ├── jsonwrite/                 # 공용: 원자적 JSON 쓰기 (write_json_atomic)
│   ├── resultspath/               # 공용: results/ 모델 폴더 철자 재사용·채점 경로·실행 시각
│   └── results_dir.sh             # 위 철자 재사용의 bash 판 (run_harness.sh 가 source)
├── llm/  slm/  vlm/  vsm/         # 클래스별 진입점 = shared/ 로의 symlink + recommended_models.md + 평가계획
├── orchestration/                 # 레인 실행·감시: run_lane.sh + tracks/ + models/<모델>.conf · lane_guard.sh · tests/ · README
├── reports/                       # 보고서 패키지: python3 -m reports.report_<track>_tracks
├── configs/                       # 모델별 YAML (models/), 로더, model_identity.json, serving_profiles/
├── data/                          # 외부 repo 중앙 clone (.gitignore)
├── results/                       # 평가 결과 (git 추적 — results/INDEX.md 가 본·보조·실험·구판 분류)
├── logs/                          # 실행 로그 (.gitignore; resume_orch/ 에 레인 상태·orchestrator.log)
├── run_full_eval.sh               # 한 모델 전 트랙 일괄 (config 의 tracks 순서)
├── start_eval_session.sh / end_eval_session.sh / check_servers.sh / sync.sh
├── CONVENTIONS.md                 # 코드 작성 규칙 (크기·분해·공용 모듈·시험·검증 방식)
└── README.md
```

코드 루트에서 `N="$(pwd -P)"`를 설정한다. KMMLU·taubench std4 같은 단일 트랙 재측정은 `bash "$N/orchestration/lanes/<track>.sh" <model_conf>`로(track: kmmlu·taubench_std4·full), 절차는 `orchestration/README.md`.

`bash tests/run_pytests.sh`로 전체 Python 시험을 실행하며, 선택 트랙 이름과 pytest 옵션을 뒤에 붙일 수 있다(예: `bash tests/run_pytests.sh nlu -q`).

모든 트랙 보고서는 N 루트에서 `python3 -m reports.report_<track>_tracks`로 실행한다(예: `python3 -m reports.report_harness_tracks`). `--base`는 결과 위치만 지정하며 기본값은 이 저장소다. 채점 코드는 실행 중인 저장소의 패키지를 쓴다. 저장소 밖 cwd에서는 N의 절대 경로를 `PYTHONPATH="$N${PYTHONPATH:+:$PYTHONPATH}"`로 명령 앞에 붙인다. 자세한 예는 [`reports/README.md`](reports/README.md)를 따른다.

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
