# taubench 트랙 결과

이 파일은 `reports/report_taubench_tracks.py` 가 `summary.json` 에서 생성한다. 손으로 고치지 말 것.

읽는 법:

- **도메인을 가로질러 평균하지 않는다.** 상류 Overall 은 retail/airline/telecom 을
  `base` split 전 과제로 재야 성립한다. 여기 수치는 `test` split 이고 retail 은 부분집합이다.
- 점수는 `Pass^1` 을 100점 척도로 적은 것이다. 괄호는 통과/측정 건수다.
- 부분집합은 도메인 이름을 달지 않는다 (`retail/test/judge-free-29`).
- 사용자 시뮬레이터 프로토콜이 고정되지 않은 런은 모델 간 표에 넣지 않는다.

## 비교 코호트

### telecom/test — protocol `0d0c0f1a90bb63de`

사용자 시뮬레이터: `openai/gpt-4.1-mini` · mode `standard` · tau2 `1.0.1`

> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| google_gemma_4_26b_a4b_it | telecom/test | 발행 불가 | 게이트 거부, 사용자 프로토콜 미고정 |
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 90.00 (36/40) | 사용자 프로토콜 미고정 |

### telecom/test — protocol `275fbfbeabee9737`

사용자 시뮬레이터: `openrouter/openai/gpt-4.1-mini` · mode `standard` · tau2 `1.0.1`

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| google_diffusiongemma_26B_A4B_it | telecom/test | 37.50 (Pass^1, 과제 40, 시행 [4]) | — |
| google_gemma_4_26b_a4b_it | telecom/test | 49.38 (Pass^1, 과제 40, 시행 [4]) | — |
| nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16 | telecom/test | 4.38 (Pass^1, 과제 40, 시행 [4]) | — |
| qwen_qwen3.8_27B_FP8 | telecom/test | 56.25 (Pass^1, 과제 40, 시행 [4]) | — |
| qwen_qwen3.8_27b | telecom/test | 58.75 (Pass^1, 과제 40, 시행 [4]) | — |

### retail/test — protocol `2892aac47f8f9475`

사용자 시뮬레이터: `openai/gpt-4.1-mini` · mode `standard` · tau2 `1.0.1`

> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| google_gemma_4_26b_a4b_it | retail/test/judge-free-29 | 75.86 (22/29) | 사용자 프로토콜 미고정, 공식 split 부분집합 |
| qwen_qwen3.5_35b_a3b_fp8 | retail/test/judge-free-29 | 72.41 (21/29) | 사용자 프로토콜 미고정, 공식 split 부분집합 |

### telecom/test — protocol `6fa5aa02fd58fc7e`

사용자 시뮬레이터: `openrouter/openai/gpt-4.1-mini` · mode `standard` · tau2 `1.0.1`

> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 발행 불가 | 게이트 거부 |

### airline/test — protocol `9eb0c62bdbcd226d`

사용자 시뮬레이터: `openrouter/openai/gpt-4.1-mini` · mode `standard` · tau2 `1.0.1`

> 비교 가능한 런은 3개다. 제외 사유가 적힌 행은 비교에서 빼고 읽을 것.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| google_gemma_4_26b_a4b_it | airline/test | 65.00 (13/20) | — |
| google_gemma_4_26b_a4b_it | airline/test | 65.00 (13/20) | — |
| qwen_qwen3.5_35b_a3b_fp8 | airline/test | 75.00 (15/20) | — |
| qwen_qwen3.5_35b_a3b_fp8 | airline/test | 발행 불가 | 게이트 거부 |

### telecom/test — protocol `b190004379363859`

사용자 시뮬레이터: `openai/qwen_qwen3.5_35b_a3b_fp8` · mode `standard` · tau2 `1.0.1`

> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 47.50 (19/40) | 사용자 프로토콜 미고정 |
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 47.50 (19/40) | 사용자 프로토콜 미고정 |
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 47.50 (19/40) | 사용자 프로토콜 미고정 |
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 47.50 (19/40) | 사용자 프로토콜 미고정 |

### airline/test — protocol `b6b79e8d5fc0d9f7`

사용자 시뮬레이터: `openrouter/openai/gpt-4.1-mini` · mode `standard` · tau2 `1.0.1`

> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| google_gemma_4_26b_a4b_it | airline/test | 50.00 (10/20) | 사용자 프로토콜 미고정 |
| qwen_qwen3.5_35b_a3b_fp8 | airline/test | 85.00 (17/20) | 사용자 프로토콜 미고정 |

### telecom/test — protocol `b73e96808b553a41`

사용자 시뮬레이터: `openrouter/openai/gpt-4.1-mini` · mode `standard` · tau2 `1.0.1`

> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| google_gemma_4_26b_a4b_it | telecom/test | 발행 불가 | 게이트 거부 |
| qwen_qwen3.5_35b_a3b_fp8 | telecom/test | 발행 불가 | 게이트 거부 |

### telecom/test — protocol `c19af26e7c6a92bf`

사용자 시뮬레이터: `None` · mode `solo` · tau2 `1.0.1`

> 비교 가능한 런은 9개다. 제외 사유가 적힌 행은 비교에서 빼고 읽을 것.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| google_diffusiongemma_26B_A4B_it | telecom/test | 27.50 (11/40) | — |
| google_diffusiongemma_26B_A4B_it | telecom/test | 20.00 (8/40) | — |
| google_diffusiongemma_26B_A4B_it | telecom/test | 22.50 (9/40) | — |
| google_gemma_4_26b_a4b_it | telecom/test | 62.50 (25/40) | — |
| google_gemma_4_26b_a4b_it | telecom/test | 62.50 (25/40) | — |
| google_gemma_4_26b_a4b_it | telecom/test | 40.00 (16/40) | — |
| nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16 | telecom/test | 10.00 (4/40) | — |
| nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16 | telecom/test | 10.00 (4/40) | — |
| nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16 | telecom/test | 5.00 (2/40) | — |
| qwen_qwen3.8_27B_FP8 | telecom/test | 발행 불가 | 게이트 거부 |
| qwen_qwen3.8_27B_FP8 | telecom/test | 발행 불가 | 게이트 거부 |
| qwen_qwen3.8_27B_FP8 | telecom/test | 발행 불가 | 게이트 거부 |
| qwen_qwen3.8_27b | telecom/test | 발행 불가 | 게이트 거부 |
| qwen_qwen3.8_27b | telecom/test | 발행 불가 | 게이트 거부 |
| qwen_qwen3.8_27b | telecom/test | 발행 불가 | 게이트 거부 |

### telecom/test — protocol `d4160331c47bd2b2`

사용자 시뮬레이터: `None` · mode `solo` · tau2 `1.0.1`

> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.

| 모델 | 축 | Pass^1 | 비교 제외 사유 |
|---|---|---:|---|
| google_gemma_4_26b_a4b_it | telecom/test | 발행 불가 | 게이트 거부 |

## 재현성

- `openai/google_gemma_4_26b_a4b_it` · protocol `0d0c0f1a90bb63de` — **UNVERIFIED**
  - 런 1개: `tbfix_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `0d0c0f1a90bb63de` — **UNVERIFIED**
  - 런 1개: `tbfix_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/google_diffusiongemma_26B_A4B_it` · protocol `275fbfbeabee9737` — **UNSUPPORTED**
  - 런 1개: `tbstd4_20261011`
  - 다중 시행 산출물이다 — 통과 집합 비교는 Pass^k 를 대신할 수 없다
- `openai/google_gemma_4_26b_a4b_it` · protocol `275fbfbeabee9737` — **UNSUPPORTED**
  - 런 1개: `tbstd4_20261003`
  - 다중 시행 산출물이다 — 통과 집합 비교는 Pass^k 를 대신할 수 없다
- `openai/nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16` · protocol `275fbfbeabee9737` — **UNSUPPORTED**
  - 런 1개: `tbstd4_20261010`
  - 다중 시행 산출물이다 — 통과 집합 비교는 Pass^k 를 대신할 수 없다
- `openai/qwen_qwen3.8_27B_FP8` · protocol `275fbfbeabee9737` — **UNSUPPORTED**
  - 런 1개: `20261003_171917_tbstd4`
  - 다중 시행 산출물이다 — 통과 집합 비교는 Pass^k 를 대신할 수 없다
- `openai/qwen_qwen3.8_27b` · protocol `275fbfbeabee9737` — **UNSUPPORTED**
  - 런 1개: `tbstd4_20261003`
  - 다중 시행 산출물이다 — 통과 집합 비교는 Pass^k 를 대신할 수 없다
- `openai/google_gemma_4_26b_a4b_it` · protocol `2892aac47f8f9475` — **UNVERIFIED**
  - 런 1개: `tbretail_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `2892aac47f8f9475` — **UNVERIFIED**
  - 런 1개: `tbretail_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `6fa5aa02fd58fc7e` — **UNVERIFIED**
  - 런 1개: `tbtel_a_20260828`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/google_gemma_4_26b_a4b_it` · protocol `9eb0c62bdbcd226d` — **DIVERGED**
  - 런 2개: `tbpin_20260827`, `tbrep_20260827`
  - 통과 건수: [13, 13]
  - 런마다 달라진 과제 6건
  - 통과 과제 집합이 런마다 다르다 (6건). 건수가 같아도 다른 과제를 맞힌 것이면 같은 측정이 아니다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `9eb0c62bdbcd226d` — **DIVERGED**
  - 런 2개: `tbpin_20260827`, `tbrep_20260827`
  - 통과 건수: [15, 15]
  - 런마다 달라진 과제 4건
  - 통과 과제 집합이 런마다 다르다 (4건). 건수가 같아도 다른 과제를 맞힌 것이면 같은 측정이 아니다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `b190004379363859` — **IDENTICAL** — 통과 과제 집합이 완전히 같다
  - 런 4개: `20260823_021442`, `tb_std_20260819`, `tb_std_rep2_20260820`, `tb_std_rep3_20260823`
  - 통과 건수: [19, 19, 19, 19]
- `openai/google_gemma_4_26b_a4b_it` · protocol `b6b79e8d5fc0d9f7` — **UNVERIFIED**
  - 런 1개: `tbair_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `b6b79e8d5fc0d9f7` — **UNVERIFIED**
  - 런 1개: `tbair_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/google_gemma_4_26b_a4b_it` · protocol `b73e96808b553a41` — **UNVERIFIED**
  - 런 1개: `tbstd1_20261002`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `b73e96808b553a41` — **UNVERIFIED**
  - 런 1개: `tbtel_b_20260828`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `openai/google_diffusiongemma_26B_A4B_it` · protocol `c19af26e7c6a92bf` — **DIVERGED**
  - 런 3개: `20260830_222550_r1`, `20260830_222550_r2`, `20260907_001502_r3`
  - 통과 건수: [11, 8, 9]
  - 런마다 달라진 과제 10건
  - 통과 과제 집합이 런마다 다르다 (10건). 건수가 같아도 다른 과제를 맞힌 것이면 같은 측정이 아니다
- `openai/google_gemma_4_26b_a4b_it` · protocol `c19af26e7c6a92bf` — **DIVERGED**
  - 런 3개: `20260830_095733_r1`, `20260830_095733_r2`, `20260927_230250_r3`
  - 통과 건수: [25, 25, 16]
  - 런마다 달라진 과제 13건
  - 통과 과제 집합이 런마다 다르다 (13건). 건수가 같아도 다른 과제를 맞힌 것이면 같은 측정이 아니다
- `openai/nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16` · protocol `c19af26e7c6a92bf` — **DIVERGED**
  - 런 3개: `20260830_095747_r1`, `20260830_123159_r1`, `20260830_123159_r2`
  - 통과 건수: [4, 4, 2]
  - 런마다 달라진 과제 8건
  - 통과 과제 집합이 런마다 다르다 (8건). 건수가 같아도 다른 과제를 맞힌 것이면 같은 측정이 아니다
- `openai/qwen_qwen3.8_27B_FP8` · protocol `c19af26e7c6a92bf` — **IDENTICAL** — 통과 과제 집합이 완전히 같다
  - 런 3개: `20261003_171917_r1`, `20261003_171917_r2`, `20261003_171917_r3`
  - 통과 건수: [0, 0, 0]
- `openai/qwen_qwen3.8_27b` · protocol `c19af26e7c6a92bf` — **IDENTICAL** — 통과 과제 집합이 완전히 같다
  - 런 3개: `20260927_232851_r1`, `20260927_232851_r2`, `20260927_232851_r3`
  - 통과 건수: [0, 0, 0]
- `openai/google_gemma_4_26b_a4b_it` · protocol `d4160331c47bd2b2` — **UNSUPPORTED**
  - 런 1개: `tbk4_20261002`
  - 다중 시행 산출물이다 — 통과 집합 비교는 Pass^k 를 대신할 수 없다

## 클레임 등급

**1회 실행 숫자는 순위표에 올리지 않는다.** 저장·표시·역사 인용은 되지만 우열 주장의 근거는 아니다. 반복 3회 이상이어야 반복성을 관측했다고 말한다.

- `openai/google_gemma_4_26b_a4b_it` · protocol `0d0c0f1a90bb63de` — `snapshot` (k=1) · 반복 1회 — 반복성을 관측하려면 3회가 필요하다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `0d0c0f1a90bb63de` — `snapshot` (k=1) · 반복 1회 — 반복성을 관측하려면 3회가 필요하다
- `openai/google_gemma_4_26b_a4b_it` · protocol `2892aac47f8f9475` — `snapshot` (k=1) · 반복 1회 — 반복성을 관측하려면 3회가 필요하다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `2892aac47f8f9475` — `snapshot` (k=1) · 반복 1회 — 반복성을 관측하려면 3회가 필요하다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `6fa5aa02fd58fc7e` — `snapshot` (k=1) · 반복 1회 — 반복성을 관측하려면 3회가 필요하다
- `openai/google_gemma_4_26b_a4b_it` · protocol `9eb0c62bdbcd226d` — `snapshot` (k=2) · 반복 2회 — 반복성을 관측하려면 3회가 필요하다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `9eb0c62bdbcd226d` — `snapshot` (k=2) · 반복 2회 — 반복성을 관측하려면 3회가 필요하다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `b190004379363859` — `repeatability_observed` (k=4) · 다수결 19/40 · 건수범위 [19, 19] · 뒤집힘 0건 · 불안정 예산 19–19
- `openai/google_gemma_4_26b_a4b_it` · protocol `b6b79e8d5fc0d9f7` — `snapshot` (k=1) · 반복 1회 — 반복성을 관측하려면 3회가 필요하다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `b6b79e8d5fc0d9f7` — `snapshot` (k=1) · 반복 1회 — 반복성을 관측하려면 3회가 필요하다
- `openai/google_gemma_4_26b_a4b_it` · protocol `b73e96808b553a41` — `snapshot` (k=1) · 반복 1회 — 반복성을 관측하려면 3회가 필요하다
- `openai/qwen_qwen3.5_35b_a3b_fp8` · protocol `b73e96808b553a41` — `not_measured` (k=1) · 런들이 공통으로 채점한 항목이 없다 — 반복 횟수와 무관하게 이 코호트는 측정된 것이 없다
- `openai/google_diffusiongemma_26B_A4B_it` · protocol `c19af26e7c6a92bf` — `repeatability_observed` (k=3) · 다수결 8/40 · 건수범위 [8, 11] · 뒤집힘 10건 · 불안정 예산 -2–18
- `openai/google_gemma_4_26b_a4b_it` · protocol `c19af26e7c6a92bf` — `repeatability_observed` (k=3) · 다수결 25/40 · 건수범위 [16, 25] · 뒤집힘 13건 · 불안정 예산 12–38
- `openai/nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16` · protocol `c19af26e7c6a92bf` — `repeatability_observed` (k=3) · 다수결 2/40 · 건수범위 [2, 4] · 뒤집힘 8건 · 불안정 예산 -6–10
- `openai/qwen_qwen3.8_27B_FP8` · protocol `c19af26e7c6a92bf` — `not_measured` (k=3) · 런들이 공통으로 채점한 항목이 없다 — 반복 횟수와 무관하게 이 코호트는 측정된 것이 없다
- `openai/qwen_qwen3.8_27b` · protocol `c19af26e7c6a92bf` — `not_measured` (k=3) · 런들이 공통으로 채점한 항목이 없다 — 반복 횟수와 무관하게 이 코호트는 측정된 것이 없다
- `google_diffusiongemma_26B_A4B_it` / `tbstd4_20261011` — **제외**: 다중 시행 산출물이다 — 통과 집합 비교는 Pass^k 를 대신할 수 없다
- `google_gemma_4_26b_a4b_it` / `tbk4_20261002` — **제외**: 다중 시행 산출물이다 — 통과 집합 비교는 Pass^k 를 대신할 수 없다
- `google_gemma_4_26b_a4b_it` / `tbstd4_20261003` — **제외**: 다중 시행 산출물이다 — 통과 집합 비교는 Pass^k 를 대신할 수 없다
- `nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16` / `tbstd4_20261010` — **제외**: 다중 시행 산출물이다 — 통과 집합 비교는 Pass^k 를 대신할 수 없다
- `qwen_qwen3.8_27B_FP8` / `20261003_171917_tbstd4` — **제외**: 다중 시행 산출물이다 — 통과 집합 비교는 Pass^k 를 대신할 수 없다
- `qwen_qwen3.8_27b` / `tbstd4_20261003` — **제외**: 다중 시행 산출물이다 — 통과 집합 비교는 Pass^k 를 대신할 수 없다

### 발행 가능한 우열 주장

- `openai/google_gemma_4_26b_a4b_it` vs `openai/qwen_qwen3.5_35b_a3b_fp8` — **발행 불가**: 사용자 프로토콜 고정 기록이 없다
- `openai/google_gemma_4_26b_a4b_it` vs `openai/qwen_qwen3.5_35b_a3b_fp8` — **발행 불가**: 사용자 프로토콜 고정 기록이 없다
- `openai/google_gemma_4_26b_a4b_it` vs `openai/qwen_qwen3.5_35b_a3b_fp8` — **발행 불가**: left 가 `snapshot` 이다 — 반복 2회로는 비교 근거가 없다
- `openai/google_gemma_4_26b_a4b_it` vs `openai/qwen_qwen3.5_35b_a3b_fp8` — **발행 불가**: 사용자 프로토콜 고정 기록이 없다
- `openai/google_gemma_4_26b_a4b_it` vs `openai/qwen_qwen3.5_35b_a3b_fp8` — **발행 불가**: left 가 `snapshot` 이다 — 반복 1회로는 비교 근거가 없다
- `openai/google_diffusiongemma_26B_A4B_it` vs `openai/google_gemma_4_26b_a4b_it` — **발행 불가**: 불안정 예산이 겹친다 (-2–18 vs 12–38) — 차이가 관측된 흔들림으로 설명된다
- `openai/google_diffusiongemma_26B_A4B_it` vs `openai/nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16` — **발행 불가**: 불안정 예산이 겹친다 (-2–18 vs -6–10) — 차이가 관측된 흔들림으로 설명된다
- `openai/google_diffusiongemma_26B_A4B_it` vs `openai/qwen_qwen3.8_27B_FP8` — **발행 불가**: right 가 `not_measured` 이다 — 반복 3회로는 비교 근거가 없다
- `openai/google_diffusiongemma_26B_A4B_it` vs `openai/qwen_qwen3.8_27b` — **발행 불가**: right 가 `not_measured` 이다 — 반복 3회로는 비교 근거가 없다
- `openai/google_gemma_4_26b_a4b_it` 우세 — 불안정 예산이 겹치지 않는다 (12–38 vs -6–10). 통계적 유의성이 아니라, 이 데이터로 반박되지 않는다는 뜻이다
- `openai/google_gemma_4_26b_a4b_it` vs `openai/qwen_qwen3.8_27B_FP8` — **발행 불가**: right 가 `not_measured` 이다 — 반복 3회로는 비교 근거가 없다
- `openai/google_gemma_4_26b_a4b_it` vs `openai/qwen_qwen3.8_27b` — **발행 불가**: right 가 `not_measured` 이다 — 반복 3회로는 비교 근거가 없다
- `openai/nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16` vs `openai/qwen_qwen3.8_27B_FP8` — **발행 불가**: right 가 `not_measured` 이다 — 반복 3회로는 비교 근거가 없다
- `openai/nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16` vs `openai/qwen_qwen3.8_27b` — **발행 불가**: right 가 `not_measured` 이다 — 반복 3회로는 비교 근거가 없다
- `openai/qwen_qwen3.8_27B_FP8` vs `openai/qwen_qwen3.8_27b` — **발행 불가**: left 가 `not_measured` 이다 — 반복 3회로는 비교 근거가 없다

> 가설검정이 아니다. 신뢰구간도 p-value 도 아니다. **관측된 불안정으로 설명이 끝나는 우열 주장을 거절하는 규칙**일 뿐이며, 거절되지 않았다고 '유의하다'는 뜻이 아니고 거절됐다고 '두 모델이 같다'는 뜻도 아니다.
