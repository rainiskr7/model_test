# 인계 문서 — agent 트랙 (2026-08-19)

## 0. 먼저: 직전 "Ko-AgentBench 오용" 분석은 대부분 무효다

그 분석은 `results/*/*/language/agent/` 를 읽었다. **2026-05~07 의 레거시 산출물**이고
이번 세션들에서 고친 것이 하나도 반영돼 있지 않다. 현재 트랙은
`language/agent_v4run/` (및 agent_p0verify / agent_l2fix / agent_cohort2) 다.

| 확인 | 레거시 `agent/` | 현행 `agent_v4run/` |
|---|---|---|
| 디렉토리 수 | 18 | 25 |
| `metadata.timestamp` | 2026-05-03 ~ 07-23 | 2026-08-16~18 |
| `native_tool_calling` | (기록 없음, 기본 False) | **True** (미스분류 있는 22런 전부) |
| `total_tool_calls > 0` | 0 / 126 | **63 / 70** |

그래서 "툴이 단 한 번도 실행되지 않았다 (91/91)" 는 **폐기된 아티팩트에 대한 참**이고
현행 트랙에 대해서는 거짓이다. 그 위에 쌓은 "결과 전체 무효", "지금 점수 게시 중단",
"전체 재실행" 도 같이 무너진다.

이전 세션이 낸 캐시 미스 결론(64~69%)과 충돌하는 것처럼 보였던 이유가 이것이다.
**두 분석이 서로 다른 런 세트를 봤다.** 미스 분류를 가진 파일 22개는 전부 v4run 계열이고,
레거시 `agent/` 에는 `query_absent` 키가 0건이다.

## 1. 3개 주장 중 살아남은 것

**주장① 정규식 툴콜 파서가 깨져 있다 — 역사적으로 사실이나 이미 수정됨.**

`ef38a8c^` 시점의 `openai_compat_adapter.py:216-230` 에 문제의 non-greedy 정규식이
실재했다. **이미 교체됐다** — `shared/agent/gpustack_custom/tool_call_parser.py` (2026-08-17)
가 `json.JSONDecoder().raw_decode()` + 역방향 중괄호 탐색을 쓰고 어댑터가 :21 에서
`from .tool_call_parser import contains_tool_call_candidate, extract_tool_calls` 로 쓴다.
→ **조치 불필요.** (2026-08-19 초안에서 "고칠 것" 이라고 쓴 것은 오류였다.)

다만 **텍스트 모드로 떨어지는 설정 위험은 남는다.** 어댑터 기본값은 여전히 False
(`openai_compat_adapter.py:101`). 정상 경로에서는
`run_gpustack_benchmark_with_logging.py:834` 가 `AGENT_NATIVE_TOOL_CALLING` 을 전파하고
`configs/load_model_config.py:192` 가 모델 설정에서 그 값을 내보낸다. 그러나
**README.md:134 의 단독 실행 예시는 모델 설정을 source 하지 않는다** — 깨끗한 셸에서
그 예시를 그대로 따라 하면 텍스트 모드가 선택된다. 문서를 고칠 것.

(참고: FunctionChat 0.922 → 0.837 텍스트 모드 저하는 **미검증으로 격하**. 해당 아티팩트가
삭제돼 현재 체크아웃에서 재확인 불가. 저장된 native 런은 0.9217.)

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

- **L1/L2 포화** — 태스크 부족 + 이진 지표 + 문항 결함. L2 는 태스크 15개에 in-score
  지표가 SelectAcc **하나뿐**이라 1문항 = 6.7%. v4run 분포는 0.9333×8 + 0.8667×2
  (= 14/15 와 13/15). SelectAcc 는 첫 골든 툴 vs 첫 호출 툴의 이진 완전일치다
  (`data/Ko-AgentBench/bench/runner/metrics.py:972,978`).
  공통 오답은 **L2-015**: 지시문은 "개정된 부동산 세법 검색" 인데 골든이 `WebSearch_daum`
  이고 다른 검색 툴이 여럿 노출돼 있다 — 모델은 `NewsSearch_naver` 를 골랐다.
  **문항이 미결정이다.** 계측기 사망도 프로젝트 구현 결함도 아니며 1.0 이 불가능하지도
  않다. 변별력 부족으로 부르는 게 정확하다.
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
3. **README.md:134 단독 실행 예시 수정** — 모델 설정을 source 하지 않아 텍스트 모드로
   떨어진다. 파서 자체는 이미 고쳐져 있다.
4. **판정 계층 결정** — FunctionChat 미측정 551건(slot 406 되묻기 / relevance 100 거절 /
   Dialog 45 다중턴) + τ-bench retail·airline. **이게 곧 깊이다.**

## 5. 방법론 교훈 (반복하지 말 것)

- **산출물을 읽기 전에 그게 어느 런 세트인지 확인할 것.** 이번 오진의 전부다.
  `results/*/*/language/agent/` 와 `agent_v4run/` 은 3개월 차이다.
- **세대 판정에 mtime 을 쓰지 말 것.** 레거시 파일 mtime 이 2026-08-16 으로 찍혀 있는데
  `metadata.timestamp` 는 2026-05-03 이다. 임베디드 timestamp 가 유일하게 믿을 근거다.
- **인용된 파일이 실제로 존재하는지 볼 것.** 원 분석의 2층 주장 전체가
  `report_tools/extract.py:79-84` 에 기대는데 레포에 그 파일이 없다.
- 리뷰어(codex/grok) 주장은 직접 재검증할 것. 이번 세션들에서 양쪽 다 최소 한 번씩 틀렸다.
- 결과 디렉토리 대소문자: macOS 가 대소문자를 구분하지 않아
  `results/google_gemma_4_26B_A4B_it/` 에 소문자 런이 섞여 들어갔다. **리눅스에서 갈라진다.**
