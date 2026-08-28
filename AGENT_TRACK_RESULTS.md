# agent 트랙 결과

이 파일은 `report_agent_tracks.py` 가 산출물에서 생성한다. 손으로 고치지 말 것 — 다시 생성하면 덮어써진다.

발행 가능한 **런** 10개 / 거부 0개. 아래 표는 축별 대표 런만 보여주므로 행 수는 이보다 적다. 판단 기준은 [`AGENT_TRACK_CLOSEOUT.md`](AGENT_TRACK_CLOSEOUT.md).

> taubench 는 이 보고서에 없다. 사용자 시뮬레이터 프로토콜 고정 여부와 공식 split 커버리지를 보는 전용 계층이 판정을 갖는다 — `foundation_model_test_non_thinking/TAUBENCH_TRACK_RESULTS.md` (`report_taubench_tracks.py` 가 생성).

## 발행 가능한 수치 (축별 대표 런)

| 트랙 | 모델 | 런 | 축 | 결과 | 상태 |
|---|---|---|---|---|---|
| functionchat | google_gemma_4_26B_A4B_it | fcfull_20260823 | exact | 599/670 = 0.8940 | 확정 |
| functionchat | google_gemma_4_26B_A4B_it | fcfull_20260823 | judged | 598/636 = 0.9403 | PROVISIONAL — 판정기 기준, 인간 검증 없음 · 프로비넌스 없음(endpoint, served_identity, rubric_sha256) |
| functionchat | qwen_qwen3.5_35b_a3b_fp8 | fcfull_20260823 | exact | 618/670 = 0.9224 | 확정 |
| functionchat | qwen_qwen3.5_35b_a3b_fp8 | fcfull_20260823 | judged | 544/636 = 0.8553 | PROVISIONAL — 판정기 기준, 인간 검증 없음 · 프로비넌스 없음(endpoint, served_identity, rubric_sha256) |

## 재현성 (반복 실행)

**건수가 같다고 같은 측정이 아니다.** 통과한 **항목 집합**을 대조한다 — 실측으로 통과 건수가 5런 내내 동일한데 통과 항목이 10개 뒤집힌 사례가 있다.

- `google_gemma_4_26b_a4b_it` · `functionchat_exact_v1` — **DIVERGED**
  - 런 3개: `fc1_20260819`, `fcrep_a_20260819`, `fcrep_b_20260819`
  - 통과 건수 [536, 534, 537] (산포 3) · 항상 통과 533건
  - 런마다 뒤집힌 항목 6건
  - 통과 항목이 런마다 다르다 (6건). 건수가 같아도 다른 항목을 맞힌 것이면 같은 측정이 아니다
- `qwen_qwen3.5_35b_a3b_fp8` · `functionchat_exact_v1` — **DIVERGED**
  - 런 5개: `20260823_020522`, `fc1_20260819`, `fcrep_a_20260819`, `fcrep_b_20260819`, `fcrep_c_20260819`
  - 통과 건수 [553, 553, 553, 553, 553] (산포 0) · 항상 통과 548건
  - 런마다 뒤집힌 항목 10건
  - 통과 항목이 런마다 다르다 (10건). 건수가 같아도 다른 항목을 맞힌 것이면 같은 측정이 아니다
- `google_gemma_4_26b_a4b_it` · `functionchat_exact_v2` — **UNVERIFIED**
  - 런 1개: `fcfull_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다
- `qwen_qwen3.5_35b_a3b_fp8` · `functionchat_exact_v2` — **UNVERIFIED**
  - 런 1개: `fcfull_20260823`
  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다

## 읽는 법

- 분자/분모를 함께 본다. 반올림된 점수만으로는 표본 크기가 사라진다.
- **축을 합산하거나 평균하지 않는다.** 서로 다른 능력을 잰다.
- PROVISIONAL 은 인간 검증 전이다. 정답률이 아니라 판정기 기준 점수다.
- 거부된 런의 숫자는 존재하더라도 인용하지 않는다.
- 재현성은 **대표 런과 다른 코호트**일 수 있다. 대표가 `UNVERIFIED` 인데 다른 scoring_version 이 `DIVERGED` 라면, 발행 중인 수치에는 재현 근거가 없다는 뜻이다.
