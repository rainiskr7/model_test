# agent 트랙 종료 보고 (2026-08-23)

이 문서가 **어떤 숫자를 믿어도 되는지에 대한 유일한 기준**이다. 결과 디렉토리에는
거부된 런과 진단용 런이 섞여 있으므로, 여기 없는 숫자는 인용하지 않는다.

**다만 문서는 무시할 수 있다.** 실제로 게이트가 거부한 gemma telecom 0.4615 를 요약
파일만 보고 여러 차례 인용했다. 그래서 규칙을 코드로 옮겼다:

```
python3 report_agent_tracks.py            # 발행 가능한 수치만 출력
python3 report_agent_tracks.py --strict   # 거부된 런이 있으면 exit 1 (CI)
```

이 도구는 `publish_status.publishable != true` 인 런의 **점수를 출력하지 않는다.**
판정 축에는 인간 검증 전까지 자동으로 PROVISIONAL 딱지가 붙는다. 수치를 인용할 때는
`summary.json` 을 직접 읽지 말고 이 도구를 쓴다 — 직접 읽는 것이 이번 오류의 경로였다.

## 요약

Ko-AgentBench 를 폐기하고 두 트랙으로 교체했다. 파이프라인 배선까지 끝났고
`run_full_eval.sh` 의 `tracks` 에 들어 있다. 아래 표의 `publishable` 만 인용 가능하다.

---

## 1. 발행 가능한 수치

산출물의 `publish_status.publishable == true` 인 것만 싣는다. 소수점만이 아니라
**분자/분모**를 함께 적는다.

### FunctionChat (kakao/FunctionChat-Bench @ 5ddb0b5)

| 축 | qwen3.5-35b-a3b-fp8 | gemma-4-26b-a4b | 상태 |
|---|---|---|---|
| exact 670 | 618/670 = 0.9224 | 599/670 = 0.8940 | **publishable** |
| judged 636 | 544/636 = 0.8553 | 598/636 = 0.9403 | **provisional** |

`judged` 가 provisional 인 이유는 §3 을 볼 것.

산출물: `results/<model>/fcfull_20260823/language/functionchat/{summary,judge}.json`

### tau2-bench (sierra-research/tau2-bench @ c339866)

표준 모드(agent-user-tools), 공식 test 분할, 고정 사용자 시뮬레이터
`openrouter/openai/gpt-4.1-mini` (temperature 0).

| 도메인 | qwen | gemma | 상태 |
|---|---|---|---|
| telecom | 36/40 = 0.9000 | **18/39 — REJECTED** | qwen만 publishable |
| retail | 21/29 = 0.7241 | 22/29 = 0.7586 | **publishable** |
| airline | 17/20 = 0.8500 | 10/20 = 0.5000 | **publishable** |

산출물: `results/<model>/{tbfix,tbretail,tbair}_20260823/language/taubench/summary.json`

---

## 2. 거부된 수치 — 인용 금지

**`gemma telecom 0.4615` 는 발행 불가다.** 게이트가 거부했다(exit 1):

```
40건 중 39건만 측정됐다 — 부분 실행이다
완주 실패 1건 (unclassified=1) — 완전 측정이 아니다
```

원인은 gemma 가 `content` 도 `tool_calls` 도 없는 빈 `AssistantMessage` 를 반환한 것이다.
후보 귀책일 가능성이 높으나 traceback 에 actor 근거가 없어 `unclassified` 로 남겼다.

**이 세션 중 이 숫자를 여러 차례 최종 수치로 인용했다. 그것은 오류였다.**
쓰려면 `18/39, 불완전 — 비교 불가` 로만 쓴다. 강행하려면 미완주를 실패로 세어
`18/40 = 0.4500` 이라 쓰고 그 판단을 명시한다.

그 외 진단용 런(설정 반복·스모크·solo 모드 실패)은 **2026-08-24 에 삭제했다** —
307MB. 그 과정에서 얻은 결론은 커밋 메시지와 이 문서에 남아 있고, 원본 궤적을 보관할
이유가 없었다. 삭제한 것:

```
fc670_20260823           커버리지 수정 이전 산출물, fcfull 로 대체
tb_std_20260820          120초 타임아웃 (13건 실패)
tb_std_t300_20260820     300초 타임아웃 (7건 실패)
tb_std_t900_20260820     900초 (ContextWindowExceeded 13건)
tb_std_m8k_20260820      서버 종료로 무효
tb_std_m8k_20260823      max_tokens=8192, tbfix 로 대체
20260819_215159/215732   solo 모드 (DummyUser 버그 / 서빙 제약)
```

**`gemma/tbfix_20260823` 은 남긴다.** 거부된 런이지만 유일한 gemma telecom 측정
시도이고, 위의 인용 금지 근거이며, 재개 시 "빈 출력이 재현되는지" 비교 대상이다.

---

## 3. 판정 축이 provisional 인 이유

**인간 라벨 검증을 하지 않았다.** 이 수치는 `gpt-4.1-mini` 루브릭 채점이지 정답률이 아니다.

특히 문제가 되는 이유는 **판정 축이 순위를 뒤집기 때문이다**:

```
exact   qwen 0.9224 > gemma 0.8940
judged  gemma 0.9403 > qwen 0.8553      <- 반대
```

차이는 `slot`(되묻기) 에 몰려 있다 — gemma 0.955 vs qwen 0.819. 그런데 exact 층에서
gemma 의 실패는 "무호출" 에 몰려 있었다(29 vs 12). **같은 행동을 두 축이 반대로
평가한다.** "gemma 가 정말 되묻기를 잘한다" 와 "판정기가 되묻기를 과대평가한다" 를
현재 수단으로 구분할 수 없다.

파일럿에서 확인한 것은 **일관성**뿐이다: 파싱 실패 0건, mini 자기 뒤집힘 3.3%,
mini vs gpt-4.1 불일치 1.7%. 두 판정기가 같은 방향으로 틀리면 이 검증은 통과한다.

또한 파일럿 표본은 qwen 출력만 썼으므로 **후보 의존적 판정 편향을 탐지할 수 없다.**

### 최소 검증 설계 (미실시)

- 모델 정체와 순서를 가린 **짝지어 블라인드 감사**
- `slot` 중심 + relevance/completion 소수
- "어느 쪽이 나은가" 가 아니라 **루브릭 기준 pass/fail**
- 한국어 검토자 1인 + 불일치 건 2인째
- 60쌍부터 시작, 순위가 불확실하면 확대
- 판정기와 일치한 사례도 무작위로 섞을 것 (공통 오판 탐지)

---

## 4. 커버리지 — 정확한 표기

"완결" 이라는 말은 쓰지 않는다. 분모를 밝힌다.

```
FunctionChat  응답 생성   1306/1306
              exact 채점   670/670
              판정 채점    636/636
tau2          원 test 태스크           100  (telecom 40 + retail 40 + airline 20)
              판정 불필요(실행 가능)     89
              qwen 측정                89/89
              gemma 측정               88/89  + 후보 오출력 1건
              retail 판정 필요로 제외    11/40
```

**"89/89" 는 gemma 에 대해 참이 아니다.** 시도 기준으로만 참이다.

---

## 5. 문서화된 한계 (고치지 않음)

| 한계 | 영향 |
|---|---|
| tau2 단일 시행 (`--num-trials 1`) | 궤적 변동 미측정. **retail 격차 0.03 은 1건 차이(22 vs 21)이므로 순위 주장 불가** |
| retail 11건 미측정 | 공식 tau2 판정기 미연결. retail 은 항상 29/40 으로 표기 |
| 판정 불안정 항목 | qwen 10, gemma 6. 과반은 성립하나 투표가 갈렸다 |
| 판정 투표 수 불균일 | 623건 2회 / 13건 5회 (qwen). `judge.votes_per_item` 에 실측 기록 |
| 낡은 산출물 | 600항목 시대 런은 dialog 커버리지 검사에서 거부된다. 정식 결과에서 제외 |
| 결과 경로 대소문자 충돌 | `google_gemma_4_26B_A4B_it` 와 소문자판이 macOS 에서 같은 디렉토리. **리눅스에서 갈라진다.** 소문자를 정본으로 한다 |

---

## 6. 허용되는 결론 / 금지되는 결론

**허용**

- 한국어 첫 호출(exact)에서 qwen 이 gemma 보다 낫다 (0.9224 vs 0.8940, 670항목)
- 다단계 실행 결과가 도메인마다 크게 다르다 — **단일 도메인으로 일반화하면 안 된다.**
  telecom(+0.44)과 airline(+0.35)은 qwen 우세로 읽어도 되지만, **retail 은 22 대 21,
  단 한 문제 차이라 순위를 말할 수 없다.**
- 판정 축은 exact 축과 반대 방향을 가리킨다 — **단, 판정기 기준이며 미검증**
- 사용자 시뮬레이터를 후보 자신으로 두면 측정이 오염된다 (qwen 0.475 -> 0.900)

**금지**

- `gemma telecom 0.4615` 인용
- 다섯 축을 합산하거나 평균해 단일 서열 발표
- exact 와 judged 를 더해 `1306` 분모의 단일 점수 발표
- retail 0.03 격차로 우열 주장
- 판정 축 수치를 "정답률" 로 서술

---

## 7. 재개 시 우선순위

1. **인간 블라인드 감사 60쌍** — 판정 축 순위 역전의 진위. 이것 없이는 §1 의 judged
   행을 provisional 밖으로 못 뺀다
2. gemma telecom 재실행 — 빈 출력 1건이 재현되는지. 재현되면 후보 귀책으로 분류
3. tau2 다중 시행 — 최소 3회. retail 격차의 유의성
4. ~~retail 11건 — tau2 공식 판정기 연결~~ — **폐기(WONTFIX)**

   retail 40건 중 11건은 nl_assertions 내용이 있어 공식 판정기가 필요하다. 붙이지
   않기로 했다. 이유는 커버리지가 아니라 **오염**이다:

   - 지금 retail 29건은 완전히 프로그램적이다(DB 상태 게이트). 판정 11건을 섞으면
     점수가 판정 조건부가 되는데, 읽는 사람에게 그 혼합이 보이지 않는다.
     정직한 `29/40` 보다 나쁜 숫자가 된다.
   - 공식 평가기는 DB 보상과 NL 보상을 **곱한다**(evaluator.py:241,249). 따라서 전체
     점수는 qwen 21~32/40, gemma 22~33/40 어디든 될 수 있다 — 어느 쪽 순위든 가능하다.
     즉 붙여도 순위를 확정하지 못한다.
   - 상류 자신이 NL assertion 을 experimental/WIP 로 표시한다(tasks.py:252).
   - 평가기에 결함도 있다: 판정 결과가 빈 목록이면 `all([])` 가 통과한다
     (evaluator_nl_assertions.py:46,127).
   - report_agent_tracks.py 는 tau2 축을 항상 non-provisional 로 출력한다(:80).
     판정만 붙이면 판정 조건부 결과가 '확정' 으로 찍힌다 — 보고 계층까지 고쳐야 한다.

   **잃는 것**: 공식 composite 커버리지, tau2 헤드라인과의 직접 비교, 그 11건에 대한
   질적 우열 정보. 그뿐이다. 현재 발행 중인 어떤 주장도 이것 없이 무너지지 않는다.
   retail 은 항상 `29/40` 으로 표기한다.

   더 싼 대안이 있긴 하다 — 40건 전부에 EvaluationType.ENV 로 DB 도달률만 재서
   `retail_db_goal_rate` 로 **별도 표기**하는 것. 절대 합치지 않는다는 조건에서만
   의미가 있다. 지금은 하지 않는다.

## 8. 이 트랙의 재현 방법

```
run_full_eval.sh <model_config>          # tracks 에 functionchat, taubench 포함
TAUBENCH_DOMAIN=retail|airline|telecom   # 기본 telecom
TAUBENCH_MODE=standard                   # solo 는 상류가 ablation 이라 부르는 변형
TAUBENCH_USER_MODEL=openrouter/openai/gpt-4.1-mini   # **후보와 달라야 한다**
TAUBENCH_USER_API_KEY                    # .env, 값은 CLI 로 넘기지 않는다
shared/functionchat/judge/run_judge.py   # 판정 층, exact 와 별도 산출물
```

Ko-AgentBench 는 `run_full_eval.sh` 에서 진입점만 주석 처리했다. 산출물·채점 코드·
진단은 전부 보존돼 있고 `report_agent_levels.sh` 도 동작한다.
