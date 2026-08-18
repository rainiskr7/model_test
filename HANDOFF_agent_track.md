# 인계 문서 — agent 트랙 (2026-08-19)

## 0. 먼저: 직전 "Ko-AgentBench 오용" 분석은 대부분 무효다

그 분석은 `results/*/*/language/agent/` 를 읽었다. **2026-05~07 의 레거시 산출물**이고
이번 세션들에서 고친 것이 하나도 반영돼 있지 않다. 현재 트랙은
`language/agent_v4run/` (및 agent_p0verify / agent_l2fix / agent_cohort2) 다.

| 확인 | 레거시 `agent/` | 현행 `agent_v4run/` |
|---|---|---|
| 디렉토리 수 | 18 | 25 |
| mtime | 2026-05-03 ~ 07-04 | 2026-08-16~18 |
| `native_tool_calling` | (기록 없음, 기본 False) | **True** (미스분류 있는 22런 전부) |
| `total_tool_calls > 0` | 0 / 126 | **63 / 70** |

그래서 "툴이 단 한 번도 실행되지 않았다 (91/91)" 는 **폐기된 아티팩트에 대한 참**이고
현행 트랙에 대해서는 거짓이다. 그 위에 쌓은 "결과 전체 무효", "지금 점수 게시 중단",
"전체 재실행" 도 같이 무너진다.

이전 세션이 낸 캐시 미스 결론(64~69%)과 충돌하는 것처럼 보였던 이유가 이것이다.
**두 분석이 서로 다른 런 세트를 봤다.** 미스 분류를 가진 파일 22개는 전부 v4run 계열이고,
레거시 `agent/` 에는 `query_absent` 키가 0건이다.

## 1. 3개 주장 중 살아남은 것

**주장① 정규식 툴콜 파서가 깨져 있다 — 부분적으로 유효. 고칠 가치 있음.**

`shared/agent/gpustack_custom/openai_compat_adapter.py:101` 에서 `native_tool_calling`
기본값이 False 이고, :120 에서 False 면 프롬프트 주입 + 정규식 경로를 탄다. 그 정규식은
non-greedy 라 `name → arguments` 순서에서 닫는 중괄호가 하나 모자란다.

현행 런은 True 라 이 경로를 안 탄다. 하지만 **죽은 코드가 아니다** — 실측 증거가 있다:
FunctionChat 반복 때 env 가 서브셸로 전파 안 돼 텍스트 모드로 떨어졌고 같은 모델이
0.922 → 0.837 이 나왔다. 즉 이 경로는 조용한 성능 저하 경로로 실재한다.

고칠 것: 균형 파서로 교체(`json.JSONDecoder().raw_decode()` 기반, 검증됨) + 기본값을
True 로 올리거나 최소한 False 로 떨어질 때 경고를 남길 것.

**주장② success 가 정답이 아니라 생존 체크다 — 사실이나 이미 처리됨.**

`aggregate.py:887` 에 이미 주석이 있다: *"기존 metadata.success_rate. 정답률이 아니라
'final_response 반환 + step>=1'"*. 현행 채점기는 이걸 점수로 안 쓰고 ToolAcc / CallEM /
ArgF1 / SelectAcc / FSM / PSM 을 직접 계산한다. `validate_run.py:364` 는 오히려
success_rate==1.0 인데 level_score≠1.0 이면 잡아내는 **sanity check** 로 쓴다.
→ 조치 불필요.

**주장③ 공식 `evaluate_model_run.py` 를 안 부른다 — 사실이나 오용은 아니다.**

참조 0건이 맞다. 다만 `shared/agent/scoring/context.py:21` 이
*"Return task_schema/logs using the same keys as evaluate_model_run.py"* 라고 밝힌다.
**호출 대신 재구현했다.** 설계 선택이지 누락이 아니다.

단 남는 실제 리스크: 그 재구현이 업스트림과 대조 검증된 적이 없다. 하려면
동일 로그 한 벌에 양쪽을 돌려 지표를 비교하는 것이지, 파이프라인을 갈아끼우는 게 아니다.

## 2. 그래서 L1/L2 포화와 L7 미측정의 진짜 원인은 (이전 세션 결론이 유효)

- **L1/L2 포화** — 태스크가 쉽고 수가 적다(L2 10~15개). L2 는 9모델 중 7개가 정확히
  0.933. 계측기가 죽어서가 아니라 천장에 닿았다.
- **L3/L4 붕괴** — 픽스처 캐시 키가 `sha256(tool, 정규화 인자, signature)` 인데 인자
  정규화가 텍스트를 안 건드려, 모델이 다르게 표현하면 무조건 미스. 호출의 64~69%.
  한국어 문제 아님(영어 미스 사례 존재, semantic_mismatch 83.1% 가 순수 수치/구조).
- **L7 미측정** — 지표가 100% LLM Judge 기반. 판정 모델을 안 붙였다. 10태스크 중 7개
  record-only.
- **L6** — RedundantCallRate 가 seed_replay 와 구조적으로 안 맞음(과거 호출이
  action_trace 에 없어 중복 재호출해도 1.0). 업스트림 설계 결함.

## 3. 현재 상태

Ko-AgentBench 는 `run_full_eval.sh` 에서 진입점만 주석 처리(커밋 `2bdcbf4`).
파일·결과·채점 코드·진단은 전부 보존. 대체 트랙 둘을 만들었다.

| 트랙 | 축 | 상태 |
|---|---|---|
| `shared/functionchat/` | 한국어 첫 호출 | 구현 완료, **2모델 실측** |
| `shared/taubench/` | 언어중립 다단계 | 구현 완료, **모델 실측 미완** |

FunctionChat 실측(native tool calling): qwen3.5-35b-a3b-fp8 0.922 / gemma-4-26b-a4b 0.893.
차이 0.029 — 반복 없이 능력이라 부를 수 없음.

## 4. 다음 세션 할 일 (우선순위)

1. **τ-bench 실제 완주** — 공식 `test` 분할 40건. 배선만 검증됐고 결과가 없다.
2. **FunctionChat 반복 3회** — `AGENT_NATIVE_TOOL_CALLING=1` 을 명시적으로 export
   (`source <(...)` 로는 전파 안 됨 — 이미 한 번 당함). 0.029 가 노이즈인지 판정.
3. **어댑터 정규식 파서 수정** — 위 주장① . 조용한 저하 경로 제거.
4. **판정 계층 결정** — FunctionChat 미측정 551건(slot 406 되묻기 / relevance 100 거절 /
   Dialog 45 다중턴) + τ-bench retail·airline. **이게 곧 깊이다.**

## 5. 방법론 교훈 (반복하지 말 것)

- **산출물을 읽기 전에 그게 어느 런 세트인지 확인할 것.** 이번 오진의 전부다.
  `results/*/*/language/agent/` 와 `agent_v4run/` 은 3개월 차이다.
- 리뷰어(codex/grok) 주장은 직접 재검증할 것. 이번 세션들에서 양쪽 다 최소 한 번씩 틀렸다.
- 결과 디렉토리 대소문자: macOS 가 대소문자를 구분하지 않아
  `results/google_gemma_4_26B_A4B_it/` 에 소문자 런이 섞여 들어갔다. **리눅스에서 갈라진다.**
