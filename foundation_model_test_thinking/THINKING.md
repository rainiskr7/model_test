# THINKING.md — thinking(추론) 파이프라인 설계 노트

이 폴더는 `foundation_model_test_non_thinking` 를 **추론(thinking) 모델**에 맞게 적응한 변형이다.
non-thinking 버전은 모델이 추론 트레이스를 내지 않는다고 가정해 만들어졌으나, thinking 모델은
최종 답 앞에 긴 추론을 낸다. 그 가정이 깨지는 모든 지점을 아래처럼 바꿨다.

## 0. 추론 출력 형태 — 둘 다 견고하게 처리

thinking 모델 출력은 서버 설정에 따라 두 형태로 온다. 평가 코드는 **둘 다** 처리한다:

- **(a) `--reasoning-parser` 분리**: 서버가 추론을 `message.reasoning_content` 로 빼고,
  `message.content` 엔 최종 답만 → 그대로 채점.
- **(b) 인라인 `<think>...</think>`**: 분리 없이 content 안에 추론 포함 → 정규식으로 strip.

핵심 유틸은 트랙별 `reasoning.py` 모듈에 **기능 분리**되어 있다(단일 책임):
- `shared/multimodal/benches/reasoning.py` — `split_reasoning`, `message_content_and_reasoning`
- `shared/nlu/reasoning.py` — dict 응답용
- `shared/agent/gpustack_custom/reasoning.py` — 객체 응답용
- 객관식/자유서술형 답 추출: `shared/multimodal/benches/answer_parse.py`
  (`extract_choice`, `extract_final_answer` — k_mmbench/k_dtcbench/mtvqa 공유, 중복 제거)
- KRETA 는 외부 repo 패치라 `_strip_think` 를 패치 안에 인라인.

`split_reasoning` 규칙: 닫힌 `</think>` 가 있으면 *마지막 `</think>` 뒤*만 최종 답으로,
열린 채 잘렸으면 그 앞만(대개 빈 답). 답 추출은 **정답 마커의 마지막 매치**를 우선해
추론 중간에 흩어진 A/B/C/D 가 먼저 잡히던 non-thinking 시절 오답을 막는다.

## 1. Sampling — 모델별 권장값 (greedy 금지)

non-thinking 은 전부 `temperature=0.0`(greedy)였다. Qwen 은 thinking 모드에서 greedy 가
반복·퇴화를 유발한다고 명시 경고 → 권장 sampling 으로 전환.

- 공통 기본값: `temperature=0.6`, `top_p=0.95`, `top_k=20`, `seed=42`(재현성).
- **모델별 override**: `configs/models/<model>.yaml` 의 `sampling:` 블록.
  `load_model_config.py` 가 이를 `THINK_*` env 로 export → 모든 트랙이 읽음.
- 모든 값은 env 로도 override: `THINK_TEMPERATURE / THINK_TOP_P / THINK_TOP_K /
  THINK_MAX_TOKENS / THINK_SEED / THINK_TIMEOUT`.
- `top_k` 는 OpenAI 표준이 아니라 vLLM `extra_body`(SDK)/body(raw)로 전달.
- thinking 토글이 없는 Qwen3.5-27B·Gemma 4 는 각자 권장값(Gemma temp 1.0/top_k 64 등)으로
  두되 CoT 프롬프트 baseline 으로만 해석.

## 2. 생성 상한 / timeout — 크게

추론 트레이스가 수천 토큰이므로 작은 상한은 답을 자른다.
- 멀티모달 `chat_with_image` 기본 `max_tokens` 512 → 2048(+`THINK_MAX_TOKENS`),
  `timeout` 60 → 600.
- nlu 8192 → 16384, agent 16384 유지, harness CoT `max_gen_toks` 8192.
- KRETA `default` 모드 4096 → 8192.

## 3. 프롬프트 — '바로 답' 대신 추론 허용 + 마커

객관식/단답 프롬프트의 "바로 답하세요"는 추론과 충돌 → "단계별로 추론한 뒤 마지막 줄에
'정답: X' 형식으로" 로 변경(k_mmbench/k_dtcbench/mtvqa). 답은 마커로 추출.

## 4. harness/KMMLU — 생성기반 CoT 신설 (가장 큰 변경)

기본 KMMLU(`output_type: multiple_choice`)는 **loglikelihood** 채점이라 프롬프트와 보기 사이에
추론이 들어갈 자리가 **구조적으로 없다**(thinking 측정 불가). upstream `kmmlu/direct` 는
`until: ["\n\n", "."]` 라 `<think>` 첫 줄바꿈에서 즉시 잘린다.

→ `shared/harness/tasks_thinking/` 에 **생성기반 CoT 변형**을 신설:
- `_kmmlu_think_template.yaml`: `generate_until`, `until: ["질문:"]`(추론 안 끊음),
  `max_gen_toks` 큼, 답은 filter(`정답[\s:]*\(?\s*([ABCD])`, group_select=-1)로 추출.
- 45개 과목 leaf `kmmlu_think_<subject>.yaml`(`HAERAE-HUB/KMMLU` 전체, zero-shot CoT).
- `run_harness.sh` 는 `local-chat-completions`(생성) + `--include_path tasks_thinking` +
  `--gen_kwargs`(THINK_*)로 호출. 서버측 chat template(enable_thinking)이 추론을 켠다.

> ⚠️ 이 경로는 loglikelihood 가 아니라 **생성+정답추출**이므로 점수의 절대값은 non-thinking
> logprob MC 와 직접 비교 불가. thinking 내부 비교용으로 해석할 것.

## 5. KRETA — direct 모드 비사용

`direct` 모드는 1토큰(32) 답 강제라 추론과 근본 비호환. thinking 파이프라인은 `default`
(추론 후 'Answer: LETTER') 사용, 생성 상한 8192. patch(`kreta_infer_gpt.patch`)가
sampling(`KRETA_*`/`THINK_*`) 주입 + 응답 `<think>` strip 후 `evaluate.py` 에 넘김.
`direct` 를 지정하면 경고만 내고 진행(권장 안 함). 패치는 `git apply --recount` 로 적용.

## 6. agent — 추론 JSON 오인 방지

tool-call 을 plain-text content 에서 정규식으로 뽑는데, 추론 안의 tool_call 모양 JSON 이
오인될 수 있어 **content 는 추론 strip 후** 파싱하고 추론은 `reasoning_content` 로 보존.

## 환경변수 요약

| env | 기본 | 의미 |
|---|---|---|
| `THINK_TEMPERATURE` | 0.6 | sampling 온도 |
| `THINK_TOP_P` | 0.95 | nucleus |
| `THINK_TOP_K` | 20 | top_k (0 이하면 미전달) |
| `THINK_MAX_TOKENS` | 8192 | 생성 상한(추론+답) |
| `THINK_SEED` | 42 | 재현성 seed |
| `THINK_TIMEOUT` | 600 | 요청 timeout(초) |
| `KRETA_TEMPERATURE/TOP_P/TOP_K` | THINK_* | KRETA 전용 override |

`run_full_eval.sh <model_config>` 실행 시 yaml `sampling:` → `THINK_*` 자동 export.
