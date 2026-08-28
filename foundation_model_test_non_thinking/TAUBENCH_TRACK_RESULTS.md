# taubench 트랙 결과

이 파일은 `report_taubench_tracks.py` 가 `summary.json` 에서 생성한다. 손으로 고치지 말 것.

읽는 법:

- **도메인을 가로질러 평균하지 않는다.** 상류 Overall 은 retail/airline/telecom 을
  `base` split 전 과제로 재야 성립한다. 여기 수치는 `test` split 이고 retail 은 부분집합이다.
- 점수는 `Pass^1` 을 100점 척도로 적은 것이다. 괄호는 통과/측정 건수다.
- 부분집합은 도메인 이름을 달지 않는다 (`retail/test/judge-free-29`).
- 사용자 시뮬레이터 프로토콜이 고정되지 않은 런은 모델 간 표에 넣지 않는다.

## 비교 코호트

### airline/test — protocol `140846a900bd1be2`

사용자 시뮬레이터: `openrouter/openai/gpt-4.1-mini` · mode `standard` · tau2 `1.0.1`

> 비교 가능한 런은 3개다. 제외 사유가 적힌 행은 비교에서 빼고 읽을 것.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| google_gemma_4_26b_a4b_it | airline/test | 65.00 (13/20) | — |
| google_gemma_4_26b_a4b_it | airline/test | 65.00 (13/20) | — |
| qwen_qwen3.5_35b_a3b_fp8 | airline/test | 75.00 (15/20) | — |
| qwen_qwen3.5_35b_a3b_fp8 | airline/test | 발행 불가 | 게이트 거부 |

### airline/test — protocol `2e87e9391477bc93`

사용자 시뮬레이터: `openrouter/openai/gpt-4.1-mini` · mode `standard` · tau2 `1.0.1`

> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| google_gemma_4_26b_a4b_it | airline/test | 50.00 (10/20) | 사용자 프로토콜 미고정 |
| qwen_qwen3.5_35b_a3b_fp8 | airline/test | 85.00 (17/20) | 사용자 프로토콜 미고정 |

### retail/test — protocol `948defa31158c7a8`

사용자 시뮬레이터: `openai/gpt-4.1-mini` · mode `standard` · tau2 `1.0.1`

> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| google_gemma_4_26b_a4b_it | retail/test/judge-free-29 | 75.86 (22/29) | 사용자 프로토콜 미고정, 공식 split 부분집합 |
| qwen_qwen3.5_35b_a3b_fp8 | retail/test/judge-free-29 | 72.41 (21/29) | 사용자 프로토콜 미고정, 공식 split 부분집합 |

### telecom/test — protocol `c3dc8e7416e11d86`

사용자 시뮬레이터: `openai/qwen_qwen3.5_35b_a3b_fp8` · mode `standard` · tau2 `1.0.1`

> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 47.50 (19/40) | 사용자 프로토콜 미고정 |
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 47.50 (19/40) | 사용자 프로토콜 미고정 |
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 47.50 (19/40) | 사용자 프로토콜 미고정 |
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 47.50 (19/40) | 사용자 프로토콜 미고정 |

### telecom/test — protocol `c67a28b832f76016`

사용자 시뮬레이터: `openrouter/openai/gpt-4.1-mini` · mode `standard` · tau2 `1.0.1`

> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 발행 불가 | 게이트 거부 |

### telecom/test — protocol `f3db6c2ca3dcf8c7`

사용자 시뮬레이터: `openai/gpt-4.1-mini` · mode `standard` · tau2 `1.0.1`

> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| google_gemma_4_26b_a4b_it | telecom/test | 발행 불가 | 게이트 거부, 사용자 프로토콜 미고정 |
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 90.00 (36/40) | 사용자 프로토콜 미고정 |

### telecom/test — protocol `f42a94d8be122d02`

사용자 시뮬레이터: `openrouter/openai/gpt-4.1-mini` · mode `standard` · tau2 `1.0.1`

> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 발행 불가 | 게이트 거부 |

## 재현성

- `openai/google_gemma_4_26b_a4b_it` · protocol `140846a900bd1be2` — **DIVERGED**
  - 런 2개: `tbpin_20260827`, `tbrep_20260827`
  - 통과 건수: [13, 13]
  - 런마다 달라진 과제 6건
  - 통과 과제 집합이 런마다 다르다 (6건). 건수가 같아도 다른 과제를 맞힌 것이면 같은 측정이 아니다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `140846a900bd1be2` — **DIVERGED**
  - 런 2개: `tbpin_20260827`, `tbrep_20260827`
  - 통과 건수: [15, 15]
  - 런마다 달라진 과제 4건
  - 통과 과제 집합이 런마다 다르다 (4건). 건수가 같아도 다른 과제를 맞힌 것이면 같은 측정이 아니다
- `openai/google_gemma_4_26b_a4b_it` · protocol `2e87e9391477bc93` — **UNVERIFIED**
  - 런 1개: `tbair_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `2e87e9391477bc93` — **UNVERIFIED**
  - 런 1개: `tbair_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/google_gemma_4_26b_a4b_it` · protocol `948defa31158c7a8` — **UNVERIFIED**
  - 런 1개: `tbretail_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `948defa31158c7a8` — **UNVERIFIED**
  - 런 1개: `tbretail_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `c3dc8e7416e11d86` — **IDENTICAL** — 통과 과제 집합이 완전히 같다
  - 런 4개: `20260823_021442`, `tb_std_20260819`, `tb_std_rep2_20260820`, `tb_std_rep3_20260823`
  - 통과 건수: [19, 19, 19, 19]
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `c67a28b832f76016` — **UNVERIFIED**
  - 런 1개: `tbtel_b_20260828`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/google_gemma_4_26b_a4b_it` · protocol `f3db6c2ca3dcf8c7` — **UNVERIFIED**
  - 런 1개: `tbfix_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `f3db6c2ca3dcf8c7` — **UNVERIFIED**
  - 런 1개: `tbfix_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `f42a94d8be122d02` — **UNVERIFIED**
  - 런 1개: `tbtel_a_20260828`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
