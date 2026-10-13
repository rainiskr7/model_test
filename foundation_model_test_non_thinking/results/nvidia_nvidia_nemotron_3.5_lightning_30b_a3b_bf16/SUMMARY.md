# nemotron 3.5 lightning 30B A3B (BF16) — 현행 비교 라운드 결과 정리 (2026-10-11)

텍스트 전용 모델(모델 카드 Input Type: Text) — multimodal 트랙은 대상 아님(configs/models/nvidia_nemotron_3.5_lightning_30b_a3b_bf16.yaml).
템플릿 기본값은 enable_thinking=True — 서빙에서 `--default-chat-template-kwargs {"enable_thinking": false}` 로 끈다. **모든 점수는 생각 모드를 끈 조건이다.**
10-10 이후 측정 서빙(audit_nvidia_..._20261010_0044 / _0311): 22c3, vLLM 0.28.0, reasoning-parser nemotron_v3, tool-call-parser qwen3_coder, 템플릿 58933db7.
08-30 본 측정의 서빙 인자는 기록이 없다(그때 run_manifest 에 vLLM 버전·템플릿이 남지 않음). 응답 530건에 reasoning·`<think` 가 0 이었다는 관측만 있다.

## 세션
| 세션 | 분류 | 내용 |
|---|---|---|
| 20260830_095747_r1, 20260830_123159_r1, 20260830_123159_r2 | 본 | nlu · functionchat · taubench(solo) 3회 |
| kmmlu_nothink_20261010_r1..r3 | 보조 | KMMLU 재측정 3회 (chat + 생각 끈 토크나이저 사본) |
| tbstd4_20261010 | 보조 | taubench standard×4 (5개 모델 공통 비교 조건) |
| 본 세션의 `language/harness.thinkopen_20261010` | 무효 | 생각 블록이 열린 chat 으로 잰 KMMLU(0.43) — 격리, 되돌리기: logs/kmmlu_protocol_diag_20261010/MOVED_harness_thinkopen.tsv |
| 095747_r1·123159_r1 의 `language/taubench.timeout_20260927` | 무효 | 격리된 이전 taubench |
| 095747_r1 의 `vision/multimodal` | 대상 아님 | 이미지 요청 8,129건 전부 400("not a multimodal model") — 발행 게이트가 REJECTED 로 막음, 집계에 안 들어감 |

## 점수
| 트랙 | r1 | r2 | r3 | 비고 |
|---|---|---|---|---|
| KMMLU (45과목, 5-shot, chat_nothink) | 0.5492 | 0.5486 | 0.5483 | 문항 가중. 과목 평균 0.5405 / 0.5393 / 0.5401. 진단 관문 통과(chat_nothink 0.492 vs completions 0.513, p=0.19) |
| functionchat 전체 | 78.1% (523) | 78.2% (524) | 77.9% (522) | singlecall 75.6/75.6/76.2, call_decision 88/87/85, dialog 81.4/84.3/80.0 |
| nlu (5항목) | 1 pass · 4 invalid | 0 · 5 invalid | 1 pass · 4 invalid | 답안 형식 위반 — 선택지 목록 `walk \| drive \| depends` 를 그대로 베껴 씀(invalid). 세차장 본문 답은 3회 모두 '걷기'(오답 방향) |
| taubench solo (telecom 40) | 10.0% | 10.0% | 5.0% | 40/40 agent_stop |

세션 순서: r1 = 20260830_095747_r1 / 20260830_123159_r1 / 20260830_123159_r2 (본), KMMLU 는 kmmlu_nothink_20261010_r1..r3.

### taubench standard×4 (tbstd4_20261010)
telecom 40 × 4회, 사용자 openrouter/openai/gpt-4.1-mini, 동시 4, 후보 요청 300s.
- **Pass^1 4.4% (7/160)** · pass^2 0.4% · pass^3·pass^4 0% · 회차별 통과 0/2/5/0
- 종료 사유: **too_many_errors 116** · max_steps 32 · user_stop 12. 측정 경로 오류·미측정 0, 도구 호출 3,475건 모두 파싱 정상.
- 실패 유형: 160개 대화 모두 첫 응답에서 고객에게 묻지 않고 전화번호를 지어내(`5551234567`, `(555) 123-4567` …) 조회 도구를 반복 호출 → "고객 없음" 오류 누적 → 중단.
  고객 쪽에만 있는 도구(`check_apn_settings` 등)를 부르기도 했다. 같은 조건의 gemma·qwen 은 첫 응답에서 계정 정보를 물었다.
- 같은 조건의 다른 모델: qwen3.8 BF16 58.75 · FP8 56.25 · gemma 4 26B 49.38(동시 1) · diffusiongemma 37.50 (TAUBENCH_TRACK_RESULTS.md, protocol 275fbfbeabee9737)

## 해석 시 주의
- 생각 모드를 끈 조건의 점수다. 이 모델은 생각 모드를 켜는 것이 기본값이라, 켠 상태의 성능은 이번 라운드 범위 밖이다(필요하면 별도 실험).
- nlu 는 형식 위반이 대부분이라 내용 판단의 근거가 되지 못한다.
- vLLM 0.30.0 은 thinking 구조가 달라 쓰지 않았다(비교 조건 0.28.0).
