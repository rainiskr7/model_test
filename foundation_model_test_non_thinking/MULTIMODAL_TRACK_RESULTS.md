# multimodal 트랙 결과

이 파일은 `report_multimodal_tracks.py`가 `_derived` sidecar에서 생성한다. 손으로 고치지 말 것.

판단 기준: [`MULTIMODAL_PUBLISH_CONTRACT.md`](MULTIMODAL_PUBLISH_CONTRACT.md).

발행 가능 source **71** / 발행 불가 source **46** / 게이트 기록 없음 **0**.

읽는 법:

- 서로 다른 벤치와 축을 합산하거나 평균하지 않는다.
- 결과는 반올림된 점수만 보지 말고 분자/분모를 함께 본다.
- PROVISIONAL은 판정기 기준이며 인간 검증 전이다.
- 거부된 런의 숫자는 원본에 존재하더라도 인용하지 않는다.

## 헤드라인 — 벤치마크별 overall

### KRETA — default, 2577문항 — protocol `700da17443eb`

전체 protocol fingerprint: `sha256:700da17443eb6ab0c6fc5505e849493a4586502d57d5cb2f366915aa9f28d986`

| 모델 | 결과 | 상태 |
|---|---|---|
| qwen_qwen3.6_35b_a3b_fp8 | 2321/2577 = 90.07% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | 2259/2577 = 87.66% | LEGACY_REVALIDATED |

> 각주: 기록된 repo commit이 런마다 다름(문항 집합은 동일): `3104bffac9fe`, `9219dbd6b1f7`.

### KRETA — direct, 2577문항 — protocol `2eac70b4f5b4`

전체 protocol fingerprint: `sha256:2eac70b4f5b4ae422ebeb77d44bc0bd0b5b0e779efbfb884f3e36b5422eaa7cd`

| 모델 | 결과 | 상태 |
|---|---|---|
| google_gemma_4_31B_it | 2030/2577 = 78.77% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | 1864/2577 = 72.33% | LEGACY_REVALIDATED |
| qwen3.5_27b | 1850/2577 = 71.79% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | 1828/2577 = 70.94% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | 1821/2577 = 70.66% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | 1782/2577 = 69.15% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | 1735/2577 = 67.33% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | 1732/2577 = 67.21% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | 1639/2577 = 63.60% | LEGACY_REVALIDATED |

> 각주: 기록된 repo commit이 런마다 다름(문항 집합은 동일): `736779d467f6`, `7c0155d6bfa1`, `aad99f4759b9`, `c273302ade2c`, `ffe124392283`.

### K-MMBench — full, 4329문항 — protocol `214f704b7c50`

전체 protocol fingerprint: `sha256:214f704b7c50dee78777eb3c6bab002a8854889ec1f1c52d8d103e6c2401b35a`

| 모델 | 결과 | 상태 |
|---|---|---|
| qwen3.6-35b-a3b | 3907/4329 = 90.25% | LEGACY_REVALIDATED |
| qwen3.5_27b | 3701/4329 = 85.49% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | 3688/4329 = 85.19% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | 3610/4329 = 83.39% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | 3608/4329 = 83.34% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | 3584/4329 = 82.79% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | 3489/4329 = 80.60% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | 3425/4329 = 79.12% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | 3395/4329 = 78.42% | LEGACY_REVALIDATED |

### K-DTCBench — full, 240문항 — protocol `4f3ddf3131ab`

전체 protocol fingerprint: `sha256:4f3ddf3131ab43c9a233de443d2e24c072421fd8fe0b01ec2d5ae3e470fdb0c5`

| 모델 | 결과 | 상태 |
|---|---|---|
| qwen3.6-35b-a3b | 214/240 = 89.17% | LEGACY_REVALIDATED |
| qwen3.5_27b | 196/240 = 81.67% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | 196/240 = 81.67% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | 195/240 = 81.25% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | 185/240 = 77.08% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | 182/240 = 75.83% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | 173/240 = 72.08% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | 172/240 = 71.67% | LEGACY_REVALIDATED |

### MTVQA-KR — full, 558문항 — protocol `22d01e02a2f6`

전체 protocol fingerprint: `sha256:22d01e02a2f6451f0043f54b2b361d974922523ed924c7830780bdbd9627aeb6`

| 모델 | 결과 | 상태 |
|---|---|---|
| qwen_qwen3.5_35b_a3b | 292/558 = 52.33% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | 292/558 = 52.33% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | 291/558 = 52.15% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | 290/558 = 51.97% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | 290/558 = 51.97% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | 288/558 = 51.61% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | 287/558 = 51.43% | LEGACY_REVALIDATED |
| qwen3.5_27b | 286/558 = 51.25% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | 273/558 = 48.92% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | 268/558 = 48.03% | LEGACY_REVALIDATED |

## 상태 요약

| 상태 | source 수 |
|---|---:|
| NATIVE | 0 |
| LEGACY_REVALIDATED | 71 |
| REJECTED | 33 |
| INSUFFICIENT_PROVENANCE | 0 |
| UNSCORED | 13 |

## 세부 축

카테고리 및 System1/2 등 세부 축은 벤치별로 접어 두었다.

<details>
<summary>KRETA — default — protocol `700da17443eb`</summary>

전체 protocol fingerprint: `sha256:700da17443eb6ab0c6fc5505e849493a4586502d57d5cb2f366915aa9f28d986`

| 모델 | 축 | 결과 | 상태 |
|---|---|---|---|
| qwen_qwen3.5_35b_a3b_fp8 | domain:Arts and Humanities | 80/83 = 96.39% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:CSAT History | 42/60 = 70.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:CSAT Science | 265/478 = 55.44% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Economics and Finance | 102/104 = 98.08% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Education and Academia | 205/215 = 95.35% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Entertainment and Media | 156/168 = 92.86% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Hospitality and Food Service | 254/264 = 96.21% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Marketing and Advertising | 139/145 = 95.86% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Medical and Healthcare | 83/90 = 92.22% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Personal and Lifestyle | 199/204 = 97.55% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Public and Administration | 240/245 = 97.96% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Retail and Commerce | 145/154 = 94.16% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Science and Technology | 87/92 = 94.57% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Transportation and Logistics | 155/167 = 92.81% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | domain:Travel and Tourism | 107/108 = 99.07% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | system:System1 | 1379/1426 = 96.70% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b_fp8 | system:System2 | 880/1151 = 76.46% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Arts and Humanities | 82/83 = 98.80% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:CSAT History | 45/60 = 75.00% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:CSAT Science | 314/478 = 65.69% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Economics and Finance | 102/104 = 98.08% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Education and Academia | 207/215 = 96.28% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Entertainment and Media | 160/168 = 95.24% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Hospitality and Food Service | 254/264 = 96.21% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Marketing and Advertising | 143/145 = 98.62% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Medical and Healthcare | 84/90 = 93.33% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Personal and Lifestyle | 201/204 = 98.53% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Public and Administration | 237/245 = 96.73% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Retail and Commerce | 145/154 = 94.16% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Science and Technology | 88/92 = 95.65% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Transportation and Logistics | 151/167 = 90.42% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | domain:Travel and Tourism | 108/108 = 100.00% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | system:System1 | 1387/1426 = 97.27% | LEGACY_REVALIDATED |
| qwen_qwen3.6_35b_a3b_fp8 | system:System2 | 934/1151 = 81.15% | LEGACY_REVALIDATED |

</details>

<details>
<summary>KRETA — direct — protocol `2eac70b4f5b4`</summary>

전체 protocol fingerprint: `sha256:2eac70b4f5b4ae422ebeb77d44bc0bd0b5b0e779efbfb884f3e36b5422eaa7cd`

| 모델 | 축 | 결과 | 상태 |
|---|---|---|---|
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Arts and Humanities | 70/83 = 84.34% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:CSAT History | 26/60 = 43.33% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:CSAT Science | 122/478 = 25.52% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Economics and Finance | 66/104 = 63.46% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Education and Academia | 162/215 = 75.35% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Entertainment and Media | 128/168 = 76.19% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Hospitality and Food Service | 183/264 = 69.32% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Marketing and Advertising | 113/145 = 77.93% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Medical and Healthcare | 51/90 = 56.67% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Personal and Lifestyle | 165/204 = 80.88% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Public and Administration | 175/245 = 71.43% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Retail and Commerce | 114/154 = 74.03% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Science and Technology | 65/92 = 70.65% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Transportation and Logistics | 119/167 = 71.26% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | domain:Travel and Tourism | 80/108 = 74.07% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | system:System1 | 1168/1426 = 81.91% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | system:System2 | 471/1151 = 40.92% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:Arts and Humanities | 78/83 = 93.98% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:CSAT History | 39/60 = 65.00% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:CSAT Science | 173/478 = 36.19% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:Economics and Finance | 87/104 = 83.65% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:Education and Academia | 185/215 = 86.05% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:Entertainment and Media | 140/168 = 83.33% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:Hospitality and Food Service | 199/264 = 75.38% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:Marketing and Advertising | 128/145 = 88.28% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:Medical and Healthcare | 70/90 = 77.78% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:Personal and Lifestyle | 172/204 = 84.31% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:Public and Administration | 196/245 = 80.00% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:Retail and Commerce | 121/154 = 78.57% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:Science and Technology | 72/92 = 78.26% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:Transportation and Logistics | 117/167 = 70.06% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | domain:Travel and Tourism | 87/108 = 80.56% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | system:System1 | 1283/1426 = 89.97% | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | system:System2 | 581/1151 = 50.48% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:Arts and Humanities | 78/83 = 93.98% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:CSAT History | 46/60 = 76.67% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:CSAT Science | 203/478 = 42.47% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:Economics and Finance | 89/104 = 85.58% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:Education and Academia | 197/215 = 91.63% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:Entertainment and Media | 146/168 = 86.90% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:Hospitality and Food Service | 223/264 = 84.47% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:Marketing and Advertising | 138/145 = 95.17% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:Medical and Healthcare | 74/90 = 82.22% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:Personal and Lifestyle | 184/204 = 90.20% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:Public and Administration | 215/245 = 87.76% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:Retail and Commerce | 129/154 = 83.77% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:Science and Technology | 80/92 = 86.96% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:Transportation and Logistics | 138/167 = 82.63% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | domain:Travel and Tourism | 90/108 = 83.33% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | system:System1 | 1366/1426 = 95.79% | LEGACY_REVALIDATED |
| google_gemma_4_31B_it | system:System2 | 664/1151 = 57.69% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Arts and Humanities | 74/83 = 89.16% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:CSAT History | 33/60 = 55.00% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:CSAT Science | 150/478 = 31.38% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Economics and Finance | 82/104 = 78.85% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Education and Academia | 182/215 = 84.65% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Entertainment and Media | 138/168 = 82.14% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Hospitality and Food Service | 203/264 = 76.89% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Marketing and Advertising | 125/145 = 86.21% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Medical and Healthcare | 69/90 = 76.67% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Personal and Lifestyle | 182/204 = 89.22% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Public and Administration | 193/245 = 78.78% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Retail and Commerce | 118/154 = 76.62% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Science and Technology | 69/92 = 75.00% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Transportation and Logistics | 135/167 = 80.84% | LEGACY_REVALIDATED |
| qwen3.5_27b | domain:Travel and Tourism | 97/108 = 89.81% | LEGACY_REVALIDATED |
| qwen3.5_27b | system:System1 | 1318/1426 = 92.43% | LEGACY_REVALIDATED |
| qwen3.5_27b | system:System2 | 532/1151 = 46.22% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:Arts and Humanities | 67/83 = 80.72% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:CSAT History | 27/60 = 45.00% | LEGACY_REVALIDATED |
| qwen3.6-35b-a3b | domain:CSAT Science | 132/478 = 27.62% | LEGACY_REVALIDATED |
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
| qwen3.6-35b-a3b | system:System2 | 487/1151 = 42.31% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Arts and Humanities | 75/83 = 90.36% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:CSAT History | 33/60 = 55.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:CSAT Science | 142/478 = 29.71% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Economics and Finance | 81/104 = 77.88% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Education and Academia | 178/215 = 82.79% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Entertainment and Media | 142/168 = 84.52% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Hospitality and Food Service | 198/264 = 75.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Marketing and Advertising | 128/145 = 88.28% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Medical and Healthcare | 63/90 = 70.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Personal and Lifestyle | 181/204 = 88.73% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Public and Administration | 194/245 = 79.18% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Retail and Commerce | 124/154 = 80.52% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Science and Technology | 69/92 = 75.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Transportation and Logistics | 127/167 = 76.05% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | domain:Travel and Tourism | 93/108 = 86.11% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | system:System1 | 1313/1426 = 92.08% | LEGACY_REVALIDATED |
| qwen_qwen3.5_27b_fp8 | system:System2 | 515/1151 = 44.74% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Arts and Humanities | 74/83 = 89.16% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:CSAT History | 30/60 = 50.00% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:CSAT Science | 128/478 = 26.78% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Economics and Finance | 82/104 = 78.85% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Education and Academia | 178/215 = 82.79% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Entertainment and Media | 124/168 = 73.81% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Hospitality and Food Service | 211/264 = 79.92% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Marketing and Advertising | 121/145 = 83.45% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Medical and Healthcare | 66/90 = 73.33% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Personal and Lifestyle | 176/204 = 86.27% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Public and Administration | 187/245 = 76.33% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Retail and Commerce | 121/154 = 78.57% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Science and Technology | 66/92 = 71.74% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Transportation and Logistics | 125/167 = 74.85% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | domain:Travel and Tourism | 93/108 = 86.11% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | system:System1 | 1264/1426 = 88.64% | LEGACY_REVALIDATED |
| qwen_qwen3.5_35b_a3b | system:System2 | 518/1151 = 45.00% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Arts and Humanities | 70/83 = 84.34% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:CSAT History | 28/60 = 46.67% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:CSAT Science | 129/478 = 26.99% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Economics and Finance | 76/104 = 73.08% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Education and Academia | 178/215 = 82.79% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Entertainment and Media | 137/168 = 81.55% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Hospitality and Food Service | 185/264 = 70.08% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Marketing and Advertising | 115/145 = 79.31% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Medical and Healthcare | 68/90 = 75.56% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Personal and Lifestyle | 170/204 = 83.33% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Public and Administration | 184/245 = 75.10% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Retail and Commerce | 121/154 = 78.57% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Science and Technology | 67/92 = 72.83% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Transportation and Logistics | 121/167 = 72.46% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | domain:Travel and Tourism | 86/108 = 79.63% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | system:System1 | 1258/1426 = 88.22% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b | system:System2 | 477/1151 = 41.44% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Arts and Humanities | 75/83 = 90.36% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:CSAT History | 30/60 = 50.00% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:CSAT Science | 138/478 = 28.87% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Economics and Finance | 80/104 = 76.92% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Education and Academia | 179/215 = 83.26% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Entertainment and Media | 142/168 = 84.52% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Hospitality and Food Service | 202/264 = 76.52% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Marketing and Advertising | 122/145 = 84.14% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Medical and Healthcare | 69/90 = 76.67% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Personal and Lifestyle | 176/204 = 86.27% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Public and Administration | 197/245 = 80.41% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Retail and Commerce | 121/154 = 78.57% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Science and Technology | 70/92 = 76.09% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Transportation and Logistics | 127/167 = 76.05% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | domain:Travel and Tourism | 93/108 = 86.11% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | system:System1 | 1286/1426 = 90.18% | LEGACY_REVALIDATED |
| qwen_qwen3.6_27b_fp8 | system:System2 | 535/1151 = 46.48% | LEGACY_REVALIDATED |

</details>

<details>
<summary>K-MMBench — full — protocol `214f704b7c50`</summary>

전체 protocol fingerprint: `sha256:214f704b7c50dee78777eb3c6bab002a8854889ec1f1c52d8d103e6c2401b35a`

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

</details>

<details>
<summary>K-DTCBench — full — protocol `4f3ddf3131ab`</summary>

전체 protocol fingerprint: `sha256:4f3ddf3131ab43c9a233de443d2e24c072421fd8fe0b01ec2d5ae3e470fdb0c5`

| 모델 | 축 | 결과 | 상태 |
|---|---|---|---|
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:chart | 52/80 = 65.00% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:document | 73/80 = 91.25% | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | category:table | 60/80 = 75.00% | LEGACY_REVALIDATED |
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

</details>


### 추론 복원 provenance

- `results/Qwen3.5_122B_A10B_GPTQ_Int4/20260720_235721/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen3.5_27b/20260525_145725/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/Qwen_Qwen3.6_35B_A3B/20260524_120652/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen_qwen3.5_27b_fp8/20260705_082256/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen_qwen3.5_35b_a3b/20260621_233258/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen_qwen3.5_35b_a3b_fp8/20260711_003523/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen_qwen3.6_27b/20260622_153150/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/qwen_qwen3.6_35b_a3b_fp8/20260702_133909/vision/multimodal/k_dtcbench`: `{"split": {"basis": "k_dtcbench.py fixed load_dataset split", "value": "test"}}`
- `results/Qwen3.5_122B_A10B_GPTQ_Int4/20260720_235721/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen3.5_27b/20260525_145725/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/Qwen_Qwen3.6_35B_A3B/20260524_120652/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.5_27b_fp8/20260705_082256/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.5_35b_a3b/20260621_233258/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.5_35b_a3b_fp8/20260711_003523/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.6_27b/20260622_153150/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.6_27b_fp8/20260704_081047/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.6_35b_a3b_fp8/20260702_133909/vision/multimodal/k_mmbench`: `{"split": {"basis": "k_mmbench.py fixed load_dataset split", "value": "dev"}}`
- `results/qwen_qwen3.5_35b_a3b_fp8/20260711_003523/vision/multimodal/kreta/qwen_qwen3.5_35b_a3b_fp8_default.jsonl`: `{"max_tokens": {"basis": "run_kreta.sh: default mode default KRETA_MAX_TOKENS", "value": 4096}}`
- `results/qwen_qwen3.6_35b_a3b_fp8/20260702_133909/vision/multimodal/kreta/qwen_qwen3.6_35b_a3b_fp8_default.jsonl`: `{"max_tokens": {"basis": "run_kreta.sh: default mode default KRETA_MAX_TOKENS", "value": 4096}}`
- `results/Qwen3.5_122B_A10B_GPTQ_Int4/20260720_235721/vision/multimodal/kreta/Qwen3.5_122B_A10B_GPTQ_Int4_direct.jsonl`: `{"max_tokens": {"basis": "run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/google_gemma_4_26B_A4B_it/20260621_221741/vision/multimodal/kreta/google_gemma_4_26b_a4b_it_direct.jsonl`: `{"max_tokens": {"basis": "run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/google_gemma_4_31B_it/20260525_152204/vision/multimodal/kreta/google_gemma_4_31B_it_direct.jsonl`: `{"max_tokens": {"basis": "run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/qwen3.5_27b/20260525_145725/vision/multimodal/kreta/qwen3.5_27b_direct.jsonl`: `{"max_tokens": {"basis": "run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/Qwen_Qwen3.6_35B_A3B/20260524_120652/vision/multimodal/kreta/qwen3.6-35b-a3b_direct.jsonl`: `{"max_tokens": {"basis": "run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/qwen_qwen3.5_27b_fp8/20260705_082256/vision/multimodal/kreta/qwen_qwen3.5_27b_fp8_direct.jsonl`: `{"max_tokens": {"basis": "run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/qwen_qwen3.5_35b_a3b/20260621_233258/vision/multimodal/kreta/qwen_qwen3.5_35b_a3b_direct.jsonl`: `{"max_tokens": {"basis": "run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/qwen_qwen3.6_27b/20260622_153150/vision/multimodal/kreta/qwen_qwen3.6_27b_direct.jsonl`: `{"max_tokens": {"basis": "run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`
- `results/qwen_qwen3.6_27b_fp8/20260704_081047/vision/multimodal/kreta/qwen_qwen3.6_27b_fp8_direct.jsonl`: `{"max_tokens": {"basis": "run_kreta.sh: direct mode default KRETA_MAX_TOKENS", "value": 32}}`

## 대표 런 자동 선정 불가 — 수치 비노출

- **B4-latency-profile / latency / gemma_4_31b_it** — 동일한 최신 완료 시각 후보가 둘 이상
  - `results/gemma_4_31b_it/20260505_130752/vision/customB/b4_latency_profile`
  - `results/google_gemma_4_31B_it/20260505_130752/vision/customB/b4_latency_profile`
- **B4-latency-profile / latency / gemma_4_26b_a4b_it** — 동일한 최신 완료 시각 후보가 둘 이상
  - `results/gemma_4_26b_a4b_it.bad/20260503_122218/vision/customB/b4_latency_profile`
  - `results/gemma_4_26b_a4b_it/20260503_122218/vision/customB/b4_latency_profile`
- **K-DTCBench / full / gemma_4_26b_a4b_it** — 동일한 최신 완료 시각 후보가 둘 이상
  - `results/gemma_4_26b_a4b_it.bad/20260505_124246/vision/multimodal/k_dtcbench`
  - `results/gemma_4_26b_a4b_it/20260505_124246/vision/multimodal/k_dtcbench`
  - `results/google_gemma_4_26B_A4B_it/20260505_124246.bad/vision/multimodal/k_dtcbench`
  - `results/google_gemma_4_26B_A4B_it/20260505_124246/vision/multimodal/k_dtcbench`
- **K-DTCBench / full / gemma_4_26b_a4b_it** — 동일한 최신 완료 시각 후보가 둘 이상
  - `results/gemma_4_26b_a4b_it.bad/20260503_120151/vision/multimodal/k_dtcbench`
  - `results/gemma_4_26b_a4b_it.bad/20260503_120309/vision/multimodal/k_dtcbench`
  - `results/gemma_4_26b_a4b_it/20260503_120151/vision/multimodal/k_dtcbench`
  - `results/gemma_4_26b_a4b_it/20260503_120309/vision/multimodal/k_dtcbench`
- **K-MMBench / full / gemma_4_26b_a4b_it** — 동일한 최신 완료 시각 후보가 둘 이상
  - `results/gemma_4_26b_a4b_it.bad/20260505_124246/vision/multimodal/k_mmbench`
  - `results/gemma_4_26b_a4b_it/20260505_124246/vision/multimodal/k_mmbench`
  - `results/google_gemma_4_26B_A4B_it/20260505_124246.bad/vision/multimodal/k_mmbench`
  - `results/google_gemma_4_26B_A4B_it/20260505_124246/vision/multimodal/k_mmbench`
- **K-MMBench / full / gemma_4_26b_a4b_it** — 동일한 최신 완료 시각 후보가 둘 이상
  - `results/gemma_4_26b_a4b_it.bad/20260503_122218/vision/multimodal/k_mmbench`
  - `results/gemma_4_26b_a4b_it/20260503_122218/vision/multimodal/k_mmbench`
- **MTVQA-KR / full / gemma_4_26b_a4b_it** — 동일한 최신 완료 시각 후보가 둘 이상
  - `results/gemma_4_26b_a4b_it.bad/20260505_124246/vision/multimodal/mtvqa_kr`
  - `results/gemma_4_26b_a4b_it/20260505_124246/vision/multimodal/mtvqa_kr`
  - `results/google_gemma_4_26B_A4B_it/20260505_124246.bad/vision/multimodal/mtvqa_kr`
  - `results/google_gemma_4_26B_A4B_it/20260505_124246/vision/multimodal/mtvqa_kr`
- **MTVQA-KR / full / gemma_4_31b_it** — 동일한 최신 완료 시각 후보가 둘 이상
  - `results/gemma_4_31b_it/20260505_130752/vision/multimodal/mtvqa_kr`
  - `results/google_gemma_4_31B_it/20260505_130752/vision/multimodal/mtvqa_kr`

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
  - summary condition 완주/실패 집계가 일치하지 않음
- **KRETA / gemma_4_26b_a4b_it / 20260503_122218** — `REJECTED`
  - 오류 응답이 포함됨
  - raw 재집계와 results.json overall이 일치하지 않음
  - raw 재집계와 results.json domain이 일치하지 않음
- **MTVQA-KR / gemma_4_26b_a4b_it / 20260503_122218** — `REJECTED`
  - raw 재집계와 summary overall이 일치하지 않음
- **B3-structured-output / gemma_4_26b_a4b_it / 20260505_124246** — `REJECTED`
  - total=0
  - manifest 전 항목을 시도하지 않음
- **KOFFVQA / gemma_4_26b_a4b_it / 20260505_124246** — `UNSCORED`
  - 채점 산출물 없음
- **KRETA / gemma_4_26b_a4b_it / 20260505_124246** — `REJECTED`
  - 오류 응답이 포함됨
  - raw 재집계와 results.json overall이 일치하지 않음
  - raw 재집계와 results.json domain이 일치하지 않음
- **K-DTCBench / gemma_4_26b_a4b_it / 20260503_120057** — `REJECTED`
  - 기대 건수 240와 다름
- **B4-latency-profile / gemma_4_26b_a4b_it / 20260503_120309** — `REJECTED`
  - latency 호출 실패 또는 미해결 값이 포함됨
  - summary condition 완주/실패 집계가 일치하지 않음
- **KRETA / gemma_4_26b_a4b_it / 20260503_122218** — `REJECTED`
  - 오류 응답이 포함됨
  - raw 재집계와 results.json overall이 일치하지 않음
  - raw 재집계와 results.json domain이 일치하지 않음
- **MTVQA-KR / gemma_4_26b_a4b_it / 20260503_122218** — `REJECTED`
  - raw 재집계와 summary overall이 일치하지 않음
- **B3-structured-output / gemma_4_26b_a4b_it / 20260505_124246** — `REJECTED`
  - total=0
  - manifest 전 항목을 시도하지 않음
- **KOFFVQA / gemma_4_26b_a4b_it / 20260505_124246** — `UNSCORED`
  - 채점 산출물 없음
- **KRETA / gemma_4_26b_a4b_it / 20260505_124246** — `REJECTED`
  - 오류 응답이 포함됨
  - raw 재집계와 results.json overall이 일치하지 않음
  - raw 재집계와 results.json domain이 일치하지 않음
- **B3-structured-output / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - total=0
  - manifest 전 항목을 시도하지 않음
- **K-DTCBench / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답이 포함됨
- **K-MMBench / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답이 포함됨
- **KOFFVQA / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답이 포함됨
- **KRETA / gemma_4_26b_a4b_it / 20260505_130752** — `REJECTED`
  - 오류 응답이 포함됨
  - raw 재집계와 results.json overall이 일치하지 않음
  - raw 재집계와 results.json domain이 일치하지 않음
- **KRETA / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답이 포함됨
  - raw 재집계와 results.json overall이 일치하지 않음
- **B3-structured-output / gemma_4_26b_a4b_it / 20260505_124246.bad** — `REJECTED`
  - total=0
  - manifest 전 항목을 시도하지 않음
- **KOFFVQA / gemma_4_26b_a4b_it / 20260505_124246.bad** — `UNSCORED`
  - 채점 산출물 없음
- **KRETA / gemma_4_26b_a4b_it / 20260505_124246.bad** — `REJECTED`
  - 오류 응답이 포함됨
  - raw 재집계와 results.json overall이 일치하지 않음
  - raw 재집계와 results.json domain이 일치하지 않음
- **B3-structured-output / gemma_4_26b_a4b_it / 20260505_124246** — `REJECTED`
  - total=0
  - manifest 전 항목을 시도하지 않음
- **KOFFVQA / gemma_4_26b_a4b_it / 20260505_124246** — `UNSCORED`
  - 채점 산출물 없음
- **KRETA / gemma_4_26b_a4b_it / 20260505_124246** — `REJECTED`
  - 오류 응답이 포함됨
  - raw 재집계와 results.json overall이 일치하지 않음
  - raw 재집계와 results.json domain이 일치하지 않음
- **B3-structured-output / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - total=0
  - manifest 전 항목을 시도하지 않음
- **K-DTCBench / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답이 포함됨
- **K-MMBench / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답이 포함됨
- **KOFFVQA / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답이 포함됨
- **KRETA / gemma_4_26b_a4b_it / 20260505_130752** — `REJECTED`
  - 오류 응답이 포함됨
  - raw 재집계와 results.json overall이 일치하지 않음
  - raw 재집계와 results.json domain이 일치하지 않음
- **KRETA / gemma_4_31b_it / 20260505_130752** — `REJECTED`
  - 오류 응답이 포함됨
  - raw 재집계와 results.json overall이 일치하지 않음
- **K-DTCBench / google_gemma_4_31B_it / 20260525_152204** — `REJECTED`
  - 오류 응답이 포함됨
- **K-MMBench / google_gemma_4_31B_it / 20260525_152204** — `REJECTED`
  - 오류 응답이 포함됨
- **KOFFVQA / google_gemma_4_31B_it / 20260525_152204** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen3.5_27b / 20260525_145725** — `REJECTED`
  - 오류 응답이 포함됨
- **KOFFVQA / qwen_qwen3.5_27b_fp8 / 20260705_082256** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen_qwen3.5_35b_a3b / 20260621_233258** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen_qwen3.5_35b_a3b_fp8 / 20260711_003523** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen_qwen3.6_27b / 20260622_153150** — `UNSCORED`
  - 채점 산출물 없음
- **K-DTCBench / qwen_qwen3.6_27b_fp8 / 20260704_081047** — `REJECTED`
  - 오류 응답이 포함됨
- **KOFFVQA / qwen_qwen3.6_27b_fp8 / 20260704_081047** — `UNSCORED`
  - 채점 산출물 없음
- **KOFFVQA / qwen_qwen3.6_35b_a3b_fp8 / 20260702_133909** — `UNSCORED`
  - 채점 산출물 없음

## B4 지연시간 — 운영 지표

정확도 헤드라인과 분리한다. 기본 표는 p50만 표시한다.

### B4-latency-profile — latency — protocol `637d13ba3098`

전체 protocol fingerprint: `sha256:637d13ba309889f68c50a9e7557be4c1468c2edc5452637746a62ee2aa3a1b22`

#### p50

| 모델 | condition | TTFT | total | tokens/sec | 상태 |
|---|---|---:|---:|---:|---|
| Qwen3.5_122B_A10B_GPTQ_Int4 | image_1024px | 0.653s | 2.416s | 11.23 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | image_256px | 0.316s | 2.205s | 13.15 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | multi_image_3x512px | 0.566s | 2.523s | 11.89 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | text_only | 0.267s | 2.413s | 13.66 tokens/s | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | image_1024px | 0.142s | 1.404s | 22.78 tokens/s | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | image_256px | 0.138s | 1.431s | 22.36 tokens/s | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | multi_image_3x512px | 0.148s | 1.257s | 22.28 tokens/s | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | text_only | 0.140s | 1.211s | 22.29 tokens/s | LEGACY_REVALIDATED |
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

<details>
<summary>p95 / p99 보기</summary>

#### p95

| 모델 | condition | TTFT | total | tokens/sec | 상태 |
|---|---|---:|---:|---:|---|
| Qwen3.5_122B_A10B_GPTQ_Int4 | image_1024px | 0.659s | 2.616s | 11.52 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | image_256px | 0.319s | 2.212s | 13.20 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | multi_image_3x512px | 0.578s | 2.575s | 11.94 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | text_only | 0.294s | 2.444s | 13.74 tokens/s | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | image_1024px | 0.155s | 1.443s | 22.98 tokens/s | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | image_256px | 0.147s | 1.441s | 22.45 tokens/s | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | multi_image_3x512px | 0.159s | 1.268s | 22.41 tokens/s | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | text_only | 0.155s | 1.223s | 23.00 tokens/s | LEGACY_REVALIDATED |
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

#### p99

| 모델 | condition | TTFT | total | tokens/sec | 상태 |
|---|---|---:|---:|---:|---|
| Qwen3.5_122B_A10B_GPTQ_Int4 | image_1024px | 0.751s | 2.624s | 11.55 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | image_256px | 0.323s | 2.214s | 13.21 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | multi_image_3x512px | 0.624s | 2.605s | 11.96 tokens/s | LEGACY_REVALIDATED |
| Qwen3.5_122B_A10B_GPTQ_Int4 | text_only | 0.339s | 2.477s | 13.76 tokens/s | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | image_1024px | 0.321s | 1.726s | 23.00 tokens/s | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | image_256px | 0.580s | 1.875s | 22.47 tokens/s | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | multi_image_3x512px | 0.911s | 2.021s | 22.45 tokens/s | LEGACY_REVALIDATED |
| google_gemma_4_26b_a4b_it | text_only | 0.242s | 1.301s | 23.05 tokens/s | LEGACY_REVALIDATED |
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

</details>
