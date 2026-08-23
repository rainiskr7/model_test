# agent 트랙 결과

이 파일은 `report_agent_tracks.py` 가 산출물에서 생성한다. 손으로 고치지 말 것 — 다시 생성하면 덮어써진다.

발행 가능 **19** / 거부 **10**. 판단 기준은 [`AGENT_TRACK_CLOSEOUT.md`](AGENT_TRACK_CLOSEOUT.md).

## 발행 가능한 수치 (축별 대표 런)

| 트랙 | 모델 | 런 | 축 | 결과 | 상태 |
|---|---|---|---|---|---|
| functionchat | google_gemma_4_26B_A4B_it | fcfull_20260823 | exact | 599/670 = 0.8940 | 확정 |
| functionchat | google_gemma_4_26B_A4B_it | fcfull_20260823 | judged | 598/636 = 0.9403 | PROVISIONAL — 판정기 기준, 인간 검증 없음 |
| functionchat | qwen_qwen3.5_35b_a3b_fp8 | fcfull_20260823 | exact | 618/670 = 0.9224 | 확정 |
| functionchat | qwen_qwen3.5_35b_a3b_fp8 | fcfull_20260823 | judged | 544/636 = 0.8553 | PROVISIONAL — 판정기 기준, 인간 검증 없음 |
| taubench | google_gemma_4_26B_A4B_it | tbair_20260823 | airline | 10/20 = 0.5000 | 확정 |
| taubench | google_gemma_4_26B_A4B_it | tbretail_20260823 | retail | 22/29 = 0.7586 | 확정 |
| taubench | qwen_qwen3.5_35b_a3b_fp8 | tbair_20260823 | airline | 17/20 = 0.8500 | 확정 |
| taubench | qwen_qwen3.5_35b_a3b_fp8 | tbretail_20260823 | retail | 21/29 = 0.7241 | 확정 |
| taubench | qwen_qwen3.5_35b_a3b_fp8 | tbfix_20260823 | telecom | 36/40 = 0.9000 | 확정 |

## 발행 불가 — 점수를 인용하지 마십시오

- **google_gemma_4_26B_A4B_it / fc670_20260823 / functionchat**
  - 게이트 기록 없음 — 현재 채점 계약으로 재채점되지 않는 낡은 산출물
- **qwen_qwen3.5_35b_a3b_fp8 / fc670_20260823 / functionchat**
  - 게이트 기록 없음 — 현재 채점 계약으로 재채점되지 않는 낡은 산출물
- **google_gemma_4_26B_A4B_it / tb_std_20260820 / taubench**
  - by_domain.telecom: 40건 중 27건만 측정됐다 — 부분 실행이다
  - by_domain.telecom: 완주 실패 13건 (environment=13) — 완전 측정이 아니다
- **google_gemma_4_26B_A4B_it / tb_std_m8k_20260820 / taubench**
  - overall.pass_rate 가 없다 — 보상값을 낸 태스크가 하나도 없다
  - by_domain.telecom.status = not_measured (no upstream records had a runnable numeric reward)
  - by_domain.telecom: 완주 실패 40건 (environment=40) — 완전 측정이 아니다
- **google_gemma_4_26B_A4B_it / tb_std_m8k_20260823 / taubench**
  - by_domain.telecom: 40건 중 38건만 측정됐다 — 부분 실행이다
  - by_domain.telecom: 완주 실패 2건 (candidate=2) — 완전 측정이 아니다
- **google_gemma_4_26B_A4B_it / tb_std_t300_20260820 / taubench**
  - by_domain.telecom: 40건 중 33건만 측정됐다 — 부분 실행이다
  - by_domain.telecom: 완주 실패 7건 (environment=7) — 완전 측정이 아니다
- **google_gemma_4_26B_A4B_it / tb_std_t900_20260820 / taubench**
  - by_domain.telecom: 40건 중 27건만 측정됐다 — 부분 실행이다
  - by_domain.telecom: 완주 실패 13건 (candidate=3, environment=10) — 완전 측정이 아니다
- **google_gemma_4_26B_A4B_it / tbfix_20260823 / taubench**
  - by_domain.telecom: 40건 중 39건만 측정됐다 — 부분 실행이다
  - by_domain.telecom: 완주 실패 1건 (unclassified=1) — 완전 측정이 아니다
- **qwen_qwen3.5_35b_a3b_fp8 / 20260819_215159 / taubench**
  - overall.pass_rate 가 없다 — 보상값을 낸 태스크가 하나도 없다
  - by_domain.telecom.status = not_measured (no upstream records had a runnable numeric reward)
  - by_domain.telecom: 완주 실패 40건 (environment=40) — 완전 측정이 아니다
- **qwen_qwen3.5_35b_a3b_fp8 / 20260819_215732 / taubench**
  - overall.pass_rate 가 없다 — 보상값을 낸 태스크가 하나도 없다
  - by_domain.telecom.status = not_measured (no upstream records had a runnable numeric reward)
  - by_domain.telecom: 완주 실패 40건 (environment=40) — 완전 측정이 아니다

## 읽는 법

- 분자/분모를 함께 본다. 반올림된 점수만으로는 표본 크기가 사라진다.
- **축을 합산하거나 평균하지 않는다.** 서로 다른 능력을 잰다.
- PROVISIONAL 은 인간 검증 전이다. 정답률이 아니라 판정기 기준 점수다.
- 거부된 런의 숫자는 존재하더라도 인용하지 않는다.
