# diffusiongemma 26B A4B — 현행 비교 라운드 결과 정리 (2026-10-11)

서빙: 22c3, vLLM 0.28.0, 원본 chat_template.jinja(sha256 앞 16 `9aeb7eac68ad87bb`), tool-call-parser gemma4, enable_thinking=false, reasoning parser 없음.
서빙 제약(configs/serving_profiles/vllm_diffusion.yaml): temperature·seed 등 거부 → 제거, 출력 상한 4096. **결정론 제어 수단이 없다 — 점수는 반복 산포와 함께 읽는다.**

## 세션
| 세션 | 분류 | 내용 |
|---|---|---|
| 20260830_222550_r1, 20260830_222550_r2, 20260907_001502_r3 | 본 | nlu · functionchat · taubench(solo) · multimodal 3회 |
| tbstd4_20261011 | 보조 | taubench standard×4 (5개 모델 공통 비교 조건) |
| 각 본 세션의 `language/taubench.badseed_20260908` | 무효 | 격리된 결과 — 리포트 도구가 읽지 않음 |
| p0verify_20260816, smoke_20260812_234414, v4run_20260817, v4run2_20260817 | 실험 | agent 트랙 시험 |
| (없음) | 측정 불가 | KMMLU — 확산 엔진이 echo+logprobs 요청에 죽어 확률 채점 불가(커밋 0140030, logs/kmmlu_protocol_diag_20261010) |

## 점수
| 트랙 | r1 | r2 | r3 | 비고 |
|---|---|---|---|---|
| functionchat 전체 | 89.4% (599) | 90.0% (603) | 89.4% (599) | singlecall 88.2/88.8/88.2, call_decision 94/95/95, dialog 91.4/91.4/90.0 |
| nlu carwash (정답 drive) | walk ✗ | depends ✗ | walk ✗ | 3회 모두 오답 |
| nlu 짜장면 4항목 | 4/4 | 4/4 | 4/4 | sacrifice · male · inferred · unlikely |
| taubench solo (telecom 40) | 27.5% | 20.0% | 22.5% | 매 회 16~17건이 '도구 호출 없이 응답'(no_tool_call)으로 중단 — 측정된 실패 |
| KRETA | | | | 3회 평균 83.73% (83.66–83.82) |
| K-MMBench | | | | 86.44% (86.26–86.56) |
| K-DTCBench | | | | 78.89% (77.50–80.00) — 흔들림이 정책 허용 초과 |
| MTVQA-KR | | | | 39.73% (38.89–40.68) — 흔들림이 정책 허용 초과 |
| KOFFVQA(판정기) | | | | 8.42/10 (8.33–8.56) — PROVISIONAL |
멀티모달 세부는 MULTIMODAL_TRACK_RESULTS.md.

### taubench standard×4 (tbstd4_20261011)
telecom 40 × 4회, 사용자 openrouter/openai/gpt-4.1-mini, 동시 4, 후보 요청 300s.
- **Pass^1 37.5% (60/160)** · pass^2 26.7% · pass^3 22.5% · pass^4 20.0% · 회차별 통과 15/14/18/13
- 종료 사유: 사용자 종료 118 · **빈 응답 중단 41 (26%)** · max_steps 1
- 빈 응답 중단 = 도구 결과 뒤 후보가 빈 메시지(생각 채널 표식만 또는 공백)를 내 tau2 가 `AssistantMessage must have either content or tool_calls` 로 시뮬레이션을 끝낸 것.
  채점은 이것을 측정된 실패 `empty_message@agent` 로 센다(shared/taubench/scoring/score_run.py, 10-11 추가). 빼고 세면 50.4%(60/119) — 그 숫자는 부풀려진 값이다.
- 같은 조건의 다른 모델: qwen3.8 BF16 58.75 · FP8 56.25 · gemma 4 26B 49.38(동시 1) · nemotron 4.38 (TAUBENCH_TRACK_RESULTS.md, protocol 275fbfbeabee9737)

## 템플릿 결정 (원본 유지)
수정 템플릿(생각 끔 때 도구 결과 뒤에도 빈 생각 블록을 넣는 nothink.jinja)을 서빙 단위 A/B 로 시험했다 — logs/resume_orch/diffusion_nemotron_prep/template_ab/analysis/report.md.
- 실패 사례 29건: 빈 응답 비율 51% → 26% (auto, 사례 개선 10·악화 0, p=0.002)
- 그러나 대조 40건에서 정상 도구 호출 95.5% → 91.5%, 여는 토큰 없이 `call:…<tool_call|>` 를 글로 내는 깨진 호출 0 → 4건. 사전 규칙(대조군 하락 ≤2%p) 위반 → **원본 유지**.
- gemma 4 26B 도 원본 템플릿으로 측정했으므로 비교 조건이 같다.

## 해석 시 주의
- 반복마다 결과가 달라진다(결정론 없음). 단일 런 숫자를 인용하지 말 것.
- taubench 점수의 약 4분의 1이 '빈 응답' 실패 유형이다 — 모델·템플릿 계열(gemma 4 와 같은 원본 템플릿)의 문제로 기록한다.
- 출력 상한 4096 은 서빙 제약이다(다른 모델은 16384).
