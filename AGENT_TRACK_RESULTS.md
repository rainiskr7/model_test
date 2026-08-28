# agent 트랙 결과

이 파일은 `report_agent_tracks.py` 가 산출물에서 생성한다. 손으로 고치지 말 것 — 다시 생성하면 덮어써진다.

발행 가능 **10** / 거부 **0**. 판단 기준은 [`AGENT_TRACK_CLOSEOUT.md`](AGENT_TRACK_CLOSEOUT.md).

## 발행 가능한 수치 (축별 대표 런)

| 트랙 | 모델 | 런 | 축 | 결과 | 상태 |
|---|---|---|---|---|---|
| functionchat | google_gemma_4_26B_A4B_it | fcfull_20260823 | exact | 599/670 = 0.8940 | 확정 |
| functionchat | google_gemma_4_26B_A4B_it | fcfull_20260823 | judged | 598/636 = 0.9403 | PROVISIONAL — 판정기 기준, 인간 검증 없음 |
| functionchat | qwen_qwen3.5_35b_a3b_fp8 | fcfull_20260823 | exact | 618/670 = 0.9224 | 확정 |
| functionchat | qwen_qwen3.5_35b_a3b_fp8 | fcfull_20260823 | judged | 544/636 = 0.8553 | PROVISIONAL — 판정기 기준, 인간 검증 없음 |

## 읽는 법

- 분자/분모를 함께 본다. 반올림된 점수만으로는 표본 크기가 사라진다.
- **축을 합산하거나 평균하지 않는다.** 서로 다른 능력을 잰다.
- PROVISIONAL 은 인간 검증 전이다. 정답률이 아니라 판정기 기준 점수다.
- 거부된 런의 숫자는 존재하더라도 인용하지 않는다.
