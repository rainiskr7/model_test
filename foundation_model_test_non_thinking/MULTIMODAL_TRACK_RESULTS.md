# multimodal 트랙 결과

이 파일은 `report_multimodal_tracks.py`가 `_derived` sidecar에서 생성한다. 손으로 고치지 말 것.

판단 기준: [`MULTIMODAL_PUBLISH_CONTRACT.md`](MULTIMODAL_PUBLISH_CONTRACT.md).

발행 가능 source **142** / 발행 불가 source **66** / 게이트 기록 없음 **0**.

읽는 법:

- 서로 다른 벤치와 축을 합산하거나 평균하지 않는다.
- 결과는 반올림된 점수만 보지 말고 분자/분모를 함께 본다.
- PROVISIONAL은 판정기 기준이며 인간 검증 전이다.
- 거부된 런의 숫자는 원본에 존재하더라도 인용하지 않는다.

## 모델 정체성 경고

다음 서빙명은 `configs/model_identity.json`에 미매핑이다. 추측해서 합치지 않고 자기 이름을 canonical id로 사용한다.

- `Qwen3.5_122B_A10B_GPTQ_Int4`
- `google_diffusiongemma_26B_A4B_it`
- `nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16`
- `qwen3.5_27b`
- `qwen_qwen3.5_27b_fp8`
- `qwen_qwen3.5_35b_a3b`
- `qwen_qwen3.5_35b_a3b_fp8`
- `qwen_qwen3.6_27b`
- `qwen_qwen3.6_27b_fp8`
- `qwen_qwen3.6_35b_a3b_fp8`
- `qwen_qwen3.8_27B_FP8`
- `qwen_qwen3.8_27b`

## 헤드라인 — 벤치마크별 overall

### KRETA — default, 2577문항 — protocol `163ee4cd4504`

전체 protocol fingerprint: `sha256:163ee4cd4504e498b92b629ee195dcc50e1f652c88a23818ef86065113d28f87`

| 모델 | 결과 (대표 런) | 반복 평균 (범위) | 무답률 | 상태 |
|---|---|---|---:|---|
| gemma_4_26b_a4b_it | 2323/2577 = 90.14% | 90.08% (89.76–90.34%) · k=3 | 2.3% | NATIVE |
| qwen_qwen3.8_27b | 2311/2577 = 89.68% | 89.78% (89.68–89.87%) · k=3 | 4.2% | NATIVE |
| qwen_qwen3.8_27B_FP8 | 2308/2577 = 89.56% | 89.74% (89.37–90.30%) · k=3 | 4.5% | NATIVE |
| qwen_qwen3.6_35b_a3b_fp8 | 2290/2577 = 88.86% | — (k=1) | 4.4% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | 2233/2577 = 86.65% | — (k=1) | 3.1% | LEGACY_REVALIDATED |

> 각주: 기록된 repo commit이 런마다 다름(문항 집합은 동일): `3104bffac9fe`, `9219dbd6b1f7`, `c273302ade2c`.

> 각주: `gemma_4_26b_a4b_it` — 상류 parser와 76행 불일치(우리 무답 60, 다른 선택지 16) — 독립 재채점 점수임.
> 각주: `qwen_qwen3.5_35b_a3b_fp8` — 상류 parser와 91행 불일치(우리 무답 80, 다른 선택지 11) — 독립 재채점 점수임.
> 각주: `qwen_qwen3.6_35b_a3b_fp8` — 상류 parser와 132행 불일치(우리 무답 113, 다른 선택지 19) — 독립 재채점 점수임.
> 각주: `qwen_qwen3.8_27B_FP8` — 상류 parser와 124행 불일치(우리 무답 115, 다른 선택지 9) — 독립 재채점 점수임.
> 각주: `qwen_qwen3.8_27b` — 상류 parser와 114행 불일치(우리 무답 109, 다른 선택지 5) — 독립 재채점 점수임.

> 재현성: `qwen_qwen3.5_35b_a3b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.6_35b_a3b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `gemma_4_26b_a4b_it` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 90.08% (89.76–90.34%) · 관측 범위 2313–2328 (fraction) · 산포 15 / 정책 허용 26 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260830_095733_r1`  2313/2577 = 89.76% (기준)
>   `20260830_095733_r2`  2328/2577 = 90.34%
>   `20260927_230250_r3`  2323/2577 = 90.14% (대표)
> 재현성: `qwen_qwen3.8_27B_FP8` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 89.74% (89.37–90.30%) · 관측 범위 2303–2327 (fraction) · 산포 24 / 정책 허용 26 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20261003_171917_r1`  2303/2577 = 89.37% (기준)
>   `20261003_171917_r2`  2327/2577 = 90.30%
>   `20261003_171917_r3`  2308/2577 = 89.56% (대표)
> 재현성: `qwen_qwen3.8_27b` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 89.78% (89.68–89.87%) · 관측 범위 2311–2316 (fraction) · 산포 5 / 정책 허용 26 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260927_232851_r1`  2316/2577 = 89.87% (기준)
>   `20260927_232851_r2`  2314/2577 = 89.79%
>   `20260927_232851_r3`  2311/2577 = 89.68% (대표)
> 모델 간 우열 — `KRETA` (fraction)
>   `gemma_4_26b_a4b_it` vs `qwen_qwen3.8_27B_FP8` — **발행 불가**: 불안정 예산이 겹친다 (2313.0–2328.0 vs 2303.0–2327.0) — 차이가 관측된 흔들림으로 설명된다
>   `gemma_4_26b_a4b_it` vs `qwen_qwen3.8_27b` — **발행 불가**: 불안정 예산이 겹친다 (2313.0–2328.0 vs 2311.0–2316.0) — 차이가 관측된 흔들림으로 설명된다
>   `qwen_qwen3.8_27B_FP8` vs `qwen_qwen3.8_27b` — **발행 불가**: 불안정 예산이 겹친다 (2303.0–2327.0 vs 2311.0–2316.0) — 차이가 관측된 흔들림으로 설명된다
>   **주의:** 집계 축이라 항목 벡터가 없다. 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없으므로 이 판정은 exact-match 축보다 약한 근거다. 가설검정도 신뢰구간도 아니다.

### KRETA — default, 2577문항 — protocol `17225b3254b1`

전체 protocol fingerprint: `sha256:17225b3254b1d8278061c003ee9810bbcb1117f9c57d52f51b9bb1575b6b84ed`

| 모델 | 결과 (대표 런) | 반복 평균 (범위) | 무답률 | 상태 |
|---|---|---|---:|---|
| google_diffusiongemma_26B_A4B_it | 2156/2577 = 83.66% | 83.73% (83.66–83.82%) · k=3 | 1.0% | NATIVE |

> 각주: `google_diffusiongemma_26B_A4B_it` — 상류 parser와 27행 불일치(우리 무답 26, 다른 선택지 1) — 독립 재채점 점수임.

> 재현성: `google_diffusiongemma_26B_A4B_it` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 83.73% (83.66–83.82%) · 관측 범위 2156–2160 (fraction) · 산포 4 / 정책 허용 26 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260830_222550_r2`  2160/2577 = 83.82% (기준)
>   `20260907_001502_r3`  2157/2577 = 83.70%
>   `20260830_222550_r1`  2156/2577 = 83.66% (대표)

### KRETA — direct, 2577문항 — protocol `8097cc67ee15`

전체 protocol fingerprint: `sha256:8097cc67ee15fcb067ad01034e481ca525e36400a8bb9fefa727476e80639c48`

| 모델 | 결과 (대표 런) | 반복 평균 (범위) | 무답률 | 상태 |
|---|---|---|---:|---|
| gemma_4_31b_it | 2030/2577 = 78.77% | — (k=1) | 0.1% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | 1860/2577 = 72.18% | — (k=1) | 0.4% | LEGACY_REVALIDATED |
| qwen3.5_27b | 1839/2577 = 71.36% | — (k=1) | 1.1% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | 1821/2577 = 70.66% | — (k=1) | 1.1% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | 1819/2577 = 70.59% | — (k=1) | 0.3% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | 1769/2577 = 68.65% | — (k=1) | 1.3% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | 1731/2577 = 67.17% | — (k=1) | 0.0% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | 1725/2577 = 66.94% | — (k=1) | 2.8% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | 1494/2577 = 57.97% | — (k=1) | 21.1% | LEGACY_REVALIDATED |

> 각주: 기록된 repo commit이 런마다 다름(문항 집합은 동일): `736779d467f6`, `7c0155d6bfa1`, `aad99f4759b9`, `c273302ade2c`, `ffe124392283`.

> 각주: `Qwen3.5_122B_A10B_GPTQ_Int4` — 상류 parser와 551행 불일치(우리 무답 545, 다른 선택지 6) — 독립 재채점 점수임.
> **주의:** `Qwen3.5_122B_A10B_GPTQ_Int4` — 무답 545건 (21.1%). 응답이 지시된 형식을 벗어나 절단됨. 점수를 능력 차이로만 해석하지 말 것.
> 각주: `gemma_4_26b_a4b_it` — 상류 parser와 11행 불일치(우리 무답 10, 다른 선택지 1) — 독립 재채점 점수임.
> 각주: `gemma_4_31b_it` — 상류 parser와 5행 불일치(우리 무답 3, 다른 선택지 2) — 독립 재채점 점수임.
> 각주: `qwen3.5_27b` — 상류 parser와 28행 불일치(우리 무답 28, 다른 선택지 0) — 독립 재채점 점수임.
> 각주: `qwen3.6-35b-a3b` — 상류 parser와 1행 불일치(우리 무답 1, 다른 선택지 0) — 독립 재채점 점수임.
> 각주: `qwen_qwen3.5_27b_fp8` — 상류 parser와 30행 불일치(우리 무답 28, 다른 선택지 2) — 독립 재채점 점수임.
> 각주: `qwen_qwen3.5_35b_a3b` — 상류 parser와 47행 불일치(우리 무답 34, 다른 선택지 13) — 독립 재채점 점수임.
> 각주: `qwen_qwen3.6_27b` — 상류 parser와 73행 불일치(우리 무답 72, 다른 선택지 1) — 독립 재채점 점수임.
> 각주: `qwen_qwen3.6_27b_fp8` — 상류 parser와 14행 불일치(우리 무답 8, 다른 선택지 6) — 독립 재채점 점수임.

> 재현성: `Qwen3.5_122B_A10B_GPTQ_Int4` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `gemma_4_26b_a4b_it` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `gemma_4_31b_it` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen3.5_27b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen3.6-35b-a3b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.5_27b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.5_35b_a3b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.6_27b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.6_27b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)

### K-MMBench — full, 4329문항 — protocol `54e6a6c9ad08`

전체 protocol fingerprint: `sha256:54e6a6c9ad08ec4b7ead056833d60bf04373ba27df8ce42286dea9a908c30a2f`

| 모델 | 결과 (대표 런) | 반복 평균 (범위) | 상태 |
|---|---|---|---|
| gemma_4_26b_a4b_it | 3758/4329 = 86.81% | — (k=1) | LEGACY_REVALIDATED |

> 중복 접기: `gemma_4_26b_a4b_it` — `results/gemma_4_26b_a4b_it/20260503_122218/vision/multimodal/k_mmbench` 유지; 동일 artifact role/SHA-256·측정 payload 복사본 `results/gemma_4_26b_a4b_it.bad/20260503_122218/vision/multimodal/k_mmbench` 접음.
> 재현성: `gemma_4_26b_a4b_it` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)

### K-MMBench — full, 4329문항 — protocol `664089f27792`

전체 protocol fingerprint: `sha256:664089f27792bdf5a50df380e0bd0e91aad47e56c61390657d7712000c0d2341`

| 모델 | 결과 (대표 런) | 반복 평균 (범위) | 상태 |
|---|---|---|---|
| google_diffusiongemma_26B_A4B_it | 3745/4329 = 86.51% | 86.44% (86.26–86.56%) · k=3 | NATIVE |

> 재현성: `google_diffusiongemma_26B_A4B_it` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 86.44% (86.26–86.56%) · 관측 범위 3734–3747 (fraction) · 산포 13 / 정책 허용 44 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260830_222550_r1`  3747/4329 = 86.56% (기준)
>   `20260830_222550_r2`  3734/4329 = 86.26%
>   `20260907_001502_r3`  3745/4329 = 86.51% (대표)
>   **주의:** `20260830_222550_r1` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260830_222550_r2` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260907_001502_r3` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.

### K-MMBench — full, 4329문항 — protocol `aa74d55ecd55`

전체 protocol fingerprint: `sha256:aa74d55ecd55e431459c1f5f572195c5b4e516d0a9462dd128f0cd12e4064a30`

| 모델 | 결과 (대표 런) | 반복 평균 (범위) | 상태 |
|---|---|---|---|
| qwen3.6-35b-a3b | 3907/4329 = 90.25% | — (k=1) | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | 3772/4329 = 87.13% | 87.19% (87.13–87.25%) · k=4 | NATIVE |
| qwen3.5_27b | 3701/4329 = 85.49% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | 3688/4329 = 85.19% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.8_27B_FP8 | 3661/4329 = 84.57% | 84.57% (84.55–84.59%) · k=3 | NATIVE |
| qwen_qwen3.8_27b | 3660/4329 = 84.55% | 84.54% (84.50–84.57%) · k=3 | NATIVE |
| qwen_qwen3.6_27b | 3610/4329 = 83.39% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | 3608/4329 = 83.34% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | 3584/4329 = 82.79% | — (k=1) | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | 3489/4329 = 80.60% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | 3425/4329 = 79.12% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | 3395/4329 = 78.42% | — (k=1) | LEGACY_REVALIDATED |

> 중복 접기: `gemma_4_26b_a4b_it` — `results/gemma_4_26b_a4b_it/20260505_124246/vision/multimodal/k_mmbench` 유지; 동일 artifact role/SHA-256·측정 payload 복사본 `results/google_gemma_4_26B_A4B_it/20260505_124246/vision/multimodal/k_mmbench`, `results/gemma_4_26b_a4b_it.bad/20260505_124246/vision/multimodal/k_mmbench`, `results/google_gemma_4_26B_A4B_it/20260505_124246.bad/vision/multimodal/k_mmbench` 접음.
> 재현성: `Qwen3.5_122B_A10B_GPTQ_Int4` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen3.5_27b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen3.6-35b-a3b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.5_27b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.5_35b_a3b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.5_35b_a3b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.6_27b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.6_27b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.6_35b_a3b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `gemma_4_26b_a4b_it` — 이 코호트에 런 4개. `repeatability_observed` · 4회 평균 87.19% (87.13–87.25%) · 관측 범위 3772–3777 (fraction) · 산포 5 / 정책 허용 44 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260505_124246`  3776/4329 = 87.23% (기준)
>   `20260830_095733_r1`  3773/4329 = 87.16%
>   `20260830_095733_r2`  3777/4329 = 87.25%
>   `20260927_230250_r3`  3772/4329 = 87.13% (대표)
>   **주의:** `20260505_124246` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260830_095733_r1` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260830_095733_r2` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260927_230250_r3` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
> 재현성: `qwen_qwen3.8_27B_FP8` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 84.57% (84.55–84.59%) · 관측 범위 3660–3662 (fraction) · 산포 2 / 정책 허용 44 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20261003_171917_r1`  3662/4329 = 84.59% (기준)
>   `20261003_171917_r2`  3660/4329 = 84.55%
>   `20261003_171917_r3`  3661/4329 = 84.57% (대표)
>   **주의:** `20261003_171917_r1` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20261003_171917_r2` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20261003_171917_r3` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
> 재현성: `qwen_qwen3.8_27b` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 84.54% (84.50–84.57%) · 관측 범위 3658–3661 (fraction) · 산포 3 / 정책 허용 44 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260927_232851_r1`  3658/4329 = 84.50% (기준)
>   `20260927_232851_r2`  3661/4329 = 84.57%
>   `20260927_232851_r3`  3660/4329 = 84.55% (대표)
>   **주의:** `20260927_232851_r1` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260927_232851_r2` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260927_232851_r3` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
> 모델 간 우열 — `K-MMBench` (fraction)
>   `gemma_4_26b_a4b_it` 우세 — 불안정 예산이 겹치지 않는다 (3772.0–3777.0 vs 3660.0–3662.0). 통계적 유의성이 아니라, 이 데이터로 반박되지 않는다는 뜻이다
>   `gemma_4_26b_a4b_it` 우세 — 불안정 예산이 겹치지 않는다 (3772.0–3777.0 vs 3658.0–3661.0). 통계적 유의성이 아니라, 이 데이터로 반박되지 않는다는 뜻이다
>   `qwen_qwen3.8_27B_FP8` vs `qwen_qwen3.8_27b` — **발행 불가**: 불안정 예산이 겹친다 (3660.0–3662.0 vs 3658.0–3661.0) — 차이가 관측된 흔들림으로 설명된다
>   **주의:** 집계 축이라 항목 벡터가 없다. 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없으므로 이 판정은 exact-match 축보다 약한 근거다. 가설검정도 신뢰구간도 아니다.

### K-DTCBench — full, 240문항 — protocol `0d96dcdd622f`

전체 protocol fingerprint: `sha256:0d96dcdd622f6aad9fbf3619c30e03be87f0be3af65202af7d8d299cfa5124e6`

| 모델 | 결과 (대표 런) | 반복 평균 (범위) | 상태 |
|---|---|---|---|
| gemma_4_26b_a4b_it | 205/240 = 85.42% | 85.00% (84.58–85.42%) · k=2 | LEGACY_REVALIDATED |

> 중복 접기: `gemma_4_26b_a4b_it` — `results/gemma_4_26b_a4b_it/20260503_120151/vision/multimodal/k_dtcbench` 유지; 동일 artifact role/SHA-256·측정 payload 복사본 `results/gemma_4_26b_a4b_it.bad/20260503_120151/vision/multimodal/k_dtcbench` 접음.
> 중복 접기: `gemma_4_26b_a4b_it` — `results/gemma_4_26b_a4b_it/20260503_120309/vision/multimodal/k_dtcbench` 유지; 동일 artifact role/SHA-256·측정 payload 복사본 `results/gemma_4_26b_a4b_it.bad/20260503_120309/vision/multimodal/k_dtcbench` 접음.
> 재현성: `gemma_4_26b_a4b_it` — 이 코호트에 런 2개. `snapshot` · 2회 평균 85.00% (84.58–85.42%) · 관측 범위 203–205 (fraction) · 산포 2 / 정책 허용 3 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260503_120151`  203/240 = 84.58% (기준)
>   `20260503_120309`  205/240 = 85.42% (대표)
>   **주의:** `20260503_120151` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260503_120309` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.

### K-DTCBench — full, 240문항 — protocol `a3fa0d693a36`

전체 protocol fingerprint: `sha256:a3fa0d693a36a437873ca73a1aa224e76ecd220dc0c4fe1c88973ee13b6e8d6b`

| 모델 | 결과 (대표 런) | 반복 평균 (범위) | 상태 |
|---|---|---|---|
| qwen3.6-35b-a3b | 214/240 = 89.17% | — (k=1) | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | 204/240 = 85.00% | 85.75% (85.00–86.25%) · k=5 | NATIVE |
| qwen3.5_27b | 196/240 = 81.67% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | 196/240 = 81.67% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | 195/240 = 81.25% | — (k=1) | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | 185/240 = 77.08% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | 182/240 = 75.83% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.8_27B_FP8 | 180/240 = 75.00% | 75.00% (75.00–75.00%) · k=3 | NATIVE |
| qwen_qwen3.8_27b | 178/240 = 74.17% | 73.89% (73.33–74.17%) · k=3 | NATIVE |
| qwen_qwen3.5_35b_a3b | 173/240 = 72.08% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | 172/240 = 71.67% | — (k=1) | LEGACY_REVALIDATED |

> 중복 접기: `gemma_4_26b_a4b_it` — `results/gemma_4_26b_a4b_it/20260505_124246/vision/multimodal/k_dtcbench` 유지; 동일 artifact role/SHA-256·측정 payload 복사본 `results/google_gemma_4_26B_A4B_it/20260505_124246/vision/multimodal/k_dtcbench`, `results/gemma_4_26b_a4b_it.bad/20260505_124246/vision/multimodal/k_dtcbench`, `results/google_gemma_4_26B_A4B_it/20260505_124246.bad/vision/multimodal/k_dtcbench` 접음.
> 재현성: `Qwen3.5_122B_A10B_GPTQ_Int4` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen3.5_27b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen3.6-35b-a3b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.5_27b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.5_35b_a3b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.5_35b_a3b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.6_27b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.6_35b_a3b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `gemma_4_26b_a4b_it` — 이 코호트에 런 5개. `repeatability_observed` · 5회 평균 85.75% (85.00–86.25%) · 관측 범위 204–207 (fraction) · 산포 3 / 정책 허용 3 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260505_124246`  207/240 = 86.25% (기준)
>   `v2b_20260824`  206/240 = 85.83%
>   `20260830_095733_r1`  206/240 = 85.83%
>   `20260830_095733_r2`  206/240 = 85.83%
>   `20260927_230250_r3`  204/240 = 85.00% (대표)
>   **주의:** `20260505_124246` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `v2b_20260824` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260830_095733_r1` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260830_095733_r2` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260927_230250_r3` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
> 재현성: `qwen_qwen3.8_27B_FP8` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 75.00% (75.00–75.00%) · 관측 범위 180–180 (fraction) · 산포 0 / 정책 허용 3 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20261003_171917_r1`  180/240 = 75.00% (기준)
>   `20261003_171917_r2`  180/240 = 75.00%
>   `20261003_171917_r3`  180/240 = 75.00% (대표)
>   **주의:** `20261003_171917_r1` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20261003_171917_r2` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20261003_171917_r3` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
> 재현성: `qwen_qwen3.8_27b` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 73.89% (73.33–74.17%) · 관측 범위 176–178 (fraction) · 산포 2 / 정책 허용 3 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260927_232851_r1`  176/240 = 73.33% (기준)
>   `20260927_232851_r2`  178/240 = 74.17%
>   `20260927_232851_r3`  178/240 = 74.17% (대표)
>   **주의:** `20260927_232851_r1` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260927_232851_r2` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260927_232851_r3` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
> 모델 간 우열 — `K-DTCBench` (fraction)
>   `gemma_4_26b_a4b_it` 우세 — 불안정 예산이 겹치지 않는다 (204.0–207.0 vs 180.0–180.0). 통계적 유의성이 아니라, 이 데이터로 반박되지 않는다는 뜻이다
>   `gemma_4_26b_a4b_it` 우세 — 불안정 예산이 겹치지 않는다 (204.0–207.0 vs 176.0–178.0). 통계적 유의성이 아니라, 이 데이터로 반박되지 않는다는 뜻이다
>   `qwen_qwen3.8_27B_FP8` 우세 — 불안정 예산이 겹치지 않는다 (180.0–180.0 vs 176.0–178.0). 통계적 유의성이 아니라, 이 데이터로 반박되지 않는다는 뜻이다
>   **주의:** 집계 축이라 항목 벡터가 없다. 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없으므로 이 판정은 exact-match 축보다 약한 근거다. 가설검정도 신뢰구간도 아니다.

### K-DTCBench — full, 240문항 — protocol `a8e50b0990bb`

전체 protocol fingerprint: `sha256:a8e50b0990bb322cad1ca860efd99f48293c3d86f215dd77258108a563f0ebc9`

| 모델 | 결과 (대표 런) | 반복 평균 (범위) | 상태 |
|---|---|---|---|
| google_diffusiongemma_26B_A4B_it | 190/240 = 79.17% | 78.89% (77.50–80.00%) · k=3 | NATIVE |

> 재현성: `google_diffusiongemma_26B_A4B_it` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 78.89% (77.50–80.00%) · 관측 범위 186–192 (fraction) · 산포 6 / 정책 허용 3 — **흔들림 큼 — 정책 허용 초과. 점수가 낮다는 뜻이 아니라 단일 런 수치를 믿기 어렵다는 뜻**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260830_222550_r1`  186/240 = 77.50% (기준)
>   `20260830_222550_r2`  192/240 = 80.00%
>   `20260907_001502_r3`  190/240 = 79.17% (대표)
>   **주의:** `20260830_222550_r1` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260830_222550_r2` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.
>   **주의:** `20260907_001502_r3` 의 `split` 는 산출물에 기록된 값이 아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다.

### MTVQA-KR — full, 558문항 — protocol `356cc6eae2af`

전체 protocol fingerprint: `sha256:356cc6eae2af10c9107886531b679f05cf23e79431df2970ae7662dfbdded969`

| 모델 | 결과 (대표 런) | 반복 평균 (범위) | 상태 |
|---|---|---|---|
| google_diffusiongemma_26B_A4B_it | 221/558 = 39.61% | 39.73% (38.89–40.68%) · k=3 | NATIVE |

> 재현성: `google_diffusiongemma_26B_A4B_it` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 39.73% (38.89–40.68%) · 관측 범위 217–227 (fraction) · 산포 10 / 정책 허용 6 — **흔들림 큼 — 정책 허용 초과. 점수가 낮다는 뜻이 아니라 단일 런 수치를 믿기 어렵다는 뜻**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260830_222550_r1`  227/558 = 40.68% (기준)
>   `20260830_222550_r2`  217/558 = 38.89%
>   `20260907_001502_r3`  221/558 = 39.61% (대표)

### MTVQA-KR — full, 558문항 — protocol `5db43694610d`

전체 protocol fingerprint: `sha256:5db43694610d33e25662146cd959377ac1f1a67d9dfdfb1cdae26ab070ac866d`

| 모델 | 결과 (대표 런) | 반복 평균 (범위) | 상태 |
|---|---|---|---|
| qwen_qwen3.8_27B_FP8 | 295/558 = 52.87% | 52.75% (52.69–52.87%) · k=3 | NATIVE |
| qwen_qwen3.8_27b | 294/558 = 52.69% | 52.87% (52.69–53.05%) · k=3 | NATIVE |
| qwen_qwen3.5_35b_a3b | 292/558 = 52.33% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | 292/558 = 52.33% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | 291/558 = 52.15% | — (k=1) | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | 290/558 = 51.97% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | 290/558 = 51.97% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | 288/558 = 51.61% | — (k=1) | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | 287/558 = 51.43% | — (k=1) | LEGACY_REVALIDATED |
| qwen3.5_27b | 286/558 = 51.25% | — (k=1) | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | 273/558 = 48.92% | — (k=1) | LEGACY_REVALIDATED |
| gemma_4_31b_it | 268/558 = 48.03% | 48.21% (48.03–48.39%) · k=2 | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | 259/558 = 46.42% | 46.09% (45.70–46.42%) · k=5 | NATIVE |

> 중복 접기: `gemma_4_26b_a4b_it` — `results/gemma_4_26b_a4b_it/20260505_124246/vision/multimodal/mtvqa_kr` 유지; 동일 artifact role/SHA-256·측정 payload 복사본 `results/google_gemma_4_26B_A4B_it/20260505_124246/vision/multimodal/mtvqa_kr`, `results/gemma_4_26b_a4b_it.bad/20260505_124246/vision/multimodal/mtvqa_kr`, `results/google_gemma_4_26B_A4B_it/20260505_124246.bad/vision/multimodal/mtvqa_kr` 접음.
> 중복 접기: `gemma_4_31b_it` — `results/gemma_4_31b_it/20260505_130752/vision/multimodal/mtvqa_kr` 유지; 동일 artifact role/SHA-256·측정 payload 복사본 `results/google_gemma_4_31B_it/20260505_130752/vision/multimodal/mtvqa_kr` 접음.
> 재현성: `Qwen3.5_122B_A10B_GPTQ_Int4` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen3.5_27b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen3.6-35b-a3b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.5_27b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.5_35b_a3b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.5_35b_a3b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.6_27b` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.6_27b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `qwen_qwen3.6_35b_a3b_fp8` — 이 코호트에 런 1개. 비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)
> 재현성: `gemma_4_26b_a4b_it` — 이 코호트에 런 5개. `repeatability_observed` · 5회 평균 46.09% (45.70–46.42%) · 관측 범위 255–259 (fraction) · 산포 4 / 정책 허용 6 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260505_124246`  258/558 = 46.24% (기준)
>   `v2b_20260824`  255/558 = 45.70%
>   `20260830_095733_r1`  257/558 = 46.06%
>   `20260830_095733_r2`  257/558 = 46.06%
>   `20260927_230250_r3`  259/558 = 46.42% (대표)
> 재현성: `gemma_4_31b_it` — 이 코호트에 런 2개. `snapshot` · 2회 평균 48.21% (48.03–48.39%) · 관측 범위 268–270 (fraction) · 산포 2 / 정책 허용 6 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260505_130752`  270/558 = 48.39% (기준)
>   `20260525_152204`  268/558 = 48.03% (대표)
> 재현성: `qwen_qwen3.8_27B_FP8` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 52.75% (52.69–52.87%) · 관측 범위 294–295 (fraction) · 산포 1 / 정책 허용 6 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20261003_171917_r1`  294/558 = 52.69% (기준)
>   `20261003_171917_r2`  294/558 = 52.69%
>   `20261003_171917_r3`  295/558 = 52.87% (대표)
> 재현성: `qwen_qwen3.8_27b` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 52.87% (52.69–53.05%) · 관측 범위 294–296 (fraction) · 산포 2 / 정책 허용 6 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260927_232851_r1`  296/558 = 53.05% (기준)
>   `20260927_232851_r2`  295/558 = 52.87%
>   `20260927_232851_r3`  294/558 = 52.69% (대표)
> 모델 간 우열 — `MTVQA-KR` (fraction)
>   `gemma_4_26b_a4b_it` vs `gemma_4_31b_it` — **발행 불가**: right 가 `snapshot` 이다 — 반복 2회로는 비교 근거가 없다
>   `qwen_qwen3.8_27B_FP8` 우세 — 불안정 예산이 겹치지 않는다 (255.0–259.0 vs 294.0–295.0). 통계적 유의성이 아니라, 이 데이터로 반박되지 않는다는 뜻이다
>   `qwen_qwen3.8_27b` 우세 — 불안정 예산이 겹치지 않는다 (255.0–259.0 vs 294.0–296.0). 통계적 유의성이 아니라, 이 데이터로 반박되지 않는다는 뜻이다
>   `gemma_4_31b_it` vs `qwen_qwen3.8_27B_FP8` — **발행 불가**: left 가 `snapshot` 이다 — 반복 2회로는 비교 근거가 없다
>   `gemma_4_31b_it` vs `qwen_qwen3.8_27b` — **발행 불가**: left 가 `snapshot` 이다 — 반복 2회로는 비교 근거가 없다
>   `qwen_qwen3.8_27B_FP8` vs `qwen_qwen3.8_27b` — **발행 불가**: 불안정 예산이 겹친다 (294.0–295.0 vs 294.0–296.0) — 차이가 관측된 흔들림으로 설명된다
>   **주의:** 집계 축이라 항목 벡터가 없다. 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없으므로 이 판정은 exact-match 축보다 약한 근거다. 가설검정도 신뢰구간도 아니다.

### KOFFVQA-judge — api_judge_end_to_end, 275문항 — protocol `e9b7bebe099f`

전체 protocol fingerprint: `sha256:e9b7bebe099f58615ff95622fcfb7f829bed4f102a9444d4d5bbc9cb36b1e162`

| 모델 | 결과 (대표 런) | 반복 평균 (범위) | 상태 |
|---|---|---|---|
| gemma_4_26b_a4b_it | 8.67/10 | 8.62/10 (8.57–8.67) · k=3 | PROVISIONAL — 판정기 기준, 인간 검증 없음 |
| google_diffusiongemma_26B_A4B_it | 8.56/10 | 8.42/10 (8.33–8.56) · k=3 | PROVISIONAL — 판정기 기준, 인간 검증 없음 |
| qwen_qwen3.8_27B_FP8 | 8.46/10 | 8.50/10 (8.46–8.53) · k=3 | PROVISIONAL — 판정기 기준, 인간 검증 없음 |
| qwen_qwen3.8_27b | 8.20/10 | 8.31/10 (8.20–8.39) · k=3 | PROVISIONAL — 판정기 기준, 인간 검증 없음 |

> 재현성: `gemma_4_26b_a4b_it` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 8.62/10 (8.57–8.67) · 관측 범위 8.56727–8.66545 (score/10) · 산포 0.0981818 / 정책 허용 0.1 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260830_095733_r1`  8.57/10 (기준)
>   `20260830_095733_r2`  8.64/10
>   `20260927_230250_r3`  8.67/10 (대표)
> 재현성: `google_diffusiongemma_26B_A4B_it` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 8.42/10 (8.33–8.56) · 관측 범위 8.33091–8.55636 (score/10) · 산포 0.225455 / 정책 허용 0.1 — **흔들림 큼 — 정책 허용 초과. 점수가 낮다는 뜻이 아니라 단일 런 수치를 믿기 어렵다는 뜻**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260830_222550_r1`  8.33/10 (기준)
>   `20260830_222550_r2`  8.36/10
>   `20260907_001502_r3`  8.56/10 (대표)
> 재현성: `qwen_qwen3.8_27B_FP8` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 8.50/10 (8.46–8.53) · 관측 범위 8.46182–8.53091 (score/10) · 산포 0.0690909 / 정책 허용 0.1 — **흔들림 허용 범위 안**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20261003_171917_r1`  8.53/10 (기준)
>   `20261003_171917_r2`  8.50/10
>   `20261003_171917_r3`  8.46/10 (대표)
> 재현성: `qwen_qwen3.8_27b` — 이 코호트에 런 3개. `repeatability_observed` · 3회 평균 8.31/10 (8.20–8.39) · 관측 범위 8.19636–8.39273 (score/10) · 산포 0.196364 / 정책 허용 0.1 — **흔들림 큼 — 정책 허용 초과. 점수가 낮다는 뜻이 아니라 단일 런 수치를 믿기 어렵다는 뜻**
>   **주의:** 항목 벡터가 없어 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없다. 이 관측 범위는 실제 불안정의 **하한**이며, exact-match 축보다 약한 근거다.
>   `20260927_232851_r1`  8.39/10 (기준)
>   `20260927_232851_r2`  8.34/10
>   `20260927_232851_r3`  8.20/10 (대표)
> 모델 간 우열 — `KOFFVQA-judge` (score/10)
>   `gemma_4_26b_a4b_it` 우세 — 불안정 예산이 겹치지 않는다 (8.567272727272726–8.665454545454546 vs 8.33090909090909–8.556363636363637). 통계적 유의성이 아니라, 이 데이터로 반박되지 않는다는 뜻이다
>   `gemma_4_26b_a4b_it` 우세 — 불안정 예산이 겹치지 않는다 (8.567272727272726–8.665454545454546 vs 8.461818181818181–8.530909090909091). 통계적 유의성이 아니라, 이 데이터로 반박되지 않는다는 뜻이다
>   `gemma_4_26b_a4b_it` 우세 — 불안정 예산이 겹치지 않는다 (8.567272727272726–8.665454545454546 vs 8.196363636363637–8.392727272727273). 통계적 유의성이 아니라, 이 데이터로 반박되지 않는다는 뜻이다
>   `google_diffusiongemma_26B_A4B_it` vs `qwen_qwen3.8_27B_FP8` — **발행 불가**: 불안정 예산이 겹친다 (8.33090909090909–8.556363636363637 vs 8.461818181818181–8.530909090909091) — 차이가 관측된 흔들림으로 설명된다
>   `google_diffusiongemma_26B_A4B_it` vs `qwen_qwen3.8_27b` — **발행 불가**: 불안정 예산이 겹친다 (8.33090909090909–8.556363636363637 vs 8.196363636363637–8.392727272727273) — 차이가 관측된 흔들림으로 설명된다
>   `qwen_qwen3.8_27B_FP8` 우세 — 불안정 예산이 겹치지 않는다 (8.461818181818181–8.530909090909091 vs 8.196363636363637–8.392727272727273). 통계적 유의성이 아니라, 이 데이터로 반박되지 않는다는 뜻이다
>   **주의:** 집계 축이라 항목 벡터가 없다. 값이 같아도 서로 다른 문항을 맞혔는지 알 수 없으므로 이 판정은 exact-match 축보다 약한 근거다. 가설검정도 신뢰구간도 아니다.

## 상태 요약

| 상태 | source 수 |
|---|---:|
| NATIVE | 59 |
| LEGACY_REVALIDATED | 83 |
| REJECTED | 40 |
| INSUFFICIENT_PROVENANCE | 0 |
| UNSCORED | 26 |

## 세부 축

카테고리 및 System1/2 등 세부 축은 벤치별로 접어 두었다.

<details>
<summary>KRETA — default — protocol `163ee4cd4504`</summary>

전체 protocol fingerprint: `sha256:163ee4cd4504e498b92b629ee195dcc50e1f652c88a23818ef86065113d28f87`

| 모델 | 축 | 결과 | 상태 |
|---|---|---|---|
| gemma_4_26b_a4b_it | domain:Arts and Humanities | 82/83 = 98.80% | NATIVE |
| gemma_4_26b_a4b_it | domain:CSAT History | 58/60 = 96.67% | NATIVE |
| gemma_4_26b_a4b_it | domain:CSAT Science | 301/478 = 62.97% | NATIVE |
| gemma_4_26b_a4b_it | domain:Economics and Finance | 100/104 = 96.15% | NATIVE |
| gemma_4_26b_a4b_it | domain:Education and Academia | 210/215 = 97.67% | NATIVE |
| gemma_4_26b_a4b_it | domain:Entertainment and Media | 159/168 = 94.64% | NATIVE |
| gemma_4_26b_a4b_it | domain:Hospitality and Food Service | 258/264 = 97.73% | NATIVE |
| gemma_4_26b_a4b_it | domain:Marketing and Advertising | 145/145 = 100.00% | NATIVE |
| gemma_4_26b_a4b_it | domain:Medical and Healthcare | 85/90 = 94.44% | NATIVE |
| gemma_4_26b_a4b_it | domain:Personal and Lifestyle | 198/204 = 97.06% | NATIVE |
| gemma_4_26b_a4b_it | domain:Public and Administration | 239/245 = 97.55% | NATIVE |
| gemma_4_26b_a4b_it | domain:Retail and Commerce | 143/154 = 92.86% | NATIVE |
| gemma_4_26b_a4b_it | domain:Science and Technology | 87/92 = 94.57% | NATIVE |
| gemma_4_26b_a4b_it | domain:Transportation and Logistics | 153/167 = 91.62% | NATIVE |
| gemma_4_26b_a4b_it | domain:Travel and Tourism | 105/108 = 97.22% | NATIVE |
| gemma_4_26b_a4b_it | system:System1 | 1393/1426 = 97.69% | NATIVE |
| gemma_4_26b_a4b_it | system:System2 | 930/1151 = 80.80% | NATIVE |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Arts and Humanities | 80/83 = 96.39% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:CSAT History | 42/60 = 70.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:CSAT Science | 242/478 = 50.63% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Economics and Finance | 102/104 = 98.08% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Education and Academia | 205/215 = 95.35% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Entertainment and Media | 156/168 = 92.86% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Hospitality and Food Service | 253/264 = 95.83% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Marketing and Advertising | 139/145 = 95.86% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Medical and Healthcare | 83/90 = 92.22% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Personal and Lifestyle | 199/204 = 97.55% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Public and Administration | 240/245 = 97.96% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Retail and Commerce | 145/154 = 94.16% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Science and Technology | 87/92 = 94.57% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Transportation and Logistics | 153/167 = 91.62% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Travel and Tourism | 107/108 = 99.07% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | system:System1 | 1377/1426 = 96.56% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | system:System2 | 856/1151 = 74.37% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Arts and Humanities | 82/83 = 98.80% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:CSAT History | 45/60 = 75.00% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:CSAT Science | 286/478 = 59.83% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Economics and Finance | 101/104 = 97.12% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Education and Academia | 206/215 = 95.81% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Entertainment and Media | 159/168 = 94.64% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Hospitality and Food Service | 253/264 = 95.83% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Marketing and Advertising | 143/145 = 98.62% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Medical and Healthcare | 84/90 = 93.33% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Personal and Lifestyle | 201/204 = 98.53% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Public and Administration | 237/245 = 96.73% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Retail and Commerce | 145/154 = 94.16% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Science and Technology | 88/92 = 95.65% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Transportation and Logistics | 152/167 = 91.02% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Travel and Tourism | 108/108 = 100.00% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | system:System1 | 1385/1426 = 97.12% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | system:System2 | 905/1151 = 78.63% | LEGACY_REVALIDATED |
| qwen_qwen3.8_27B_FP8 | domain:Arts and Humanities | 79/83 = 95.18% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:CSAT History | 43/60 = 71.67% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:CSAT Science | 298/478 = 62.34% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:Economics and Finance | 103/104 = 99.04% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:Education and Academia | 209/215 = 97.21% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:Entertainment and Media | 159/168 = 94.64% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:Hospitality and Food Service | 253/264 = 95.83% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:Marketing and Advertising | 143/145 = 98.62% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:Medical and Healthcare | 89/90 = 98.89% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:Personal and Lifestyle | 199/204 = 97.55% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:Public and Administration | 237/245 = 96.73% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:Retail and Commerce | 148/154 = 96.10% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:Science and Technology | 85/92 = 92.39% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:Transportation and Logistics | 155/167 = 92.81% | NATIVE |
| qwen_qwen3.8_27B_FP8 | domain:Travel and Tourism | 108/108 = 100.00% | NATIVE |
| qwen_qwen3.8_27B_FP8 | system:System1 | 1390/1426 = 97.48% | NATIVE |
| qwen_qwen3.8_27B_FP8 | system:System2 | 918/1151 = 79.76% | NATIVE |
| qwen_qwen3.8_27b | domain:Arts and Humanities | 80/83 = 96.39% | NATIVE |
| qwen_qwen3.8_27b | domain:CSAT History | 43/60 = 71.67% | NATIVE |
| qwen_qwen3.8_27b | domain:CSAT Science | 298/478 = 62.34% | NATIVE |
| qwen_qwen3.8_27b | domain:Economics and Finance | 101/104 = 97.12% | NATIVE |
| qwen_qwen3.8_27b | domain:Education and Academia | 206/215 = 95.81% | NATIVE |
| qwen_qwen3.8_27b | domain:Entertainment and Media | 160/168 = 95.24% | NATIVE |
| qwen_qwen3.8_27b | domain:Hospitality and Food Service | 260/264 = 98.48% | NATIVE |
| qwen_qwen3.8_27b | domain:Marketing and Advertising | 143/145 = 98.62% | NATIVE |
| qwen_qwen3.8_27b | domain:Medical and Healthcare | 87/90 = 96.67% | NATIVE |
| qwen_qwen3.8_27b | domain:Personal and Lifestyle | 200/204 = 98.04% | NATIVE |
| qwen_qwen3.8_27b | domain:Public and Administration | 239/245 = 97.55% | NATIVE |
| qwen_qwen3.8_27b | domain:Retail and Commerce | 146/154 = 94.81% | NATIVE |
| qwen_qwen3.8_27b | domain:Science and Technology | 86/92 = 93.48% | NATIVE |
| qwen_qwen3.8_27b | domain:Transportation and Logistics | 154/167 = 92.22% | NATIVE |
| qwen_qwen3.8_27b | domain:Travel and Tourism | 108/108 = 100.00% | NATIVE |
| qwen_qwen3.8_27b | system:System1 | 1384/1426 = 97.05% | NATIVE |
| qwen_qwen3.8_27b | system:System2 | 927/1151 = 80.54% | NATIVE |

</details>

<details>
<summary>KRETA — default — protocol `17225b3254b1`</summary>

전체 protocol fingerprint: `sha256:17225b3254b1d8278061c003ee9810bbcb1117f9c57d52f51b9bb1575b6b84ed`

| 모델 | 축 | 결과 | 상태 |
|---|---|---|---|
| google_diffusiongemma_26B_A4B_it | domain:Arts and Humanities | 82/83 = 98.80% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:CSAT History | 49/60 = 81.67% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:CSAT Science | 212/478 = 44.35% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:Economics and Finance | 96/104 = 92.31% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:Education and Academia | 204/215 = 94.88% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:Entertainment and Media | 152/168 = 90.48% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:Hospitality and Food Service | 246/264 = 93.18% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:Marketing and Advertising | 142/145 = 97.93% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:Medical and Healthcare | 82/90 = 91.11% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:Personal and Lifestyle | 194/204 = 95.10% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:Public and Administration | 231/245 = 94.29% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:Retail and Commerce | 138/154 = 89.61% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:Science and Technology | 84/92 = 91.30% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:Transportation and Logistics | 142/167 = 85.03% | NATIVE |
| google_diffusiongemma_26B_A4B_it | domain:Travel and Tourism | 102/108 = 94.44% | NATIVE |
| google_diffusiongemma_26B_A4B_it | system:System1 | 1359/1426 = 95.30% | NATIVE |
| google_diffusiongemma_26B_A4B_it | system:System2 | 797/1151 = 69.24% | NATIVE |

</details>

<details>
<summary>KRETA — direct — protocol `8097cc67ee15`</summary>

전체 protocol fingerprint: `sha256:8097cc67ee15fcb067ad01034e481ca525e36400a8bb9fefa727476e80639c48`

| 모델 | 축 | 결과 | 상태 |
|---|---|---|---|
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Arts and Humanities | 69/83 = 83.13% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:CSAT History | 24/60 = 40.00% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:CSAT Science | 39/478 = 8.16% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Economics and Finance | 64/104 = 61.54% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Education and Academia | 150/215 = 69.77% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Entertainment and Media | 126/168 = 75.00% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Hospitality and Food Service | 176/264 = 66.67% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Marketing and Advertising | 111/145 = 76.55% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Medical and Healthcare | 48/90 = 53.33% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Personal and Lifestyle | 158/204 = 77.45% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Public and Administration | 163/245 = 66.53% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Retail and Commerce | 110/154 = 71.43% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Science and Technology | 62/92 = 67.39% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Transportation and Logistics | 118/167 = 70.66% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Travel and Tourism | 76/108 = 70.37% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | system:System1 | 1142/1426 = 80.08% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | system:System2 | 352/1151 = 30.58% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:Arts and Humanities | 77/83 = 92.77% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:CSAT History | 39/60 = 65.00% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:CSAT Science | 174/478 = 36.40% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:Economics and Finance | 87/104 = 83.65% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:Education and Academia | 185/215 = 86.05% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:Entertainment and Media | 140/168 = 83.33% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:Hospitality and Food Service | 198/264 = 75.00% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:Marketing and Advertising | 128/145 = 88.28% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:Medical and Healthcare | 70/90 = 77.78% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:Personal and Lifestyle | 172/204 = 84.31% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:Public and Administration | 196/245 = 80.00% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:Retail and Commerce | 119/154 = 77.27% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:Science and Technology | 72/92 = 78.26% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:Transportation and Logistics | 116/167 = 69.46% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | domain:Travel and Tourism | 87/108 = 80.56% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | system:System1 | 1282/1426 = 89.90% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | system:System2 | 578/1151 = 50.22% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:Arts and Humanities | 78/83 = 93.98% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:CSAT History | 46/60 = 76.67% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:CSAT Science | 204/478 = 42.68% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:Economics and Finance | 89/104 = 85.58% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:Education and Academia | 197/215 = 91.63% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:Entertainment and Media | 146/168 = 86.90% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:Hospitality and Food Service | 223/264 = 84.47% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:Marketing and Advertising | 138/145 = 95.17% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:Medical and Healthcare | 74/90 = 82.22% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:Personal and Lifestyle | 184/204 = 90.20% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:Public and Administration | 215/245 = 87.76% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:Retail and Commerce | 129/154 = 83.77% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:Science and Technology | 80/92 = 86.96% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:Transportation and Logistics | 137/167 = 82.04% | LEGACY_REVALIDATED |
| gemma_4_31b_it | domain:Travel and Tourism | 90/108 = 83.33% | LEGACY_REVALIDATED |
| gemma_4_31b_it | system:System1 | 1366/1426 = 95.79% | LEGACY_REVALIDATED |
| gemma_4_31b_it | system:System2 | 664/1151 = 57.69% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Arts and Humanities | 74/83 = 89.16% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:CSAT History | 33/60 = 55.00% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:CSAT Science | 150/478 = 31.38% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Economics and Finance | 81/104 = 77.88% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Education and Academia | 182/215 = 84.65% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Entertainment and Media | 138/168 = 82.14% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Hospitality and Food Service | 196/264 = 74.24% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Marketing and Advertising | 125/145 = 86.21% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Medical and Healthcare | 69/90 = 76.67% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Personal and Lifestyle | 182/204 = 89.22% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Public and Administration | 191/245 = 77.96% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Retail and Commerce | 118/154 = 76.62% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Science and Technology | 69/92 = 75.00% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Transportation and Logistics | 134/167 = 80.24% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Travel and Tourism | 97/108 = 89.81% | LEGACY_REVALIDATED |
| qwen3.5_27b | system:System1 | 1318/1426 = 92.43% | LEGACY_REVALIDATED |
| qwen3.5_27b | system:System2 | 521/1151 = 45.26% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Arts and Humanities | 67/83 = 80.72% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:CSAT History | 27/60 = 45.00% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:CSAT Science | 131/478 = 27.41% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Economics and Finance | 77/104 = 74.04% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Education and Academia | 178/215 = 82.79% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Entertainment and Media | 124/168 = 73.81% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Hospitality and Food Service | 188/264 = 71.21% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Marketing and Advertising | 121/145 = 83.45% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Medical and Healthcare | 69/90 = 76.67% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Personal and Lifestyle | 164/204 = 80.39% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Public and Administration | 195/245 = 79.59% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Retail and Commerce | 112/154 = 72.73% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Science and Technology | 66/92 = 71.74% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Transportation and Logistics | 126/167 = 75.45% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Travel and Tourism | 86/108 = 79.63% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | system:System1 | 1245/1426 = 87.31% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | system:System2 | 486/1151 = 42.22% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Arts and Humanities | 75/83 = 90.36% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:CSAT History | 33/60 = 55.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:CSAT Science | 141/478 = 29.50% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Economics and Finance | 81/104 = 77.88% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Education and Academia | 178/215 = 82.79% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Entertainment and Media | 142/168 = 84.52% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Hospitality and Food Service | 196/264 = 74.24% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Marketing and Advertising | 128/145 = 88.28% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Medical and Healthcare | 63/90 = 70.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Personal and Lifestyle | 181/204 = 88.73% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Public and Administration | 192/245 = 78.37% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Retail and Commerce | 123/154 = 79.87% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Science and Technology | 69/92 = 75.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Transportation and Logistics | 126/167 = 75.45% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Travel and Tourism | 93/108 = 86.11% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | system:System1 | 1313/1426 = 92.08% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | system:System2 | 508/1151 = 44.14% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Arts and Humanities | 73/83 = 87.95% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:CSAT History | 29/60 = 48.33% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:CSAT Science | 127/478 = 26.57% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Economics and Finance | 82/104 = 78.85% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Education and Academia | 178/215 = 82.79% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Entertainment and Media | 124/168 = 73.81% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Hospitality and Food Service | 210/264 = 79.55% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Marketing and Advertising | 121/145 = 83.45% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Medical and Healthcare | 66/90 = 73.33% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Personal and Lifestyle | 172/204 = 84.31% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Public and Administration | 186/245 = 75.92% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Retail and Commerce | 118/154 = 76.62% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Science and Technology | 67/92 = 72.83% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Transportation and Logistics | 125/167 = 74.85% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Travel and Tourism | 91/108 = 84.26% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | system:System1 | 1263/1426 = 88.57% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | system:System2 | 506/1151 = 43.96% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Arts and Humanities | 70/83 = 84.34% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:CSAT History | 27/60 = 45.00% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:CSAT Science | 128/478 = 26.78% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Economics and Finance | 75/104 = 72.12% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Education and Academia | 177/215 = 82.33% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Entertainment and Media | 137/168 = 81.55% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Hospitality and Food Service | 183/264 = 69.32% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Marketing and Advertising | 115/145 = 79.31% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Medical and Healthcare | 68/90 = 75.56% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Personal and Lifestyle | 169/204 = 82.84% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Public and Administration | 182/245 = 74.29% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Retail and Commerce | 120/154 = 77.92% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Science and Technology | 67/92 = 72.83% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Transportation and Logistics | 122/167 = 73.05% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Travel and Tourism | 85/108 = 78.70% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | system:System1 | 1254/1426 = 87.94% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | system:System2 | 471/1151 = 40.92% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Arts and Humanities | 75/83 = 90.36% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:CSAT History | 30/60 = 50.00% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:CSAT Science | 140/478 = 29.29% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Economics and Finance | 79/104 = 75.96% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Education and Academia | 178/215 = 82.79% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Entertainment and Media | 142/168 = 84.52% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Hospitality and Food Service | 202/264 = 76.52% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Marketing and Advertising | 122/145 = 84.14% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Medical and Healthcare | 69/90 = 76.67% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Personal and Lifestyle | 175/204 = 85.78% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Public and Administration | 197/245 = 80.41% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Retail and Commerce | 119/154 = 77.27% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Science and Technology | 70/92 = 76.09% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Transportation and Logistics | 128/167 = 76.65% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Travel and Tourism | 93/108 = 86.11% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | system:System1 | 1283/1426 = 89.97% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | system:System2 | 536/1151 = 46.57% | LEGACY_REVALIDATED |

</details>

<details>
<summary>K-MMBench — full — protocol `54e6a6c9ad08`</summary>

전체 protocol fingerprint: `sha256:54e6a6c9ad08ec4b7ead056833d60bf04373ba27df8ce42286dea9a908c30a2f`

| 모델 | 축 | 결과 | 상태 |
|---|---|---|---|
| gemma_4_26b_a4b_it | category:action_recognition | 201/215 = 93.49% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:attribute_comparison | 112/141 = 79.43% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:attribute_recognition | 244/264 = 92.42% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:celebrity_recognition | 381/396 = 96.21% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:function_reasoning | 277/304 = 91.12% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:future_prediction | 100/130 = 76.92% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:identity_reasoning | 175/176 = 99.43% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:image_emotion | 174/200 = 87.00% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:image_quality | 93/150 = 62.00% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:image_scene | 394/407 = 96.81% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:image_style | 198/212 = 93.40% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:image_topic | 137/140 = 97.86% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:nature_relation | 165/179 = 92.18% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:object_localization | 210/315 = 66.67% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:ocr | 150/156 = 96.15% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:physical_property_reasoning | 160/219 = 73.06% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:physical_relation | 65/94 = 69.15% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:social_relation | 132/172 = 76.74% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:spatial_relationship | 135/177 = 76.27% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:structuralized_imagetext_understanding | 255/282 = 90.43% | LEGACY_REVALIDATED |

</details>

<details>
<summary>K-MMBench — full — protocol `664089f27792`</summary>

전체 protocol fingerprint: `sha256:664089f27792bdf5a50df380e0bd0e91aad47e56c61390657d7712000c0d2341`

| 모델 | 축 | 결과 | 상태 |
|---|---|---|---|
| google_diffusiongemma_26B_A4B_it | category:action_recognition | 206/215 = 95.81% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:attribute_comparison | 94/141 = 66.67% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:attribute_recognition | 232/264 = 87.88% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:celebrity_recognition | 381/396 = 96.21% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:function_reasoning | 278/304 = 91.45% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:future_prediction | 102/130 = 78.46% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:identity_reasoning | 175/176 = 99.43% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:image_emotion | 174/200 = 87.00% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:image_quality | 81/150 = 54.00% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:image_scene | 396/407 = 97.30% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:image_style | 198/212 = 93.40% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:image_topic | 137/140 = 97.86% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:nature_relation | 165/179 = 92.18% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:object_localization | 219/315 = 69.52% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:ocr | 153/156 = 98.08% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:physical_property_reasoning | 169/219 = 77.17% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:physical_relation | 60/94 = 63.83% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:social_relation | 139/172 = 80.81% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:spatial_relationship | 134/177 = 75.71% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:structuralized_imagetext_understanding | 252/282 = 89.36% | NATIVE |

</details>

<details>
<summary>K-MMBench — full — protocol `aa74d55ecd55`</summary>

전체 protocol fingerprint: `sha256:aa74d55ecd55e431459c1f5f572195c5b4e516d0a9462dd128f0cd12e4064a30`

| 모델 | 축 | 결과 | 상태 |
|---|---|---|---|
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:action_recognition | 199/215 = 92.56% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:attribute_comparison | 104/141 = 73.76% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:attribute_recognition | 210/264 = 79.55% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:celebrity_recognition | 379/396 = 95.71% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:function_reasoning | 275/304 = 90.46% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:future_prediction | 87/130 = 66.92% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:identity_reasoning | 163/176 = 92.61% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:image_emotion | 155/200 = 77.50% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:image_quality | 66/150 = 44.00% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:image_scene | 375/407 = 92.14% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:image_style | 193/212 = 91.04% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:image_topic | 129/140 = 92.14% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:nature_relation | 140/179 = 78.21% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:object_localization | 174/315 = 55.24% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:ocr | 143/156 = 91.67% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:physical_property_reasoning | 147/219 = 67.12% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:physical_relation | 65/94 = 69.15% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:social_relation | 125/172 = 72.67% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:spatial_relationship | 129/177 = 72.88% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:structuralized_imagetext_understanding | 231/282 = 81.91% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:action_recognition | 203/215 = 94.42% | NATIVE |
| gemma_4_26b_a4b_it | category:attribute_comparison | 107/141 = 75.89% | NATIVE |
| gemma_4_26b_a4b_it | category:attribute_recognition | 242/264 = 91.67% | NATIVE |
| gemma_4_26b_a4b_it | category:celebrity_recognition | 384/396 = 96.97% | NATIVE |
| gemma_4_26b_a4b_it | category:function_reasoning | 278/304 = 91.45% | NATIVE |
| gemma_4_26b_a4b_it | category:future_prediction | 101/130 = 77.69% | NATIVE |
| gemma_4_26b_a4b_it | category:identity_reasoning | 175/176 = 99.43% | NATIVE |
| gemma_4_26b_a4b_it | category:image_emotion | 175/200 = 87.50% | NATIVE |
| gemma_4_26b_a4b_it | category:image_quality | 89/150 = 59.33% | NATIVE |
| gemma_4_26b_a4b_it | category:image_scene | 395/407 = 97.05% | NATIVE |
| gemma_4_26b_a4b_it | category:image_style | 199/212 = 93.87% | NATIVE |
| gemma_4_26b_a4b_it | category:image_topic | 137/140 = 97.86% | NATIVE |
| gemma_4_26b_a4b_it | category:nature_relation | 168/179 = 93.85% | NATIVE |
| gemma_4_26b_a4b_it | category:object_localization | 209/315 = 66.35% | NATIVE |
| gemma_4_26b_a4b_it | category:ocr | 150/156 = 96.15% | NATIVE |
| gemma_4_26b_a4b_it | category:physical_property_reasoning | 165/219 = 75.34% | NATIVE |
| gemma_4_26b_a4b_it | category:physical_relation | 66/94 = 70.21% | NATIVE |
| gemma_4_26b_a4b_it | category:social_relation | 139/172 = 80.81% | NATIVE |
| gemma_4_26b_a4b_it | category:spatial_relationship | 135/177 = 76.27% | NATIVE |
| gemma_4_26b_a4b_it | category:structuralized_imagetext_understanding | 255/282 = 90.43% | NATIVE |
| qwen3.5_27b | category:action_recognition | 209/215 = 97.21% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:attribute_comparison | 98/141 = 69.50% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:attribute_recognition | 223/264 = 84.47% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:celebrity_recognition | 373/396 = 94.19% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:function_reasoning | 278/304 = 91.45% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:future_prediction | 83/130 = 63.85% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:identity_reasoning | 176/176 = 100.00% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:image_emotion | 173/200 = 86.50% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:image_quality | 83/150 = 55.33% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:image_scene | 392/407 = 96.31% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:image_style | 198/212 = 93.40% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:image_topic | 134/140 = 95.71% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:nature_relation | 151/179 = 84.36% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:object_localization | 208/315 = 66.03% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:ocr | 151/156 = 96.79% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:physical_property_reasoning | 169/219 = 77.17% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:physical_relation | 80/94 = 85.11% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:social_relation | 136/172 = 79.07% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:spatial_relationship | 137/177 = 77.40% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:structuralized_imagetext_understanding | 249/282 = 88.30% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:action_recognition | 207/215 = 96.28% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:attribute_comparison | 124/141 = 87.94% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:attribute_recognition | 249/264 = 94.32% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:celebrity_recognition | 391/396 = 98.74% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:function_reasoning | 281/304 = 92.43% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:future_prediction | 85/130 = 65.38% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:identity_reasoning | 176/176 = 100.00% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:image_emotion | 164/200 = 82.00% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:image_quality | 95/150 = 63.33% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:image_scene | 399/407 = 98.03% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:image_style | 198/212 = 93.40% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:image_topic | 135/140 = 96.43% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:nature_relation | 169/179 = 94.41% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:object_localization | 256/315 = 81.27% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:ocr | 147/156 = 94.23% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:physical_property_reasoning | 182/219 = 83.11% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:physical_relation | 77/94 = 81.91% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:social_relation | 158/172 = 91.86% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:spatial_relationship | 161/177 = 90.96% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:structuralized_imagetext_understanding | 253/282 = 89.72% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:action_recognition | 206/215 = 95.81% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:attribute_comparison | 98/141 = 69.50% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:attribute_recognition | 226/264 = 85.61% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:celebrity_recognition | 372/396 = 93.94% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:function_reasoning | 277/304 = 91.12% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:future_prediction | 85/130 = 65.38% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:identity_reasoning | 176/176 = 100.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:image_emotion | 168/200 = 84.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:image_quality | 83/150 = 55.33% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:image_scene | 392/407 = 96.31% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:image_style | 200/212 = 94.34% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:image_topic | 134/140 = 95.71% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:nature_relation | 151/179 = 84.36% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:object_localization | 204/315 = 64.76% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:ocr | 151/156 = 96.79% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:physical_property_reasoning | 169/219 = 77.17% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:physical_relation | 79/94 = 84.04% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:social_relation | 133/172 = 77.33% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:spatial_relationship | 134/177 = 75.71% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:structuralized_imagetext_understanding | 250/282 = 88.65% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:action_recognition | 190/215 = 88.37% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:attribute_comparison | 96/141 = 68.09% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:attribute_recognition | 220/264 = 83.33% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:celebrity_recognition | 365/396 = 92.17% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:function_reasoning | 264/304 = 86.84% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:future_prediction | 69/130 = 53.08% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:identity_reasoning | 168/176 = 95.45% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:image_emotion | 152/200 = 76.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:image_quality | 67/150 = 44.67% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:image_scene | 374/407 = 91.89% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:image_style | 176/212 = 83.02% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:image_topic | 123/140 = 87.86% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:nature_relation | 138/179 = 77.09% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:object_localization | 176/315 = 55.87% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:ocr | 139/156 = 89.10% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:physical_property_reasoning | 161/219 = 73.52% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:physical_relation | 66/94 = 70.21% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:social_relation | 112/172 = 65.12% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:spatial_relationship | 121/177 = 68.36% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:structuralized_imagetext_understanding | 218/282 = 77.30% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:action_recognition | 191/215 = 88.84% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:attribute_comparison | 97/141 = 68.79% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:attribute_recognition | 216/264 = 81.82% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:celebrity_recognition | 363/396 = 91.67% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:function_reasoning | 264/304 = 86.84% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:future_prediction | 67/130 = 51.54% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:identity_reasoning | 165/176 = 93.75% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:image_emotion | 155/200 = 77.50% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:image_quality | 66/150 = 44.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:image_scene | 378/407 = 92.87% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:image_style | 179/212 = 84.43% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:image_topic | 123/140 = 87.86% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:nature_relation | 139/179 = 77.65% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:object_localization | 175/315 = 55.56% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:ocr | 145/156 = 92.95% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:physical_property_reasoning | 159/219 = 72.60% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:physical_relation | 69/94 = 73.40% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:social_relation | 121/172 = 70.35% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:spatial_relationship | 126/177 = 71.19% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:structuralized_imagetext_understanding | 227/282 = 80.50% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:action_recognition | 198/215 = 92.09% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:attribute_comparison | 104/141 = 73.76% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:attribute_recognition | 222/264 = 84.09% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:celebrity_recognition | 369/396 = 93.18% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:function_reasoning | 269/304 = 88.49% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:future_prediction | 84/130 = 64.62% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:identity_reasoning | 174/176 = 98.86% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:image_emotion | 164/200 = 82.00% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:image_quality | 80/150 = 53.33% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:image_scene | 390/407 = 95.82% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:image_style | 196/212 = 92.45% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:image_topic | 130/140 = 92.86% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:nature_relation | 161/179 = 89.94% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:object_localization | 174/315 = 55.24% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:ocr | 147/156 = 94.23% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:physical_property_reasoning | 161/219 = 73.52% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:physical_relation | 72/94 = 76.60% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:social_relation | 135/172 = 78.49% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:spatial_relationship | 131/177 = 74.01% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:structuralized_imagetext_understanding | 249/282 = 88.30% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:action_recognition | 196/215 = 91.16% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:attribute_comparison | 108/141 = 76.60% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:attribute_recognition | 223/264 = 84.47% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:celebrity_recognition | 365/396 = 92.17% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:function_reasoning | 273/304 = 89.80% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:future_prediction | 88/130 = 67.69% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:identity_reasoning | 174/176 = 98.86% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:image_emotion | 164/200 = 82.00% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:image_quality | 83/150 = 55.33% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:image_scene | 385/407 = 94.59% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:image_style | 194/212 = 91.51% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:image_topic | 128/140 = 91.43% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:nature_relation | 159/179 = 88.83% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:object_localization | 171/315 = 54.29% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:ocr | 149/156 = 95.51% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:physical_property_reasoning | 166/219 = 75.80% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:physical_relation | 70/94 = 74.47% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:social_relation | 133/172 = 77.33% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:spatial_relationship | 131/177 = 74.01% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | category:structuralized_imagetext_understanding | 248/282 = 87.94% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:action_recognition | 193/215 = 89.77% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:attribute_comparison | 99/141 = 70.21% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:attribute_recognition | 222/264 = 84.09% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:celebrity_recognition | 379/396 = 95.71% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:function_reasoning | 265/304 = 87.17% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:future_prediction | 68/130 = 52.31% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:identity_reasoning | 175/176 = 99.43% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:image_emotion | 156/200 = 78.00% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:image_quality | 75/150 = 50.00% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:image_scene | 388/407 = 95.33% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:image_style | 189/212 = 89.15% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:image_topic | 128/140 = 91.43% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:nature_relation | 158/179 = 88.27% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:object_localization | 199/315 = 63.17% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:ocr | 146/156 = 93.59% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:physical_property_reasoning | 160/219 = 73.06% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:physical_relation | 72/94 = 76.60% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:social_relation | 144/172 = 83.72% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:spatial_relationship | 134/177 = 75.71% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:structuralized_imagetext_understanding | 234/282 = 82.98% | LEGACY_REVALIDATED |
| qwen_qwen3.8_27B_FP8 | category:action_recognition | 209/215 = 97.21% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:attribute_comparison | 103/141 = 73.05% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:attribute_recognition | 228/264 = 86.36% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:celebrity_recognition | 373/396 = 94.19% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:function_reasoning | 285/304 = 93.75% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:future_prediction | 76/130 = 58.46% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:identity_reasoning | 172/176 = 97.73% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:image_emotion | 164/200 = 82.00% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:image_quality | 78/150 = 52.00% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:image_scene | 389/407 = 95.58% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:image_style | 198/212 = 93.40% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:image_topic | 133/140 = 95.00% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:nature_relation | 147/179 = 82.12% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:object_localization | 200/315 = 63.49% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:ocr | 148/156 = 94.87% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:physical_property_reasoning | 160/219 = 73.06% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:physical_relation | 64/94 = 68.09% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:social_relation | 147/172 = 85.47% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:spatial_relationship | 136/177 = 76.84% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:structuralized_imagetext_understanding | 251/282 = 89.01% | NATIVE |
| qwen_qwen3.8_27b | category:action_recognition | 209/215 = 97.21% | NATIVE |
| qwen_qwen3.8_27b | category:attribute_comparison | 104/141 = 73.76% | NATIVE |
| qwen_qwen3.8_27b | category:attribute_recognition | 226/264 = 85.61% | NATIVE |
| qwen_qwen3.8_27b | category:celebrity_recognition | 372/396 = 93.94% | NATIVE |
| qwen_qwen3.8_27b | category:function_reasoning | 284/304 = 93.42% | NATIVE |
| qwen_qwen3.8_27b | category:future_prediction | 74/130 = 56.92% | NATIVE |
| qwen_qwen3.8_27b | category:identity_reasoning | 172/176 = 97.73% | NATIVE |
| qwen_qwen3.8_27b | category:image_emotion | 166/200 = 83.00% | NATIVE |
| qwen_qwen3.8_27b | category:image_quality | 77/150 = 51.33% | NATIVE |
| qwen_qwen3.8_27b | category:image_scene | 389/407 = 95.58% | NATIVE |
| qwen_qwen3.8_27b | category:image_style | 198/212 = 93.40% | NATIVE |
| qwen_qwen3.8_27b | category:image_topic | 134/140 = 95.71% | NATIVE |
| qwen_qwen3.8_27b | category:nature_relation | 146/179 = 81.56% | NATIVE |
| qwen_qwen3.8_27b | category:object_localization | 201/315 = 63.81% | NATIVE |
| qwen_qwen3.8_27b | category:ocr | 148/156 = 94.87% | NATIVE |
| qwen_qwen3.8_27b | category:physical_property_reasoning | 162/219 = 73.97% | NATIVE |
| qwen_qwen3.8_27b | category:physical_relation | 63/94 = 67.02% | NATIVE |
| qwen_qwen3.8_27b | category:social_relation | 148/172 = 86.05% | NATIVE |
| qwen_qwen3.8_27b | category:spatial_relationship | 133/177 = 75.14% | NATIVE |
| qwen_qwen3.8_27b | category:structuralized_imagetext_understanding | 254/282 = 90.07% | NATIVE |

</details>

<details>
<summary>K-DTCBench — full — protocol `0d96dcdd622f`</summary>

전체 protocol fingerprint: `sha256:0d96dcdd622f6aad9fbf3619c30e03be87f0be3af65202af7d8d299cfa5124e6`

| 모델 | 축 | 결과 | 상태 |
|---|---|---|---|
| gemma_4_26b_a4b_it | category:chart | 58/80 = 72.50% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:document | 75/80 = 93.75% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:table | 72/80 = 90.00% | LEGACY_REVALIDATED |

</details>

<details>
<summary>K-DTCBench — full — protocol `a3fa0d693a36`</summary>

전체 protocol fingerprint: `sha256:a3fa0d693a36a437873ca73a1aa224e76ecd220dc0c4fe1c88973ee13b6e8d6b`

| 모델 | 축 | 결과 | 상태 |
|---|---|---|---|
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:chart | 52/80 = 65.00% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:document | 73/80 = 91.25% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:table | 60/80 = 75.00% | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | category:chart | 58/80 = 72.50% | NATIVE |
| gemma_4_26b_a4b_it | category:document | 77/80 = 96.25% | NATIVE |
| gemma_4_26b_a4b_it | category:table | 69/80 = 86.25% | NATIVE |
| qwen3.5_27b | category:chart | 53/80 = 66.25% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:document | 73/80 = 91.25% | LEGACY_REVALIDATED |
| qwen3.5_27b | category:table | 70/80 = 87.50% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:chart | 64/80 = 80.00% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:document | 79/80 = 98.75% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | category:table | 71/80 = 88.75% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:chart | 53/80 = 66.25% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:document | 73/80 = 91.25% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | category:table | 69/80 = 86.25% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:chart | 49/80 = 61.25% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:document | 68/80 = 85.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | category:table | 56/80 = 70.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:chart | 49/80 = 61.25% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:document | 70/80 = 87.50% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | category:table | 53/80 = 66.25% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:chart | 48/80 = 60.00% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:document | 69/80 = 86.25% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | category:table | 65/80 = 81.25% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:chart | 55/80 = 68.75% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:document | 73/80 = 91.25% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | category:table | 68/80 = 85.00% | LEGACY_REVALIDATED |
| qwen_qwen3.8_27B_FP8 | category:chart | 42/80 = 52.50% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:document | 70/80 = 87.50% | NATIVE |
| qwen_qwen3.8_27B_FP8 | category:table | 68/80 = 85.00% | NATIVE |
| qwen_qwen3.8_27b | category:chart | 41/80 = 51.25% | NATIVE |
| qwen_qwen3.8_27b | category:document | 70/80 = 87.50% | NATIVE |
| qwen_qwen3.8_27b | category:table | 67/80 = 83.75% | NATIVE |

</details>

<details>
<summary>K-DTCBench — full — protocol `a8e50b0990bb`</summary>

전체 protocol fingerprint: `sha256:a8e50b0990bb322cad1ca860efd99f48293c3d86f215dd77258108a563f0ebc9`

| 모델 | 축 | 결과 | 상태 |
|---|---|---|---|
| google_diffusiongemma_26B_A4B_it | category:chart | 48/80 = 60.00% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:document | 74/80 = 92.50% | NATIVE |
| google_diffusiongemma_26B_A4B_it | category:table | 68/80 = 85.00% | NATIVE |

</details>


### 추론 복원 provenance

- `results/gemma_4_26b_a4b_it/20260503_120309/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/Qwen3.5_122B_A10B_GPTQ_Int4/20260720_235721/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/google_gemma_4_26B_A4B_it/20260927_230250_r3/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen3.5_27b/20260525_145725/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/Qwen_Qwen3.6_35B_A3B/20260524_120652/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen_qwen3.5_27b_fp8/20260705_082256/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen_qwen3.5_35b_a3b/20260621_233258/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen_qwen3.5_35b_a3b_fp8/20260711_003523/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen_qwen3.6_27b/20260622_153150/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen_qwen3.6_35b_a3b_fp8/20260702_133909/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen_qwen3.8_27B_FP8/20261003_171917_r3/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen_qwen3.8_27b/20260927_232851_r3/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/google_diffusiongemma_26B_A4B_it/20260907_001502_r3/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/gemma_4_26b_a4b_it/20260503_122218/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/google_diffusiongemma_26B_A4B_it/20260907_001502_r3/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/Qwen3.5_122B_A10B_GPTQ_Int4/20260720_235721/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/google_gemma_4_26B_A4B_it/20260927_230250_r3/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen3.5_27b/20260525_145725/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/Qwen_Qwen3.6_35B_A3B/20260524_120652/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.5_27b_fp8/20260705_082256/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.5_35b_a3b/20260621_233258/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.5_35b_a3b_fp8/20260711_003523/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.6_27b/20260622_153150/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.6_27b_fp8/20260704_081047/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.6_35b_a3b_fp8/20260702_133909/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.8_27B_FP8/20261003_171917_r3/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.8_27b/20260927_232851_r3/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.5_35b_a3b_fp8/20260711_003523/vision/multimodal/kreta/qwen_qwen3.5_35b_a3b_fp8_default.jsonl`: `{"max_tokens": {"basis": "legacy run_kreta.sh: default mode default KRETA_MAX_TOKENS", "value": 4096}}`
- `results/qwen_qwen3.6_35b_a3b_fp8/20260702_133909/vision/multimodal/kreta/qwen_qwen3.6_35b_a3b_fp8_default.jsonl`: `{"max_tokens": {"basis": "legacy run_kreta.sh: default mode default KRETA_MAX_TOKENS", "value": 4096}}`
- `results/Qwen3.5_122B_A10B_GPTQ_Int4/20260720_235721/vision/multimodal/kreta/Qwen3.5_122B_A10B_GPTQ_Int4_direct.jsonl`: `{"max_tokens": {"basis": "legacy run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/google_gemma_4_26b_a4b_it/20260621_221741/vision/multimodal/kreta/google_gemma_4_26b_a4b_it_direct.jsonl`: `{"max_tokens": {"basis": "legacy run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/google_gemma_4_31B_it/20260525_152204/vision/multimodal/kreta/google_gemma_4_31B_it_direct.jsonl`: `{"max_tokens": {"basis": "legacy run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/qwen3.5_27b/20260525_145725/vision/multimodal/kreta/qwen3.5_27b_direct.jsonl`: `{"max_tokens": {"basis": "legacy run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/Qwen_Qwen3.6_35B_A3B/20260524_120652/vision/multimodal/kreta/qwen3.6-35b-a3b_direct.jsonl`: `{"max_tokens": {"basis": "legacy run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/qwen_qwen3.5_27b_fp8/20260705_082256/vision/multimodal/kreta/qwen_qwen3.5_27b_fp8_direct.jsonl`: `{"max_tokens": {"basis": "legacy run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/qwen_qwen3.5_35b_a3b/20260621_233258/vision/multimodal/kreta/qwen_qwen3.5_35b_a3b_direct.jsonl`: `{"max_tokens": {"basis": "legacy run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/qwen_qwen3.6_27b/20260622_153150/vision/multimodal/kreta/qwen_qwen3.6_27b_direct.jsonl`: `{"max_tokens": {"basis": "legacy run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/qwen_qwen3.6_27b_fp8/20260704_081047/vision/multimodal/kreta/qwen_qwen3.6_27b_fp8_direct.jsonl`: `{"max_tokens": {"basis": "legacy run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`

## 발행 불가 — 점수를 인용하지 마십시오

- **KOFFVQA / Qwen3.5_122B_A10B_GPTQ_Int4 / 20260720_235721** — `UNSCORED`
  - 채점 산출물 없음
- **B3-structured-output / qwen3.6-35b-a3b / 20260524_120652** — `REJECTED`
  - total=0
  - manifest 전 항목을 시도하지 않음
- **KOFFVQA / qwen3.6-35b-a3b / 20260524_120652** — `UNSCORED`
  - 채점 산출물 없음
- **K-DTCBench / gemma_4_26b_a4b_it / 20260503_120057** — `REJECTED`
  - 기대 건수 240와 다름
- **B4-latency-profile / gemma_4_26b_a4b_it / 20260503_120309** — `REJECTED`
  - latency 호출 실패 또는 미해결 값이 포함됨
- **KRETA / gemma_4_26b_a4b_it / 20260503_122218** — `REJECTED`
  - 오류 응답 548건 포함
- **MTVQA-KR / gemma_4_26b_a4b_it / 20260503_122218** — `REJECTED`
  - raw 재집계와 summary overall이 일치하지 않음
- **B3-structured-output / gemma_4_26b_a4b_it / 20260505_124246** — `REJECTED`
  - total=0
  - manifest 전 항목을 시도하지 않음
- **KOFFVQA / gemma_4_26b_a4b_it / 20260505_124246** — `UNSCORED`
  - 채점 산출물 없음
- **KRETA / gemma_4_26b_a4b_it / 20260505_124246** — `REJECTED`
  - 오류 응답 548건 포함
- **K-DTCBench / gemma_4_26b_a4b_it / 20260503_120057** — `REJECTED`
  - 기대 건수 240와 다름
- **B4-latency-profile / gemma_4_26b_a4b_it / 20260503_120309** — `REJECTED`
  - latency 호출 실패 또는 미해결 값이 포함됨
- **KRETA / gemma_4_26b_a4b_it / 20260503_122218** — `REJECTED`
  - 오류 응답 548건 포함
- **MTVQA-KR / gemma_4_26b_a4b_it / 20260503_122218** — `REJECTED`
  - raw 재집계와 summary overall이 일치하지 않음
- **B3-structured-output / gemma_4_26b_a4b_it / 20260505_124246** — `REJECTED`
  - total=0
  - manifest 전 항목을 시도하지 않음
- **KOFFVQA / gemma_4_26b_a4b_it / 20260505_124246** — `UNSCORED`
  - 채점 산출물 없음
- **KRETA / gemma_4_26b_a4b_it / 20260505_124246** — `REJECTED`
  - 오류 응답 548건 포함
- **B3-structured-output / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - total=0
  - manifest 전 항목을 시도하지 않음
- **K-DTCBench / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답 1건 포함
- **K-MMBench / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답 5건 포함
- **KOFFVQA / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답이 포함됨
- **KRETA / gemma_4_26b_a4b_it / 20260505_130752** — `REJECTED`
  - 오류 응답 548건 포함
- **KRETA / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답 2577건 포함
- **KOFFVQA / google_diffusiongemma_26B_A4B_it / 20260830_222550_r1** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / google_diffusiongemma_26B_A4B_it / 20260830_222550_r2** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / google_diffusiongemma_26B_A4B_it / 20260907_001502_r3** — `UNSCORED`
  - 채점 산출물 없음
- **B3-structured-output / gemma_4_26b_a4b_it / 20260505_124246.bad** — `REJECTED`
  - total=0
  - manifest 전 항목을 시도하지 않음
- **KOFFVQA / gemma_4_26b_a4b_it / 20260505_124246.bad** — `UNSCORED`
  - 채점 산출물 없음
- **KRETA / gemma_4_26b_a4b_it / 20260505_124246.bad** — `REJECTED`
  - 오류 응답 548건 포함
- **B3-structured-output / gemma_4_26b_a4b_it / 20260505_124246** — `REJECTED`
  - total=0
  - manifest 전 항목을 시도하지 않음
- **KOFFVQA / gemma_4_26b_a4b_it / 20260505_124246** — `UNSCORED`
  - 채점 산출물 없음
- **KRETA / gemma_4_26b_a4b_it / 20260505_124246** — `REJECTED`
  - 오류 응답 548건 포함
- **KOFFVQA / google_gemma_4_26b_a4b_it / 20260830_095733_r1** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / google_gemma_4_26b_a4b_it / 20260830_095733_r2** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / google_gemma_4_26b_a4b_it / 20260927_230250_r3** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / google_gemma_4_26b_a4b_it / v2b_20260824** — `UNSCORED`
  - 채점 산출물 없음
- **B3-structured-output / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - total=0
  - manifest 전 항목을 시도하지 않음
- **K-DTCBench / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답 1건 포함
- **K-MMBench / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답 5건 포함
- **KOFFVQA / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답이 포함됨
- **KRETA / gemma_4_26b_a4b_it / 20260505_130752** — `REJECTED`
  - 오류 응답 548건 포함
- **KRETA / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답 2577건 포함
- **K-DTCBench / google_gemma_4_31B_it / 20260525_152204** — `REJECTED`
  - 오류 응답 1건 포함
- **K-MMBench / google_gemma_4_31B_it / 20260525_152204** — `REJECTED`
  - 오류 응답 5건 포함
- **KOFFVQA / google_gemma_4_31B_it / 20260525_152204** — `UNSCORED`
  - 채점 산출물 없음
- **B4-latency-profile / nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16 / 20260830_095747_r1** — `REJECTED`
  - latency 호출 실패 또는 미해결 값이 포함됨
- **K-DTCBench / nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16 / 20260830_095747_r1** — `REJECTED`
  - 오류 응답 240건 포함
- **K-MMBench / nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16 / 20260830_095747_r1** — `REJECTED`
  - 오류 응답 4329건 포함
- **KOFFVQA / nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16 / 20260830_095747_r1** — `REJECTED`
  - 오류 응답이 포함됨
- **KRETA / nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16 / 20260830_095747_r1** — `REJECTED`
  - 오류 응답 2577건 포함
- **MTVQA-KR / nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16 / 20260830_095747_r1** — `REJECTED`
  - 오류 응답 558건 포함
- **KOFFVQA / qwen3.5_27b / 20260525_145725** — `REJECTED`
  - 오류 응답이 포함됨
- **KOFFVQA / qwen_qwen3.5_27b_fp8 / 20260705_082256** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen_qwen3.5_35b_a3b / 20260621_233258** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen_qwen3.5_35b_a3b_fp8 / 20260711_003523** — `UNSCORED`
  - 채점 산출물 없음
- **KRETA / qwen_qwen3.5_35b_a3b_fp8 / v2_20260824_2300** — `REJECTED`
  - 미해결 응답 6건 포함
- **KOFFVQA / qwen_qwen3.6_27b / 20260622_153150** — `UNSCORED`
  - 채점 산출물 없음
- **K-DTCBench / qwen_qwen3.6_27b_fp8 / 20260704_081047** — `REJECTED`
  - 오류 응답 1건 포함
- **KOFFVQA / qwen_qwen3.6_27b_fp8 / 20260704_081047** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen_qwen3.6_35b_a3b_fp8 / 20260702_133909** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen_qwen3.8_27B_FP8 / 20261003_171917_r1** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen_qwen3.8_27B_FP8 / 20261003_171917_r2** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen_qwen3.8_27B_FP8 / 20261003_171917_r3** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen_qwen3.8_27b / 20260927_232851_r1** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen_qwen3.8_27b / 20260927_232851_r2** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen_qwen3.8_27b / 20260927_232851_r3** — `UNSCORED`
  - 채점 산출물 없음

## B4 지연시간 — 운영 지표

정확도 헤드라인과 분리한다. 기본 표는 p50만 표시한다.

### B4-latency-profile — latency — protocol `30c7859181d0`

전체 protocol fingerprint: `sha256:30c7859181d0bfe69f2f1e084ef175a97bb12c924920ba390c3d376bf91522f5`

#### p50

| 모델 | condition | TTFT | total | tokens/sec | 상태 |
|---|---|---:|---:|---:|---|
| gemma_4_26b_a4b_it | image_1024px | 0.147s | 1.457s | 21.96 tokens/s | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | image_256px | 0.141s | 1.450s | 22.07 tokens/s | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | multi_image_3x512px | 0.151s | 1.309s | 21.40 tokens/s | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | text_only | 0.150s | 1.237s | 21.82 tokens/s | LEGACY_REVALIDATED |

<details>
<summary>p95 / p99 보기</summary>

#### p95

| 모델 | condition | TTFT | total | tokens/sec | 상태 |
|---|---|---:|---:|---:|---|
| gemma_4_26b_a4b_it | image_1024px | 0.167s | 1.486s | 22.19 tokens/s | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | image_256px | 0.156s | 1.475s | 22.30 tokens/s | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | multi_image_3x512px | 0.166s | 1.336s | 21.62 tokens/s | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | text_only | 0.171s | 1.303s | 22.14 tokens/s | LEGACY_REVALIDATED |

#### p99

| 모델 | condition | TTFT | total | tokens/sec | 상태 |
|---|---|---:|---:|---:|---|
| gemma_4_26b_a4b_it | image_1024px | 0.385s | 1.692s | 22.21 tokens/s | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | image_256px | 0.621s | 1.941s | 22.37 tokens/s | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | multi_image_3x512px | 0.887s | 2.054s | 21.64 tokens/s | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | text_only | 0.485s | 1.601s | 22.27 tokens/s | LEGACY_REVALIDATED |

</details>

> 중복 접기: `gemma_4_26b_a4b_it` — `results/gemma_4_26b_a4b_it/20260503_122218/vision/customB/b4_latency_profile` 유지; 동일 artifact role/SHA-256·측정 payload 복사본 `results/gemma_4_26b_a4b_it.bad/20260503_122218/vision/customB/b4_latency_profile` 접음.

### B4-latency-profile — latency — protocol `80955a66c67e`

전체 protocol fingerprint: `sha256:80955a66c67ef2b7fc8f5f5938a09dda13af9a01ae0acc1906acd24f4c05baf2`

#### p50

| 모델 | condition | TTFT | total | tokens/sec | 상태 |
|---|---|---:|---:|---:|---|
| Qwen3.5_122B_A10B_GPTQ_Int4 | image_1024px | 0.653s | 2.416s | 11.23 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | image_256px | 0.316s | 2.205s | 13.15 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | multi_image_3x512px | 0.566s | 2.523s | 11.89 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | text_only | 0.267s | 2.413s | 13.66 tokens/s | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | image_1024px | 0.152s | 1.402s | 22.83 tokens/s | NATIVE |
| gemma_4_26b_a4b_it | image_256px | 0.143s | 1.392s | 22.99 tokens/s | NATIVE |
| gemma_4_26b_a4b_it | multi_image_3x512px | 0.172s | 1.273s | 21.99 tokens/s | NATIVE |
| gemma_4_26b_a4b_it | text_only | 0.147s | 1.183s | 22.83 tokens/s | NATIVE |
| gemma_4_31b_it | image_1024px | 0.536s | 8.227s | 3.65 tokens/s | LEGACY_REVALIDATED |
| gemma_4_31b_it | image_256px | 0.519s | 7.957s | 3.77 tokens/s | LEGACY_REVALIDATED |
| gemma_4_31b_it | multi_image_3x512px | 0.558s | 9.171s | 3.71 tokens/s | LEGACY_REVALIDATED |
| gemma_4_31b_it | text_only | 0.527s | 9.140s | 3.72 tokens/s | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | image_1024px | 0.185s | 1.172s | 26.46 tokens/s | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | image_256px | 0.267s | 1.128s | 23.93 tokens/s | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | multi_image_3x512px | 0.424s | 1.477s | 22.34 tokens/s | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | text_only | 0.199s | 1.184s | 26.18 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | image_1024px | 0.327s | 3.995s | 8.01 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | image_256px | 0.278s | 3.703s | 8.10 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | multi_image_3x512px | 0.255s | 4.157s | 8.18 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | text_only | 0.262s | 3.686s | 8.14 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | image_1024px | 0.470s | 1.087s | 27.59 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | image_256px | 0.252s | 0.860s | 34.89 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | multi_image_3x512px | 0.425s | 1.035s | 28.98 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | text_only | 0.217s | 0.869s | 36.83 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | image_1024px | 0.396s | 0.832s | 36.06 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | image_256px | 0.210s | 0.632s | 47.46 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | multi_image_3x512px | 0.349s | 0.777s | 38.61 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | text_only | 0.181s | 0.632s | 50.65 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | image_1024px | 0.563s | 7.038s | 4.26 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | image_256px | 0.501s | 7.408s | 4.32 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | multi_image_3x512px | 0.482s | 6.952s | 4.32 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | text_only | 0.479s | 7.163s | 4.33 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | image_1024px | 0.381s | 4.282s | 7.01 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | image_256px | 0.318s | 4.231s | 7.09 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | multi_image_3x512px | 0.298s | 4.201s | 7.14 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | text_only | 0.304s | 4.347s | 7.13 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | image_1024px | 0.107s | 0.657s | 47.18 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | image_256px | 0.143s | 0.623s | 43.34 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | multi_image_3x512px | 0.253s | 0.806s | 38.46 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | text_only | 0.114s | 0.665s | 46.61 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.8_27B_FP8 | image_1024px | 0.799s | 2.333s | 13.29 tokens/s | NATIVE |
| qwen_qwen3.8_27B_FP8 | image_256px | 0.391s | 2.076s | 14.45 tokens/s | NATIVE |
| qwen_qwen3.8_27B_FP8 | multi_image_3x512px | 0.675s | 2.370s | 13.08 tokens/s | NATIVE |
| qwen_qwen3.8_27B_FP8 | text_only | 0.378s | 2.229s | 14.36 tokens/s | NATIVE |
| qwen_qwen3.8_27b | image_1024px | 1.248s | 3.739s | 8.29 tokens/s | NATIVE |
| qwen_qwen3.8_27b | image_256px | 0.621s | 3.371s | 8.90 tokens/s | NATIVE |
| qwen_qwen3.8_27b | multi_image_3x512px | 1.081s | 3.297s | 9.40 tokens/s | NATIVE |
| qwen_qwen3.8_27b | text_only | 0.598s | 3.350s | 8.96 tokens/s | NATIVE |

<details>
<summary>p95 / p99 보기</summary>

#### p95

| 모델 | condition | TTFT | total | tokens/sec | 상태 |
|---|---|---:|---:|---:|---|
| Qwen3.5_122B_A10B_GPTQ_Int4 | image_1024px | 0.659s | 2.616s | 11.52 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | image_256px | 0.319s | 2.212s | 13.20 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | multi_image_3x512px | 0.578s | 2.575s | 11.94 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | text_only | 0.294s | 2.444s | 13.74 tokens/s | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | image_1024px | 0.183s | 1.461s | 23.00 tokens/s | NATIVE |
| gemma_4_26b_a4b_it | image_256px | 0.161s | 1.453s | 23.13 tokens/s | NATIVE |
| gemma_4_26b_a4b_it | multi_image_3x512px | 0.211s | 1.328s | 22.18 tokens/s | NATIVE |
| gemma_4_26b_a4b_it | text_only | 0.175s | 1.255s | 22.94 tokens/s | NATIVE |
| gemma_4_31b_it | image_1024px | 0.558s | 8.398s | 3.75 tokens/s | LEGACY_REVALIDATED |
| gemma_4_31b_it | image_256px | 0.571s | 8.541s | 3.82 tokens/s | LEGACY_REVALIDATED |
| gemma_4_31b_it | multi_image_3x512px | 0.581s | 9.658s | 3.72 tokens/s | LEGACY_REVALIDATED |
| gemma_4_31b_it | text_only | 0.567s | 9.603s | 3.78 tokens/s | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | image_1024px | 0.202s | 1.212s | 26.87 tokens/s | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | image_256px | 0.295s | 1.213s | 24.14 tokens/s | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | multi_image_3x512px | 0.497s | 1.623s | 22.79 tokens/s | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | text_only | 0.231s | 1.282s | 26.42 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | image_1024px | 0.331s | 4.015s | 8.02 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | image_256px | 0.287s | 3.718s | 8.11 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | multi_image_3x512px | 0.264s | 4.176s | 8.19 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | text_only | 0.268s | 3.727s | 8.17 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | image_1024px | 0.500s | 1.172s | 27.76 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | image_256px | 0.261s | 0.878s | 35.09 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | multi_image_3x512px | 0.433s | 1.043s | 29.14 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | text_only | 0.291s | 1.070s | 37.16 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | image_1024px | 0.506s | 0.944s | 40.14 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | image_256px | 0.287s | 0.724s | 50.82 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | multi_image_3x512px | 0.431s | 0.876s | 42.22 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | text_only | 0.287s | 0.752s | 54.73 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | image_1024px | 0.567s | 7.046s | 4.27 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | image_256px | 0.508s | 7.416s | 4.33 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | multi_image_3x512px | 0.488s | 7.076s | 4.32 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | text_only | 0.490s | 7.294s | 4.34 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | image_1024px | 0.397s | 4.341s | 7.07 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | image_256px | 0.335s | 4.329s | 7.16 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | multi_image_3x512px | 0.314s | 4.281s | 7.21 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | text_only | 0.320s | 4.423s | 7.21 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | image_1024px | 0.124s | 0.675s | 47.61 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | image_256px | 0.166s | 0.648s | 43.78 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | multi_image_3x512px | 0.286s | 0.843s | 38.76 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | text_only | 0.154s | 0.708s | 47.11 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.8_27B_FP8 | image_1024px | 0.815s | 2.370s | 13.42 tokens/s | NATIVE |
| qwen_qwen3.8_27B_FP8 | image_256px | 0.405s | 2.100s | 14.54 tokens/s | NATIVE |
| qwen_qwen3.8_27B_FP8 | multi_image_3x512px | 0.744s | 2.435s | 13.19 tokens/s | NATIVE |
| qwen_qwen3.8_27B_FP8 | text_only | 0.452s | 2.244s | 14.44 tokens/s | NATIVE |
| qwen_qwen3.8_27b | image_1024px | 1.336s | 3.837s | 8.50 tokens/s | NATIVE |
| qwen_qwen3.8_27b | image_256px | 0.646s | 3.452s | 9.12 tokens/s | NATIVE |
| qwen_qwen3.8_27b | multi_image_3x512px | 1.258s | 3.427s | 9.60 tokens/s | NATIVE |
| qwen_qwen3.8_27b | text_only | 0.622s | 3.437s | 9.18 tokens/s | NATIVE |

#### p99

| 모델 | condition | TTFT | total | tokens/sec | 상태 |
|---|---|---:|---:|---:|---|
| Qwen3.5_122B_A10B_GPTQ_Int4 | image_1024px | 0.751s | 2.624s | 11.55 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | image_256px | 0.323s | 2.214s | 13.21 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | multi_image_3x512px | 0.624s | 2.605s | 11.96 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | text_only | 0.339s | 2.477s | 13.76 tokens/s | LEGACY_REVALIDATED |
| gemma_4_26b_a4b_it | image_1024px | 0.334s | 1.628s | 23.02 tokens/s | NATIVE |
| gemma_4_26b_a4b_it | image_256px | 0.326s | 1.580s | 23.14 tokens/s | NATIVE |
| gemma_4_26b_a4b_it | multi_image_3x512px | 0.907s | 2.027s | 22.21 tokens/s | NATIVE |
| gemma_4_26b_a4b_it | text_only | 0.283s | 1.322s | 22.97 tokens/s | NATIVE |
| gemma_4_31b_it | image_1024px | 0.768s | 8.777s | 3.75 tokens/s | LEGACY_REVALIDATED |
| gemma_4_31b_it | image_256px | 0.762s | 8.747s | 3.82 tokens/s | LEGACY_REVALIDATED |
| gemma_4_31b_it | multi_image_3x512px | 2.098s | 10.740s | 3.72 tokens/s | LEGACY_REVALIDATED |
| gemma_4_31b_it | text_only | 0.686s | 9.878s | 3.81 tokens/s | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | image_1024px | 0.472s | 1.522s | 26.99 tokens/s | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | image_256px | 0.309s | 1.282s | 24.22 tokens/s | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | multi_image_3x512px | 0.524s | 1.682s | 22.84 tokens/s | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | text_only | 0.296s | 1.385s | 26.46 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | image_1024px | 0.587s | 4.263s | 8.03 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | image_256px | 0.292s | 3.829s | 8.12 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | multi_image_3x512px | 0.523s | 4.419s | 8.22 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | text_only | 0.343s | 3.805s | 8.18 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | image_1024px | 0.879s | 1.209s | 27.78 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | image_256px | 0.307s | 0.961s | 35.11 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | multi_image_3x512px | 0.488s | 1.142s | 29.21 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | text_only | 0.384s | 1.130s | 37.23 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | image_1024px | 0.959s | 1.398s | 40.43 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | image_256px | 0.447s | 0.879s | 51.47 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | multi_image_3x512px | 0.790s | 1.246s | 42.73 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | text_only | 0.672s | 1.127s | 54.93 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | image_1024px | 0.938s | 7.416s | 4.27 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | image_256px | 0.514s | 7.423s | 4.33 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | multi_image_3x512px | 1.138s | 7.381s | 4.32 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | text_only | 0.505s | 7.380s | 4.38 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | image_1024px | 0.663s | 4.607s | 7.07 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | image_256px | 0.341s | 4.369s | 7.20 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | multi_image_3x512px | 0.595s | 4.528s | 7.22 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | text_only | 0.329s | 4.443s | 7.22 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | image_1024px | 0.317s | 0.871s | 47.83 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | image_256px | 0.173s | 0.654s | 43.86 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | multi_image_3x512px | 0.347s | 0.894s | 38.79 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | text_only | 0.194s | 0.744s | 47.17 tokens/s | LEGACY_REVALIDATED |
| qwen_qwen3.8_27B_FP8 | image_1024px | 0.882s | 2.424s | 13.59 tokens/s | NATIVE |
| qwen_qwen3.8_27B_FP8 | image_256px | 0.496s | 2.191s | 14.70 tokens/s | NATIVE |
| qwen_qwen3.8_27B_FP8 | multi_image_3x512px | 0.811s | 2.564s | 13.61 tokens/s | NATIVE |
| qwen_qwen3.8_27B_FP8 | text_only | 0.478s | 2.300s | 14.46 tokens/s | NATIVE |
| qwen_qwen3.8_27b | image_1024px | 1.357s | 3.876s | 8.55 tokens/s | NATIVE |
| qwen_qwen3.8_27b | image_256px | 0.692s | 3.493s | 9.23 tokens/s | NATIVE |
| qwen_qwen3.8_27b | multi_image_3x512px | 1.373s | 3.585s | 9.84 tokens/s | NATIVE |
| qwen_qwen3.8_27b | text_only | 0.668s | 3.490s | 9.29 tokens/s | NATIVE |

</details>

> 중복 접기: `gemma_4_31b_it` — `results/gemma_4_31b_it/20260505_130752/vision/customB/b4_latency_profile` 유지; 동일 artifact role/SHA-256·측정 payload 복사본 `results/google_gemma_4_31B_it/20260505_130752/vision/customB/b4_latency_profile` 접음.
