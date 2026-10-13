# P1 계약 — 결정 모델 평가 코드의 입출력·채점·기록 규칙

작성 2026-10-13 · **판 3** (판 2 의 미정 필드 6곳을 채움 — Codex·grok 반박 반영) · 상태: 구현 중 (작업 ① 끝)
상위 문서: [`JEV_TEST_PLAN.md`](JEV_TEST_PLAN.md) 개정 13. 이 문서와 계획이 다르면 계획이 기준이고, 이 문서를 고친다.
범위: **첫 실행 = A 묶음 + B1** (계획 §7). B·C·T2·WorkflowEvals·B2 는 이 판에서 정하지 않는다. **score 질문은 이 판의 범위 밖**이다 (A 묶음에 없다) — 응답 검증기(§3-1)·채점은 score 를 만나면 `NotImplementedError` 로 멈추고, task yaml 검사기(§1-1)는 오류 목록에 넣는다.

이 문서는 코드를 쓰는 사람(Codex)이 **추측 없이** 구현할 수 있게 하는 것이 목적이다. 여기 없는 결정이 필요하면 구현하지 말고 `SPEC_AMBIGUOUS: <절> <내용>` 으로 보고한다.

---

## 0. 확인된 사실 (참조 구현·데이터 직접 확인, 10-13)

| 사실 | 근거 |
|---|---|
| Clef 는 state 가 문자열이면 그대로, 객체면 `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",",":"))` | `hf_cards/clef/joint_schema_model.py:35–43` |
| Clef 는 state 꼬리만 잘라 `상한 − 고정부` 에 맞춘다. 고정부(질문 스키마)만으로 넘으면 오류. 딱 맞는 입력은 안 잘려도 `usage.input_tokens == 상한` | `:162–170`, `:572–575` |
| Clef 는 질문을 요청 순서대로, choice 선택지는 ID 정렬 순으로, 선택지마다 `{"option_id", "description"}` 를 넣는다. noul 기본 설명은 영어. instructions 가 비면 질문 ID 를 지시문으로 쓴다 | `:46–57`, `:112–135` |
| Clef 응답 choice: `choice`(반올림 전 argmax)·`confidence`·`probabilities`, 4자리 반올림 | `:523–545` |
| pplx 요청은 `model`·`state`·`questions`(+`images`) 외 키 거부. choice 1–255. 알 수 없는 모델 이름·스키마 오류·추론 중 모든 `ValueError` 가 **422** | `hf_cards/pplx11/source_src_autojev_server.py:50–81`, `:152–156`, `:223–226` |
| pplx 서버는 요청 하나씩 — 바쁘면 529 + `Retry-After: 1`, 준비 전 503. temperature 는 서버가 `logits / T` 로 한 번 | `:205–228` |
| pplx 의 state 인코딩·8,192 초과 처리·반올림은 받은 파일에 없다 (`model.prepare`, `autojev.model.answer`) | **미확인** — P0 |
| FunctionChat 606행: 모든 행이 도구 5개(→ 선택지 6), 도구 이름 100종(행 안 중복 0, `NONE` 이름 0), call 100행 모두 도구 호출 1개·정답 도구가 그 행 `input_tools` 안 | 10-13 집계 (Claude·Codex 각각, 판 3 에서 Claude 재집계) |
| 첫 실행 6셋 모두 **성공 질문 정답이 빠진 행 0** — KoSGD USER 턴 42,297 · FunctionChat 606 · K-MHaS 21,939 · KOTE 5,000 · KorFin 8,818 · KLUE-MRC 5,841 | 10-13 Claude 집계 (로컬 사본, 일회성) |
| 길이: 6셋 모두 8,192 토큰 초과 0 (최대 KoSGD 4,902 — 감사 v3) | `audits/audit_v3`, 10-12 길이 측정 |
| K-MHaS 같은 문장 76 행 · 그중 라벨이 다른 묶음 1 · KorFin aspect 이름이 문장에 글자 그대로 없는 행 71 · KOTE 고른 감정 8개 양성 637–2,185 (test 5,000) | 10-13 Claude 집계 |

---

## 1. 설정 파일 (코드보다 먼저)

### 1-1. `configs/tasks/<set>.yaml` 스키마 (셋마다 하나, 동결 대상)

```yaml
set: kosgd                     # datasets.yaml 의 id
variant: full                  # 판이 있으면 판마다 파일 하나 (kosgd_full.yaml, kosgd_actions_only.yaml)
state:
  kind: json_string            # json_string | plain_text
  keys: [dialogue, catalog]    # json_string 일 때 키 순서 (이 순서로 직렬화, 정렬하지 않는다)
  target_key: dialogue         # json_string 일 때 '대상 발화' 가 있는 키 (§4-3). plain_text 는 쓰지 않는다
questions:                     # 순서 = 요청에 넣는 순서. per_item_questions 만 있는 셋은 [] 가능
  - id: ongoing_1              # ASCII snake_case, 정답 정보 없음
    role: success              # success | diagnostic
    type: choice               # noul | choice
    instructions: "..."        # 비울 수 없다
    options: catalog_intents_plus_none    # choice: 고정 목록 이름 | per_item (FunctionChat 도구처럼 항목마다)
    label: ongoing_slot_1      # 정답 규칙 이름 (score/labels.py 의 등록 함수 — 이름 전체가 키, ':' 로 쪼개지 않는다)
  - id: act_inform
    role: success
    type: noul
    instructions: "..."
    criteria: {"true": "...", "false": "..."}   # noul 은 항상 명시 (§2-3)
    label: act:INFORM
per_item_questions: null       # 항목마다 질문 수가 다른 셋 (KorFin) — 아래 형식
group_key: dialogue_id         # §6 묶음 키 규칙 이름
```
- **`per_item_questions`** (판 3): `{id_pattern: "aspect_{k}", role, type, instructions_template: "...{ASPECT}...", options | criteria, label}`. `k` 는 1부터, 원 데이터에 처음 나온 순서. `id_pattern` 은 `{k}` 를 정확히 한 번 담고, 펼친 ID 는 ASCII snake_case. 펼친 질문은 정적 `questions` 뒤에 붙는다. 정적 질문과 ID 가 겹치면 오류 — 검사는 `id_pattern` 의 `{k}` 앞뒤 문자열 + 양의 정수(앞자리 0 없음) 정규식으로 정적 ID 를 대조한다 (k 상한 없음). 실제로 펼칠 때도 중복을 다시 검사한다.
- 성공 질문 최소 1개 규칙은 **정적 `questions` 또는 `per_item_questions.role == success`** 로 만족한다 (판 2 검사기는 정적 질문만 봐서 KorFin 을 거부했다 — 작업 ②-0 에서 고친다).
- 고정 목록(예: KoSGD 카탈로그·의도 선택지, KorFin 감성 3개)은 `configs/tasks/lists/<name>.json` 에 실제 값으로 둔다. 코드는 목록을 만들지 않고 읽기만 한다 (목록 생성 스크립트는 따로, 라벨만 읽음).
- `options: per_item` 의 FunctionChat 도구 선택지는 **정규화한 `input_tools` 하나에서만** 만든다 (§6-2). `NONE` 설명은 `lists/functionchat_none.json`.
- `configs/tasks/b1.yaml`: B1 시스템 문구 · 사용자 문구 틀 · 라벨 문자열 62개 순서 · 생성 매개변수 (§2-5).
- yaml 은 **중복 키를 거부하는 로더**로 읽는다 (`datasets.yaml` 에서 실제로 중복이 있었다 — 10-13 고침).

### 1-2. 동결 해시
fingerprint 에는 **파일별** sha256 을 넣는다: 쓰인 task yaml 들 · 목록 json 들 · `b1.yaml` · 분할 파일 · 입력 데이터 파일 해시 목록 · **인코더 규칙** `encoder: {rule: <모델 yaml 의 규칙 이름>, sha256: <규칙 본문 해시>}` (판 3 — 호출 기록이 아니라 여기에 둔다, §4-3).

---

## 2. 요청 계약

### 2-1. 봉투
`{"model": <모델 yaml 의 served_name>, "state": <문자열>, "questions": {<id>: {...}}}` — 키는 이 셋뿐. 바이트 = `json.dumps(body, ensure_ascii=False, separators=(",", ":"))`, UTF-8. `request_sha256` 은 이 바이트로.

### 2-2. state 는 항상 문자열
- 이유: 모델마다 객체 state 를 렌더링하는 방식이 다르거나(Clef 는 키 정렬) 알 수 없다(pplx). 문자열로 보내면 **모든 모델이 같은 글자를 같은 순서로** 받는다. 계획 §1 도 state 를 "문자열 또는 JSON" 으로 허용한다.
- `json_string`: 내부 객체를 `keys` 순서로 `json.dumps(obj, ensure_ascii=False, separators=(",", ":"))`. `plain_text`: 원문 그대로.
- **render 의 출력** (판 3) = `Rendered(state: str, target_end_char: int)`. `target_end_char` = state 문자열 안에서 대상 발화가 끝나는 **문자 위치(끝 다음 칸, 0부터)**:
  - `json_string`: `target_key` 값이 목록이면 그 **마지막 원소**의 직렬화가 끝나는 위치(`}` 다음), 문자열이면 그 문자열 직렬화의 닫는 `"` 다음.
  - `plain_text`: `len(state)`.
  - 토큰 위치 $e$ 로 바꾸는 것은 `run/length.py` (인코더 규칙, P0).

| 셋 | kind | keys | target_key |
|---|---|---|---|
| KoSGD | json_string | `dialogue` (첫 턴~대상 USER 턴의 `{speaker, utterance}`), `catalog` (고정 목록) — `datasets.yaml` 이름 그대로 | `dialogue` (마지막 = 대상 USER 턴) |
| FunctionChat | json_string | `input_messages` (정규화), `input_tools` — `datasets.yaml` 이름 그대로 | `input_messages` |
| K-MHaS · KOTE · KorFin | plain_text | — | — |
| KLUE-MRC | json_string | `context`, `question` | `question` |

- 감사 v3 는 state 를 객체로 다뤘다(R4 가 dict·키를 검사, R7 이 `진행중_1/2` 를 하드코딩). 그래서 동결 때 **감사 v4** 를 따로 만든다: 실제 전송 문자열을 다시 파싱해 독립 원본과 비교하고, 길이는 서버 인코더 입력으로 잰다. 감사 v3 코드는 고치지 않는다 (보존본).

### 2-3. 질문
- 질문 ID·순서·instructions: task yaml 그대로 (펼친 질문은 §1-1). instructions 는 비우지 않는다.
- **noul 은 `criteria` 를 항상 명시**한다 (task yaml 의 한국어 `true`/`false` 설명). 모델 기본값은 모델마다 다르거나(Clef 영어) 알 수 없어(pplx) 같은 입력을 보장하지 못한다.
- choice `criteria` = `{선택지 ID: 설명}` — `Item.questions[].options` 그대로. 1–255 개, 선택지 ID 는 비지 않은 문자열(snake_case 규칙은 **질문 ID 에만** — `NONE`·`서비스/의도` 도 선택지 ID 다), 중복 금지, **`casefold()` 한 값도 서로 달라야 한다** (`NONE`·`none` 이 함께 있으면 오류). systemone 요청의 선택지는 **`options` 순서 그대로** 보낸다 (정렬하지 않는다 — Clef 는 자기가 정렬한다). 정렬은 B1 라벨 배정(§2-5)에서만, 파이썬 `sorted()` (코드포인트 순 — `NONE` 이 소문자 ID 앞) (판 3 보정 3·4).

### 2-4. 로컬 검증 (보내기 전)
봉투 키 · 타입 · 개수 · 빈 문자열 · ID 규칙 · 모델 이름이 모델 yaml 과 같은지. 실패하면 보내지 않고 `error/request_contract` (우리 버그).

### 2-5. B1 요청 (vLLM, 질문 하나당 호출 하나)
- `POST /v1/chat/completions`, `messages=[system, user]`, `chat_template_kwargs={"enable_thinking": false}`.
- 사용자 문구 = state 문자열 + `\n\n질문: ` + instructions + `\n` + 선택지 줄 + `\n답:`. 선택지 줄 = `<라벨>. [<선택지 ID>] <설명>` (Clef 처럼 ID 와 설명을 함께 보인다). noul 은 `A. [true] <true 설명>` / `B. [false] <false 설명>`.
- 라벨 배정: 선택지를 ID 정렬 순(noul 은 true, false)으로 놓고 `b1.yaml` 의 62개 라벨을 차례로. 대응표 `{label: option_id}` 를 호출 기록에 남긴다. 선택지 편향 검사(계획 §4-5)는 이 대응만 바꾼다.
- 매개변수: 계획 §2-3 그대로 (`max_tokens=1, logprobs=true, top_logprobs=선택지 수, temperature=1, top_p=1, top_k=-1, min_p=0, repetition_penalty=1, frequency_penalty=0, presence_penalty=0, allowed_token_ids=<라벨 토큰>`).
- 호출 단위: 질문마다 하나 (KoSGD 전체판 12 호출). 행동판은 B1 에서 따로 돌리지 않고 전체판 호출에서 가져온다 (§5-4).

---

## 3. 응답 계약

### 3-1. systemone 검증기 (결정 모델 공통)
JSON 파싱은 **중복 키 거부**(`object_pairs_hook`), `bool` 은 숫자로 인정하지 않는다. 사유 코드는 아래 순서로 처음 걸린 것 하나.

| 순서 | 검사 | 사유 코드 |
|---|---|---|
| 1 | 본문이 JSON 객체, `answers` 가 객체 | `bad_body` |
| 2 | `answers` 키 집합 == 요청 질문 ID 집합 | `qid_mismatch` |
| 3 | 답마다 `type` == 요청 type | `type_mismatch` |
| 4 | noul: `noul` 유한 실수, 0 ≤ p ≤ 1 | `noul_value` |
| 5 | choice: `probabilities` 키 == 선택지 ID 집합 | `choice_keys` |
| 6 | choice: 값 유한·0–1, \|합 − 1\| ≤ 선택지 수 × 5e-5 + 1e-9 | `choice_values` |
| 7 | choice: `choice` ∈ 선택지, \|`confidence` − `probabilities[choice]`\| ≤ 1e-9 | `choice_pick` |

- 최상위·답 객체의 **추가 키는 허용**하고 `extra_keys` 경고로만 남긴다 (`model`·`id`·`usage`·`provider` 등). `usage` 가 있고 null 이 아니면 객체여야 하고 `input_tokens` 는 정수(bool 제외)여야 한다 — 아니면 경고 `usage_input_tokens_invalid` (`usage` 가 없거나 null 이면 경고 없음). 경고는 중복을 빼고 처음 나온 순서로, 검증 실패(사유 코드)여도 그때까지 모은 경고를 함께 돌려준다 (판 3 보정 4).
- 검증은 요청 단위로 전부 아니면 전무다 — 질문 하나라도 실패하면 그 요청은 `error`, 나머지 질문 값도 채점에 쓰지 않는다 (§7-3).

### 3-2. 답과 확신 → `ParsedAnswer` (계획 §4-1·§4-2, 판 3)
**클래스 ID 는 항상 문자열**이다: noul 은 `"true"`/`"false"`, choice 는 선택지 ID. 답·정답·확률표 키가 같은 문자열을 쓴다 (bool 을 쓰지 않는다 — `probs[answer]` 가 그대로 된다).

| 경로 | `answer` | `probs` | `confidence` |
|---|---|---|---|
| systemone noul | `"true"` iff p ≥ 0.5 | `{"true": p, "false": 1 − p}` (p = 응답 `noul` 원값, 1−p 는 여기서 한 번만) | max(p, 1 − p) |
| systemone choice | 응답 `choice` | 응답 `probabilities` **그대로** (재정규화·재반올림 안 함) | 응답 `confidence` |
| B1 choice | 재정규화한 라벨 분포의 argmax, **동률이면 라벨 순서 앞** → 대응표로 선택지 ID | 재정규화 분포를 선택지 ID 키로 | 그 답의 확률 |
| B1 noul | `"true"` iff p ≥ 0.5 (p = 대응표에서 `true` 인 라벨의 재정규화 확률) — **라벨 순서로 동률을 깨지 않는다** (사용자 결정 10-13, 계획 개정 13) | `{"true": p, "false": 1 − p}` | max(p, 1 − p) |

- **질문 확신은 `confidence`** 다 (계획 §4-1 출력 계약 — 사용자 결정). choice 에서 `probs[answer] < max(probs) − 1e-9` 이면 경고 `choice_not_argmax` 를 그 호출에 남기고 상태는 바꾸지 않는다 (Clef 는 반올림 전 argmax 라 반올림 후 동률은 걸리지 않는다).
- B1 검사: 모든 라벨 토큰이 `top_logprobs` 안에 유한값으로 있어야 한다 (≤ −9999 는 빠진 것). 하나라도 빠지면 그 호출은 `error/b1_missing_label`.
- B1 토큰 대조 (판 3 보정 3): `top_logprobs` 원소 `{token, logprob}` 의 `token.strip()` 이 라벨 문자열과 **정확히 같으면** 그 라벨이다. 라벨이 아닌 토큰은 무시한다 (`allowed_token_ids` 가 막으므로 원래 없다 — 있으면 경고 `b1_extra_token`). 같은 라벨이 둘 이상이면 logprob 가 큰 것 하나를 쓰고 경고 `b1_duplicate_label`. 재정규화 = 라벨 logprob 의 softmax (최댓값을 빼고 exp).
- 재정규화는 **B1 후보 분포에만** 한다.

---

## 4. 상태·재시도·잘림

### 4-1. 최종 상태와 사유
논리 요청마다 **상태** 하나 (`ok` · `rejected` · `truncated` · `error`) + **사유** 하나. 계획의 `retried` 는 상태가 아니라 시도 수다.

| 상태 | 사유 |
|---|---|
| `rejected` | `input_limit` (P0 에서 확인한 길이 거부 응답 형태와 일치할 때만) |
| `truncated` | `target_cut` (①) · `tail_cut` (②) — 아래 §4-3 |
| `error` | `request_contract` · `http_422_other` · `http_<code>` · `transport` · `timeout` · §3-1 사유 코드 · `b1_missing_label` |

- 422 는 원인이 여럿이라(§0) **응답 메시지가 P0 에서 확인한 길이 거부 형태와 맞을 때만** `rejected/input_limit`, 나머지는 `error/http_422_other`.
- 길이 초과인데 정상 응답이 온 경우(③)는 사유가 아니라 **관측 필드** `answered_over_limit: true` 로 남긴다 (상태는 `truncated`). ①/② 와 ③ 이 함께 성립할 수 있다.

### 4-2. 시도와 재시도
| 응답 | 처리 |
|---|---|
| 200 + 검증 통과 | 끝 → §4-3 판정 |
| 200 + 검증 실패 | 재시도 없음 → `error/<사유 코드>` (모델 출력을 서버가 변환하는 과정 어딘가의 형식 위반 — 원인을 단정하지 않는다) |
| 422 | 재시도 없음 → §4-1 |
| 529 · 503 · 연결 오류 · 시간 초과(600초) | `Retry-After` 를 따르거나 1·2·4·8·16초 뒤, **논리 요청(B1 은 호출)당 총 5회** — resume 을 넘어 누적 |
| 그 밖의 4xx/5xx | 재시도 없음 → `error/http_<code>` |

- 동시성: 서버당 기본 1. P0 실측 후 모델 yaml 에 (최대 8, 계획 §6).
- 재시도는 같은 바이트 (`request_sha256` 동일).

### 4-3. 잘림 판정 (계획 §4-2·§4-4) — **호출마다**
- 보내기 전에 호출마다 `LengthInfo` 를 잰다 (판 3: B1 은 질문마다 고정부가 다르고, KoSGD 판끼리도 질문 수가 달라 논리 요청 하나에 값 하나로는 틀린다):
  - $\ell$ = `length_tokens`: 잘리기 전 입력 길이 (모델 yaml 의 인코더 규칙, 래퍼 포함 — P0).
  - $e$ = `target_end`: `Rendered.target_end_char` 를 같은 인코더의 토큰 위치로 바꾼 값 (그 문자를 덮는 마지막 토큰의 끝, state 시작 기준).
  - $L_m$ = `limit`, 고정부 = `fixed_tokens` (질문 스키마·봉투·래퍼 — 계산법 P0).
- `run/length.py` 의 `classify(LengthInfo) -> "not_truncated" | "target_cut" | "tail_cut"` 는 **길이만** 본다: $\ell \le L_m$ → `not_truncated` (`usage.input_tokens == L_m` 이어도). $\ell > L_m$ 이면 $r = L_m −$ `fixed_tokens` (저장 안 함), $e > r$ → `target_cut`, 아니면 `tail_cut`. `None` 을 '안 잘림' 으로 쓰지 않는다.
- 상태 결합은 `run/executor.py` 만: 서버 길이 거부(`rejected/input_limit`) 가 잘림 판정보다 우선 · 잘림이면서 200 정상 응답 → `answered_over_limit: true` · $\ell \le L_m$ 인데 `usage.input_tokens ≠ ℓ` 이면 `length_mismatch` 경고 (인코더 규칙이 틀렸다는 신호 — 보고한다).
- 논리 요청의 **길이 구간**(계획 §4-4: ≤4,096 · 4,097–8,192 · 8,193–16,384 · >16,384) 은 그 요청 호출들의 `length_tokens` 최댓값으로 정한다.

---

## 5. 기록·resume·보존

### 5-1. 위치 (판 3: 개발·시험 기록을 나눈다)
```
jev_test/results/<safe_model>/<run_id>/A/<set>/<variant>/
├─ fingerprint.json    # 커밋
├─ dev/   attempts.jsonl · final.jsonl          # 커밋 안 함
├─ threshold.json      # 커밋 — dev/final.jsonl 만으로 만든다 (§5-7)
├─ test/  seal.json (커밋) · attempts.jsonl · final.jsonl (커밋 안 함)
├─ extra/ attempts.jsonl · final.jsonl          # 커밋 안 함 — 묶음 대표가 아닌 행 (FunctionChat 만, §6-1)
├─ scores.json         # 커밋 (집계만, 문항 텍스트 없음, §7-6)
├─ risk.json           # 커밋 (§7-4)
└─ summary.json        # 커밋 — evalcommon 호환 요약 (§8-3)
jev_test/results/_compare/<compare_id>/A/<set>/<variant>/compare.json   # 커밋 — 모델 횡단 (공통 코호트·bootstrap, §7-6)
```
`attempts.jsonl`·`final.jsonl` 은 `.gitignore` (데이터 라이선스 — 재배포 금지). 요청 원문은 저장하지 않는다 — 분할 파일 + task yaml + 입력 데이터로 다시 만들고 `request_sha256` 으로 대조한다. **커밋되는 파일에는 문항 원문·정답 원문·원문에서 온 묶음 키 문자열이 들어가지 않는다** (ID·해시·숫자만 — §9 표식 검사).

### 5-2. 식별자 세 단계
- `logical_id` = `<set>:<group_id>:<item_id>` (§6).
- `call_id` = `logical_id` (결정 모델) 또는 `logical_id + "/" + question_id` (B1).
- `attempt` = `call_id` 안의 시도 번호 (1부터, resume 을 넘어 이어 센다).
- B1 의 논리 요청 해시 = `sha256("".join(sorted(call request_sha256)))`. 호출 하나가 `error` 여도 나머지 호출은 끝까지 돈다(진단용). 논리 상태는 호출 중 가장 나쁜 것 (`error` > `rejected` > `truncated` > `ok`).

### 5-3. 레코드
- `attempts.jsonl`: `{call_id, logical_id, attempt, session_id, started_at, ended_at, latency_ms, http_status, retry_after, transport_error, terminal, request_sha256, response_raw}` — `session_id` = 그 실행 프로세스의 ID (프로세스 시작 시 한 번 만든 UUID4, resume 하면 새 값. 판 3 보정: 비용의 '세션이 갈린 요청' 판정용) — `terminal` = 이 시도로 그 호출이 끝났는가 (200·422·재시도 없는 오류·재시도 소진). `response_raw` 는 UTF-8 문자열, 못 읽으면 `{"b64": ...}`. 시각은 UTC ISO-8601 (밀리초).
- `final.jsonl`: `{logical_id, status, reason, answered_over_limit, warnings, derived_from, calls: [CallRecord]}`.
- `CallRecord` (판 3): `{call_id, attempts, status, reason, warnings, request_sha256, length: LengthInfo | null, usage, answers_parsed, label_map?, top_logprobs_raw?}` — 판 2 의 최상위 `length_tokens`·`target_end` 는 `length` 안으로 옮긴다. `length` 가 null 인 것은 파생 레코드(§5-4)와 측정 전에 멈춘 `error/request_contract` 뿐.
- **`answers_parsed`** (판 3) = `{question_id: ParsedAnswer} | null`:
  - 그 호출에 **200 + 검증 통과 응답이 있으면** 맵, 키 집합 == 그 호출이 물은 질문 ID 집합 (B1 은 질문 하나). 상태 `ok` 와 `truncated`(③ 정상 응답) 가 여기 든다 — 잘림은 채점에서 상태로 빠지고, 맵은 "상한을 넘었는데 답한 경우" 진단에 쓴다 (사용자 결정 10-13).
  - 그 밖(`rejected`·`error`·`b1_missing_label`·응답 없음) 은 **null**. 부분 맵은 없다.
  - **채점 가능 여부는 맵이 아니라 논리 요청 상태로만** 정한다 (§7-3). B1 에서 다른 호출이 error 면 ok 호출의 맵은 남지만 채점에 쓰지 않는다.
- 왕복: `CallRecord.from_dict` 가 `answers_parsed` 를 `ParsedAnswer` 로 복원해야 한다 (`Any` 금지). terminal 응답으로 복구(§5-5)한 레코드는 최초 실행 레코드와 같아야 한다.

### 5-4. 판 파생 (KoSGD)
- 질문을 **따로** 채점하는 모델(pplx, B1)의 행동판은 전체판 레코드에서 행동 질문 10개(성공 8 + 진단 2)만 골라 만든다. 레코드에 `derived_from: <전체판 run 경로>` 를 적고 호출·비용은 0 으로 센다. `answers_parsed` 는 10개로 거른 복사본 (스키마 같음). 전체판 논리 요청이 `ok` 가 아니면 파생도 같은 상태·사유.
- 질문을 **함께** 채점하는 모델(Clef 계열)은 행동판을 따로 돌린다.
- 어느 쪽인지는 모델 yaml 의 `question_scoring: joint | separate`.

### 5-5. resume
1. 기존 `fingerprint.json` 이 `started_at` 을 빼고 같아야 한다. 다르면 거부 (C5).
2. `final.jsonl` 에 있는 `logical_id` 는 건너뛴다. 중복이면 거부.
3. 없는 ID 는 `attempts.jsonl` 에서 호출별로 복구한다: `terminal` 인 시도가 있는 호출은 **그 응답으로 결과를 다시 만든다 (다시 호출하지 않는다)**. terminal 이 없는 호출만 남은 재시도 예산 안에서 다시 시도한다.
4. 파일 끝 줄이 JSON 이 아니면(쓰다 끊김) 그 줄만 버리고 경고. 중간 줄이 깨졌으면 거부.
5. 줄마다 flush + fsync. final 줄은 그 논리 요청의 모든 attempts 줄 뒤에.
6. 시험 단계 resume 은 `test/seal.json` 의 `threshold_sha256` 이 지금 `threshold.json` 과 같아야 한다. 다르면 거부 (§5-7).

### 5-6. 비공개 보존 (커밋하지 않는 재현 자료)
- 실행이 끝나면 `jev_test/archive/<run_id>.tar.zst` (git 제외) 를 만든다: `dev/`·`test/`·`extra/` 의 `attempts.jsonl`·`final.jsonl` · 쓰인 task yaml · 목록 · 분할 파일 · `b1.yaml` · 입력 데이터 파일 해시 목록 + 그 아카이브의 sha256 을 `fingerprint.json` 에 기록.
- 입력 데이터 자체는 `jev_test/dataset/<set>/` (git 제외)에 고정 revision 으로 두고, 파일별 sha256 을 `dataset/<set>/SHA256SUMS` 로 남긴다. 재채점은 아카이브 + 같은 해시의 데이터로 한다.
- 이 자료가 사라지면 재채점은 불가능하다 — 해시는 변경을 알려 줄 뿐 복구하지 못한다. 보관 위치는 이 Mac 의 작업 폴더 하나뿐이라는 한계를 결과에 적는다.

### 5-7. 실행 단계와 임계값 봉인 (판 3)
`run/cli.py` 하위 명령 순서: `split` → `run --stage dev` → `threshold` → `run --stage test` (→ `run --stage extra`) → `score` → `certify`.
1. `threshold` 는 `dev/final.jsonl` **만** 읽는다 (test/extra 경로를 열지 않는다). 개발 단계가 끝나지 않았으면(분할의 dev 묶음 중 final 이 없는 것) 거부.
2. `run --stage test` 는 `threshold.json` 이 없으면 시작하지 않는다. 첫 시험 호출 **전에** `test/seal.json = {threshold_sha256, dev_final_sha256, sealed_at}` 를 쓴다.
3. `certify` 는 아래를 모두 확인하고 하나라도 어긋나면 실패한다:
   - (a) `dev/final.jsonl` 의 바이트 sha256 == `threshold.json.dev_input.sha256` == `seal.dev_final_sha256`.
   - (b) **같은 규칙으로 `dev/final.jsonl` 에서 t\* 를 다시 계산**하면 `threshold.json.by_tau` 와 같다 (t\* 가 개발 기록과 동결 규칙만의 함수라는 증거 — 시험 기록이 무엇이든 결과가 같다).
   - (c) `sha256(threshold.json)` == `seal.threshold_sha256` == `risk.json` 의 `threshold_sha256`.
   - mtime 비교는 **보조 경고**로만 남긴다 (mtime 은 되돌릴 수 있어 증거가 아니다).
4. 한계 (결과에 적는다): (b) 는 "임계값이 시험 점수를 쓰지 않았다" 를 보이지만, 개발 단계를 여러 번 돌려 고르는 일은 막지 못한다 — 그래서 `dev/attempts.jsonl` 의 시도 기록과 fingerprint 를 아카이브에 함께 둔다.

---

## 6. 평가 풀·묶음·분할 (계획 §4-3)

분할 파일 `configs/splits/<set>.json` = `{set, seed, pool_rule, allocation, groups: {group_id: [item_id…]}, representative: {group_id: logical_id}, dev: [group_id…], test: [group_id…], extra: [logical_id…], diagnostic_demotions: [...], notes: {label_conflict_groups: int, ...}}`. **라벨만 읽는 스크립트**가 만든다 (모델 호출 없음). seed = `datasets.yaml` 의 20261012. `group_id` 는 원문 문자열이 아니라 ID (아래 표) — 원문 묶음 키는 분할 파일에 쓰지 않는다.

| 셋 | 항목 | 묶음 키 → `group_id` | 평가 풀 (cap) |
|---|---|---|---|
| KoSGD | USER 턴 | `dialogue_id` | 10-12 선정 그대로 (`audits/kosgd_audit/audit_result.json`, 대화당 1턴 3,000) |
| FunctionChat | 행 (`serial_num`) | 연결요소 — 첫 user 메시지 `content` 일치 또는 `json.dumps(input_tools, sort_keys=True, ensure_ascii=False)` 일치로 union-find. **107 이 아니면 멈춘다.** `group_id` = 요소 안 최소 serial | 606 전부 (대표 107 + `extra` 499) |
| K-MHaS · KOTE | 행 | 원문 문자열 (같은 문장은 한 묶음) → `group_id` = 묶음 안 최소 행 번호 | 묶음 단위 단순 무작위 cap |
| KorFin-ASC | (SRC, aspect) 행 → SRC 하나가 요청 하나 | SRC 문자열 → `group_id` = 그 SRC 의 최소 `SID` 앞부분(`4208_0` → `4208`) | SRC 묶음 단위 단순 무작위 1,000. aspect 질문은 원 데이터에 처음 나온 순서, ID `aspect_1…k` |
| KLUE-MRC | (context, question) | context 문자열 → `group_id` = 묶음 안 최소 `guid` | `source` 별 **비례 할당**(최대 나머지 방식)으로 context 묶음 2,000 |

결정적 규칙:
- 단순 무작위 cap: `ids = sorted(group_ids)`; `random.Random(f"{seed}:{set}:pool").sample(ids, cap)`.
- 비례 할당: 층별 묶음 수 $G_h$, 할당 $\lfloor cap \cdot G_h / G \rfloor$ + 나머지는 소수부가 큰 층부터 (동률은 층 이름순). 층 안에서는 위 단순 무작위 (`…:pool:{h}`). 할당표를 `allocation` 에 적는다.
- 대표: `random.Random(f"{seed}:{set}:rep:{group_id}").choice(sorted(members))` (KoSGD 는 선정 그대로).
- 분할: `ids = sorted(풀의 group_id)`; `random.Random(f"{seed}:{set}:split").shuffle(ids)`; 앞 `floor(0.2·len)` 개발.
- KOTE 진단 강등: 평가 풀 전체 라벨에서 양성 < 50 인 감정을 `diagnostic_demotions` 에 적는다 (모델 점수를 보지 않는다 — 다시 고르지 않는다).
- `notes.label_conflict_groups`: 같은 묶음 안에 정답이 다른 행이 있는 묶음 수 (K-MHaS 1 — 대표에 따라 정답이 정해진다. 빼지 않고 건수만).
- **판 3 보정 5 (③a 세부)** — 규칙 값은 `configs/splits/rules.yaml`:
  - `item_id`·`group_id` 는 문자열이고 `:` 를 담지 않는다 (logical_id 구분자). KoSGD `group_id` = `dialogue_id`, `item_id` = 대화 안 `turn_index` (SYSTEM 포함 전체 턴 목록의 위치, `audit_result.json` 의 `selected_turns` 와 같은 뜻). FunctionChat `item_id` = `serial_num`, `group_id` = 요소 안 **정수로** 최소인 serial. K-MHaS·KOTE `item_id` = parquet 행 번호, `group_id` = 묶음 안 정수로 최소인 행 번호. KorFin `item_id` = `group_id` (SRC 하나가 항목 하나 — 그 SRC 의 aspect 행 `SID` 들이 항목을 이룬다). KLUE-MRC `item_id` = `guid`, `group_id` = 묶음 안 문자열로 최소인 `guid`.
  - 묶음 키는 문자열 **정확 일치** (정규화하지 않는다). KLUE-MRC 한 묶음의 행들이 `source` 가 다르면 멈춘다.
  - `groups` 는 **평가 풀 묶음만**, 키는 `sorted()`, 구성원도 `sorted()`. `dev`·`test` 는 분할 뒤 `sorted()` 로 적는다 (소속만 의미가 있다). `representative` 키도 `sorted()`.
  - 단순 무작위 cap 에서 cap ≥ 묶음 수면 전부. `allocation`: 비례 할당은 `{층: 묶음 수}`, 그 밖은 `{"all": 풀 묶음 수}`.
  - KOTE 강등은 **평가 풀 대표 항목**(dev+test) 의 라벨로 센다.
  - **KOTE 라벨 (판 3 보정 7, 사용자 결정 10-13)**: 정답은 `raw.json` 의 평가자 5명 투표에서 **3명 이상이 고른 감정** (`rules.yaml` 의 `votes.min_raters`). `io/sources/kote.py` 는 parquet 행마다 `ID` 로 raw 를 찾아 `votes: {감정: 고른 평가자 수}`·`labels_majority: [감정 이름, sorted()]` 를 붙인다 (평가자 한 명 안에서 같은 감정이 겹치면 한 번). raw 에 ID 가 없거나 문장이 parquet 과 다르거나, 평가자 수가 `n_raters` 가 아니거나, 감정 이름이 44개 이름(parquet 메타데이터) 밖이면 멈춘다. 라벨 충돌·강등은 `labels_majority` 로 센다 (`dichotomized` 의 `labels` 는 쓰지 않는다).
  - `notes` = `{n_rows, n_groups_total, n_pool_groups, label_conflict_groups_total, label_conflict_groups_pool}` (충돌은 `label_field` 가 있는 셋만, 라벨 집합을 정렬해 비교).
  - 분할 파일 바이트 = `json.dumps(plan.to_dict(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"` — 같은 입력이면 입력 순서와 무관하게 같은 바이트 (보정 6: `sort_keys`). 문항 원문·원문 묶음 키는 들어가면 안 된다 (§5-1) — 한글은 `diagnostic_demotions` 의 감정 이름(설정 값)에만 허용.
- **판 3 보정 6 (③a 명세 반박 반영)**:
  - KoSGD `SourceRow.row_id` = `f"{dialogue_id}#{turn_index}"` (`turn_index` 는 원본에 필드가 없다 — `turns` 를 enumerate 한 위치). `item_id` = `str(turn_index)`. `frames` 는 목록, 의도는 `frame["state"]["active_intent"]`. 고정 선정이 없는 대화·중복 대화·SYSTEM 턴·범위 밖 위치를 가리키면 멈춘다.
  - FunctionChat 묶음 키의 '첫 user 메시지' = `input_messages` 에서 **처음 `role == "user"` 인 원소**의 `content` (실제 606행 모두 첫 원소는 `system`). 도구 키 = `input_tools` 전체의 `json.dumps(sort_keys=True, ensure_ascii=False)`.
  - parquet 의 목록 열은 Arrow `to_pylist()` (또는 명시적 `list`/`int` 변환) 로 파이썬 값으로 바꾼다 (pandas `ndarray` 는 JSON 이 안 된다).
  - KLUE-MRC 는 **모든 행**을 둔다 (`is_impossible` 은 정답 필드 — 행을 거르지 않는다).
  - KorFin `SourceRow` 는 `SID` 마다 하나, `n_rows` = SID 수 (8,818). 분할 파일의 구성원은 `[group_id]` 하나.
  - 비례 할당에서 cap ≥ 전체 묶음 수면 전부(할당 = 층별 묶음 수). 모집단이 비거나 cap 이 양의 정수가 아니면 멈춘다. `pool_rule` = `rules.yaml` 의 그 셋 `pool` 객체 그대로.
  - 모듈 사이 결과: `Groups(row_to_group: dict[str, str], members: dict[str, list[str]])` (data/grouping), `PoolResult(group_ids: list[str], allocation: dict[str, int])` (data/pool) — §8-5 에 추가.

### 6-1. `extra` (묶음 대표가 아닌 행)
- FunctionChat 만 (`datasets.yaml` 의 "606행 F1·처리율은 기술 통계"). 다른 셋은 대표만 돌린다.
- extra 는 임계값·인증에 쓰지 않는다. 시험 단계 뒤에 돌리고, `scores.json` 의 `all_rows` 모집단(dev 대표 + test 대표 + extra)에만 쓴다.

### 6-2. 항목 만들기 순서 (판 3)
`io/sources/<set>.py` (원본 → `SourceRow` 목록) → `data/grouping.py` (`SourceRow` 목록 + 묶음 규칙 → `{row_id: group_id}`, **전체 행을 본 뒤에** 정한다 — FunctionChat 연결요소) → `data/items/<set>.py` (`SourceRow` 들 + `group_id` + `TaskSpec` + 목록 + `SplitPlan.diagnostic_demotions` → `Item`, 순수).
- `Item` 을 만들 때 **질문을 펼치고 질문마다 정답을 붙인다** (`BoundQuestion.gold`). 정답은 `score/labels.py` 의 등록 규칙 `label_rule(rows, binding) -> str | None` 이 만든다 — `binding` 은 펼친 질문의 재료 (`{k, ASPECT}` 등, 정적 질문은 `{}`).
- KOTE 강등 감정은 이때 `role = diagnostic` 으로 바꾼다.
- FunctionChat 도구 선택지 = 정규화한 `input_tools` 의 `{function.name: function.description}` + `NONE`. call 행의 정답 도구가 선택지에 없으면 **멈춘다** (10-13 집계로는 0).
- KoSGD: 정답 의도 ID 는 `서비스/의도` (서비스가 달라도 이름이 같은 의도 4개). 고정 칸 정답 = 이번 턴 frame 의 `active_intent` 중 `NONE` 아닌 것을 **카탈로그 순서**로 (사전순 아님). 앞 턴 베끼기 기준용 직전 정답은 `Item.baseline.copy_prev` (직전 USER 턴의 고정 칸 정답, 첫 USER 턴은 `["NONE","NONE"]`).

---

## 7. 채점

### 7-1. 셋별 적용표
요청 오류 $\ell_i$ = 성공 질문 중 **정답이 있는 것**($M_i$) 하나라도 틀림 (KoSGD 칸 예외). 확신 $s_i = \min_{j \in J_i}$ 질문 `confidence` (**성공 질문 전체** — 정답 유무와 무관). $v_i = 1$ iff 상태 `ok`.

| 셋 (판) | 성공 질문 | 진단 | 질문별 F1 | 보정 |
|---|---|---|---|---|
| KoSGD 전체판 | `ongoing_1·2` (묶음) + 행동 noul 8 | AFFIRM_INTENT·NEGATE_INTENT | noul: 2클래스 macro-F1. 칸: 고정 칸 정답 기준 macro-F1 (§7-2) | noul: 질문별. 칸: 고정 칸 정답 기준 칸별 |
| KoSGD 행동판 | 행동 noul 8 | 같음 | 같음 | 같음 |
| FunctionChat | 행동 choice 3 + 도구 choice 6 (도구 5 + NONE) | — | 행동: 3클래스 macro-F1. 도구: **macro-F1 을 내지 않는다** — call 행의 도구 정답률, 비호출 행의 `NONE` 정답률을 따로 | 행동: 3선택지. 도구: 6선택지 top-label ECE·Brier·log loss (모든 행이 6선택지) |
| K-MHaS | noul 9 | — | 질문별 2클래스 macro-F1 | 질문별 |
| KOTE | noul 8 − 강등 | 강등된 감정 | 같음 | 같음 |
| KorFin-ASC | aspect 마다 choice 3 | — | **모든 aspect 질문을 합친** 3클래스 macro-F1 (`pooled.aspect`) | 합쳐서 |
| KLUE-MRC | noul 1 | — | 2클래스 macro-F1 | 그 질문 |

- macro-F1 의 클래스 = **정답 또는 예측에 한 번이라도 나온 클래스**. 둘 다에 없는 클래스는 넣지 않는다. 클래스별 support·tp·재현율·정밀도를 함께 낸다 (계획 §4-1 "클래스별 재현율"). 분모가 0 인 재현율·정밀도는 `{num: 0, den: 0}` 로 두고 값을 만들지 않는다.
- ECE: 15 등폭 bin `[0,1/15), …, [14/15, 1]` (마지막 닫힘), top-label (`confidence` 대 `answer == gold`). bin 은 **빈 것도 포함해 15개 모두** `{index, lo, hi, n, acc, conf}` (빈 bin 의 acc·conf 는 null). bin 의 n 합 == 그 질문의 채점 수.
- Brier: 확률표 전체에 대한 one-hot 제곱합의 평균 (noul 은 2클래스라 $2(p-y)^2$ 와 같다). log loss: $-\log \mathrm{clip}(p_{\rm gold}, 10^{-12}, 1)$.
- 선택지 수가 다른 질문끼리 보정 지표를 평균하지 않는다.
- 채점 수가 0 인 질문: `accuracy = {0, 0}`, `macro_f1`·`ece`·`brier`·`log_loss` null, bin 15개는 n 0·acc/conf null (판 3 보정).

### 7-2. KoSGD 칸
- 정답 칸 고정: 정답 의도(`NONE` 아닌 것, 0–2개)를 **카탈로그 순서**로 정렬해 ①·② 에 넣고 모자라면 `NONE`. 질문 문구("서비스 목록에서 앞에 있는 서비스의 일 = ①")와 같은 규칙이다.
- **묶음 정답(요청 오류·위험에 씀)**: 순서 무관 — $\{a_1, a_2\}$ 다중집합 == 정답 다중집합, 그리고 `NONE` 아닌 같은 값이 두 칸에 없음.
- **칸별 F1·보정**: 위 **고정 칸 정답**으로만 계산한다 (예측을 보고 정답을 재배정하지 않는다 — 재배정하면 보정이 낙관적으로 치우친다, Codex 반례: Brier 1.96 → 0.0002).
- 진단 열: "순서만 틀린 묶음" 건수 (묶음 정답이지만 고정 칸 정답과 다른 것).
- 앞 턴 베끼기: `Item.baseline.copy_prev` 의 묶음 정답률만 (확률이 없어 처리율·보정 없음).

### 7-3. 코호트·정답 없음
- 모델별 채점 코호트 = 상태 `ok` 인 논리 요청 (질문 전부). `truncated`(③ 포함)·`rejected`·`error` 는 채점·보정에서 빠지고 처리율 분모에만 남는다.
- 공통 코호트 = 비교하는 모든 모델(B1 포함)이 `ok` 인 `logical_id` — 모델 하나의 폴더로는 만들 수 없으므로 `compare.json` 에 둔다 (§7-6).
- **정답 없음(MISSING)** 은 `BoundQuestion.gold = null` 이다 — `"false"`·`"NONE"`·빈 의도 집합(= `["NONE","NONE"]`) 과 다르다.
  - 질문별 F1·보정: 정답 있는 것만, `n_missing` 을 옆에 적는다. `n_missing` 은 `n_scored` 와 같은 **채점 코호트(상태 `ok`) 안에서** 센다 (판 3 보정).
  - $s_i$: MISSING 질문도 **빼지 않는다** (빼면 정답 유무가 수락 판단에 들어간다 — 계획 §4-2).
  - $\ell_i$: $M_i$ (정답 있는 성공 질문) 로만.
  - $M_i = \varnothing$ 인 요청: 위험 표에 넣지 않는다 — **분모 $|S|$ 에서도 뺀다** (사용자 결정 10-13, 계획 개정 13). `n_empty_mask` 로 따로 센다. 첫 실행 6셋에서는 0 건이다 (§0).

### 7-4. 위험 (`risk.json`, 계획 §4-2)
`risk.json` = `{schema: "risk/1", model, set, variant, run_id, threshold_sha256, cells: {"0.01": RiskCell, "0.02": RiskCell, "0.05": RiskCell}}`. `RiskCell` (판 3):

```
{tau: "0.02", status: MEETS|FAILS|UNDERPOWERED|NO_THRESHOLD, insufficient_by_design: bool, unit: "group_representative",
 t_star,
 dev:  {n_groups, n_denom, n_empty_mask, n_accepted, k_errors},
 test: {n_groups (=|T|), n_denom, n_empty_mask, n_accepted, k_errors, U, coverage: {num, den}, b_flip},
 by_status: {ok, rejected, truncated, error},            # 시험, n_empty_mask 뺀 뒤
 accepted_mix: {
   by_class:      {question_id: {class: {sampled, n, k}}},   # 성공 질문의 정답 클래스별 (KoSGD 칸은 고정 칸 정답)
   by_service:    {service: {sampled, n, k}} | null,          # KoSGD 만 — 다중 서비스 요청은 서비스마다 센다 (합 > n)
   by_stratum:    {stratum: {sampled, n, k}} | null,          # KLUE-MRC source
   by_n_questions:{count: {sampled, n, k}}                    # 요청당 성공 질문 수 (KorFin 1–8)
 },
 by_length_bucket: {"le_4096"|"le_8192"|"le_16384"|"gt_16384": {sampled, n_valid, n, k}},
 diagnostic_error_in_accepted: {question_id: {n, wrong}}}
```
- `sampled` = 그 칸에 든 시험 요청 수 (분모), `n` = 수락 수, `k` = 수락 중 요청 오류. 사람 이관률 = $1 - n/\text{sampled}$ (FunctionChat 유형별은 `by_class.<행동 질문>`).
- `insufficient_by_design` = $|T| < n_{\min}(\tau)$ — **플래그일 뿐 계산은 그대로 한다** (상태는 정상 규칙으로 정해지며 MEETS 가 될 수 없다). 계획 §4-2 3번의 "따로 표시" 가 이 플래그다.
- `b_flip` 은 MEETS 일 때만, 아니면 null. NO_THRESHOLD 면 `t_star`·`test.n_accepted`·`k_errors`·`U` 는 null, `coverage = {num: 0, den: n_denom}`.
- 판 2 의 `test.groups/n/k` · `accepted_mix: {분포}` 는 위 필드로 바꾼다.

### 7-5. 임계값 (`threshold.json`, 판 3)
```
{schema: "threshold/1", model, set, variant, run_id,
 rule: "plan-4-2:dev_risk<=tau/2;max_coverage;tie_larger_t",
 unit: "group_representative",
 dev_input: {path: "dev/final.jsonl", sha256, nbytes, n_groups, n_denom, n_empty_mask},
 by_tau: {"0.01": {tau: "0.01", status: SELECTED|NO_THRESHOLD, t_star, n_accepted, k_errors, coverage: {num, den}}, "0.02": …, "0.05": …}}
```
- τ 키는 **문자열** `"0.01"`·`"0.02"`·`"0.05"` (부동소수 키 불일치 방지). 값에도 같은 `tau` 를 넣고 키와 같아야 한다 (dataclass 왕복 = 파일 형식).
- 후보 t = 개발 표본에서 $v_i = 1$ 이고 $M_i \ne \varnothing$ 인 요청의 $s_i$ 의 서로 다른 값. 규칙: $k_D/n_D \le \tau/2$ 인 t 중 개발 처리율 $n_D / $`n_denom` 최대, 동률이면 큰 t. 후보가 없거나 만족하는 t 가 없으면 `NO_THRESHOLD` (`t_star`·`n_accepted`·`k_errors` null, `coverage = {0, n_denom}`). 같은 점수는 함께 수락하거나 함께 빠진다 (쪼개지 않는다).
- KoSGD 의 $\ell_i$ 는 칸 묶음 비교(§7-2), 다른 셋은 기본 규칙 — 같은 함수를 `score/tasks` 가 셋별로 부른다.

### 7-6. 점수 (`scores.json` = `ScoreTable`) 와 비교 (`compare.json`) — 판 3
비율은 전부 `{num, den}` 으로 적는다 (채점 코호트 분모와 처리율 분모가 섞이지 않게). 값(소수)은 보고서가 계산한다.

```
scores.json = {schema: "scores/1", model, set, variant, run_id,
  populations: {
    "test":     Population,     # 인증 표본: 시험 묶음 대표 — certified: true (인증 셀은 risk.json)
    "all_rows": Population      # FunctionChat 만: dev 대표 + test 대표 + extra (606) — certified: false
  },
  cost: {by_stage: {dev|test|extra: Cost}} }

Population = {certified, unit: "group_representative"|"row",
  counts: {n_sampled, by_status: {ok, rejected, truncated, error}, n_empty_mask},
  request: {n_scored, wrong: {num, den}},               # 요청 오류 ℓ_i (정답 기준), 실행 오류와 다르다
  questions: {question_id: QStats},
  pooled: {"aspect": QStats} | {},                       # KorFin 만 — aspect_k 관측을 먼저 합친 뒤 계산
  set_specific: {...}}

QStats = {role, type, n_scored, n_missing, accuracy: {num, den}, macro_f1 | null,
  classes: {class: {support, predicted, tp, recall: {num, den}, precision: {num, den}}},
  calibration: {ece, bins: [15 × {index, lo, hi, n, acc, conf}], brier, log_loss},
  warnings: {choice_not_argmax: int}}
```
- `set_specific`:
  - KoSGD: `bundle_correct {num,den}` · `order_only_bundles` · `copy_baseline_bundle_correct {num,den}`.
  - FunctionChat: `tool_acc_on_call {num,den}` · `none_acc_on_noncall {num,den}` (도구 질문의 `macro_f1` 은 null).
  - KorFin: `aspect_not_in_text: {n_scored, wrong}` (진단 열 — aspect 이름이 문장에 글자 그대로 없는 질문, §0 의 71 행).
  - 그 밖의 셋: `{}`.
- 점수는 **임계값과 무관한 `ok` 코호트**의 값이다 (수락 집합의 점수는 `risk.json`). 이름으로 둘을 섞지 않는다.
- `Cost` = `{n_logical, n_calls, n_attempts, n_retries, failure: {num: 상태 error 인 논리 요청, den: n_logical}, latency_ms: {population: "logical_ok", n, p50, p95, n_excluded_resumed}, input_tokens: {sum, n_calls_missing_usage, n_missing_on_200}, derived_from: str | null}`.
  - 백분위: 정렬한 값에서 위치 $(n-1)p$ 의 선형 보간 (numpy 기본과 같다). $n = 0$ 이면 p50·p95 null.
  - 지연 = 논리 요청의 **완료 지연** = 마지막 terminal 시도 `ended_at` − 첫 시도 `started_at` (재시도·대기 포함, B1 은 호출 전부). 그 요청의 시도에 `session_id` 가 둘 이상이면(resume 으로 갈림) 지연에서 빼고 `n_excluded_resumed` 로 센다 — **`ok` 요청 중에서만** 센다 (모집단이 `logical_ok`; 작업 ⑥ 에서 `ok` 아닌 resume 요청 fixture 추가).
  - 입력 토큰 (판 3 보정 2): 호출마다 **마지막 terminal 시도**의 `response_raw` 를 JSON 으로 읽어 `usage.input_tokens` (B1 은 vLLM `usage.prompt_tokens`) 가 **정수(bool 제외)** 이면 응답 코드와 무관하게 `sum` 에 더하고, 아니면(terminal 시도 없음 · 본문 못 읽음 · usage 없음 · 정수 아님) `n_calls_missing_usage` 로 센다. 모든 호출은 둘 중 정확히 하나에 든다 (`sum` 에 든 호출 수 + `n_calls_missing_usage` == `n_calls`). `sum` 은 **하한**이다. `n_missing_on_200` = 그중 terminal 이 200 인 호출 수 (서버가 usage 를 안 주는 경우를 실패와 따로 보이게).
  - 파생 판(§5-4) 은 수치 전부 0 (p50·p95 null) 이고 `derived_from` 에 전체판 run 경로. 직접 돌린 판은 `derived_from: null`.
- `compare.json` (모델 횡단) = `{schema: "compare/1", models: [...], set, variant, common_cohort: {n, logical_ids_sha256, per_model: {model: Population}}, bootstrap: {...}}`:
  - 공통 코호트는 비교 모델 전부(B1 포함)가 `ok` 인 시험 `logical_id` 의 정확한 교집합. ID 목록은 정렬해 해시만 적는다.
  - bootstrap (§7-7) 결과.

### 7-7. 통계 설정
- 모델 간 차이: 묶음 단위 paired bootstrap, 2,000 회, `random.Random(f"{seed}:boot:{set}")`, 임계값은 고정(다시 고르지 않는다). 처리율·F1 차이에만.
  - 인증 처리율 차이: 시험 묶음 대표.
  - **FunctionChat 606행 기술 통계의 F1 차이: 107 묶음 단위로 행을 함께 재표집** (계획 §3 FunctionChat 세부 — 판 2 의 "시험 표본" 은 계획과 달랐다).
- 위험 상한에는 bootstrap 을 쓰지 않는다 (계획 §4-1).

### 7-8. 채점 내부 인터페이스
`score/tasks.py` 는 요청마다 `RequestOutcome` (메모리 전용, 커밋 안 함) 을 만들어 `score/risk.py`·`score/bootstrap.py`·threshold 계산에 넘긴다. 집계(`ScoreTable`) 에서 요청 단위 결과를 되살리지 않는다 — 같은 정답률이라도 오답이 한 요청에 몰렸는지에 따라 $\ell_i$ 가 다르다.

---

## 8. 구현 구성 — 기능별, 바이브코딩하기 편하게

사용자 지시(10-13): **기능별로, 기능 하나씩 AI 에게 맡겨 고치기 편하게.**

### 8-1. 규칙
- **파일 하나 = 기능 하나.** 첫머리 docstring 에 "무엇 · 입력 · 출력 · 이 계약의 몇 절". 그 파일만 열어도 고칠 수 있게.
- **작게**: 파일 ≤ 200 줄, 함수 ≤ 50 줄 정도.
- **입출력은 정해진 곳에만**: 파일 읽기 `io/` (설정·데이터·분할·레코드), 네트워크 `client/`. 나머지(`contract/`·`data/`·`score/`)는 순수 함수 — 이미 읽은 객체를 받는다.
- **모듈 사이는 `types/` 의 dataclass 만** (§8-5 필드).
- **상태기계는 한 곳**: `run/executor.py` 만 시도 시작·재시도·terminal 판정·resume 복구·상태 결합(§4-3)을 소유한다. `client/` 는 **한 번의 시도**만 (재시도 안 함), `io/records.py` 는 줄 추가·읽기만.
- **기능마다 짝 테스트** `tests/<폴더>/test_<파일>.py` + 경계마다 통합 테스트 하나. GPU·서버 없이 fixture 로 돈다. 한 기능을 고치면 그 단위 테스트와 해당 경계 통합 테스트를 같이 돌린다.
- **설정은 코드 밖**: 문구·선택지·라벨·재시도·cap 은 yaml. 코드에 박지 않는다.
- **`jeveval/README.md` 기능 지도**: 파일마다 한 줄 + 의존 방향 `run → client/io → score/data/contract → types` (거꾸로 금지).

### 8-2. 구성
```
jev_test/jeveval/
├─ types/      __init__.py (JsonRecord) · records.py · specs.py · results.py · outcomes.py
├─ io/         config.py (yaml, 중복 키 거부) · sources/<set>.py (원본 → SourceRow) · splits.py · records.py · archive.py
├─ contract/   taskspec.py · render.py (§2-2 → Rendered) · request.py (§2-1·2-3·2-4) · response.py (§3-1) · b1_prompt.py (§2-5)
├─ data/       items/<set>.py (SourceRow → Item, 순수) · expand.py (per_item_questions 펼치기) · grouping.py · pool.py · split.py (§6)
├─ score/      answers.py (§3-2 → ParsedAnswer) · labels.py (정답 규칙 등록) · tasks.py (§7-1 → RequestOutcome) · kosgd_slots.py (§7-2) · calibration.py · f1.py · threshold.py (§7-5) · risk.py (§7-4) · population.py (§7-6) · cost.py · bootstrap.py
├─ client/     systemone.py · vllm_chat.py (한 번의 시도)
├─ reference/  pplx_runner.py · clef_runner.py (참조 구현을 고치지 않고 부르는 얇은 층 — T0·C1 temperature 경로)
└─ run/        executor.py (상태기계) · length.py (§4-3) · seal.py (§5-7) · cli.py (하위 명령: split · run · threshold · score · certify · compare)
```

### 8-3. 결과 규약
새 결과(`scores.json`·`risk.json`·`threshold.json`·`compare.json`)는 이 계약이 정하고, 최상위 집계와 맞추기 위해 `summary.json` 을 `reranker_test/evalcommon` 의 `make_score_summary` 로 추가로 쓴다: **`risk.json` 의 주 지표 판·τ `"0.02"` `RiskCell` 에서만** 만든다 — `metric = "coverage_at_risk_2pct"`, `score` = `test.coverage.num / test.coverage.den` (NO_THRESHOLD·UNDERPOWERED 면 0), `extra = {status, insufficient_by_design}`. `scores.json` 의 정답률로 만들지 않는다.

### 8-4. 작업 순서 (각 작업 = 파일 몇 개 + 그 테스트, 따로 리뷰·실행)
1. ~~`types/` + `io/config.py` + task yaml 스키마 검사 + §9 fixture~~ — **끝** (10-13, 커밋 `dafe4b2`)
2. **②-0** (작업 ① 고침): `types/` 를 §8-5 로 갱신 (`SourceRow`·`BoundQuestion`·`Item`·`Rendered`·`ParsedAnswer`·`LengthInfo`·`CallRecord.length`·`answers_parsed` 타입·`Threshold`·`ThresholdFile`·`RiskCell`·`ScoreTable` 계열·`RequestOutcome`) · `contract/taskspec.py` 의 `per_item_questions` 검사·성공 질문 규칙 (§1-1) · §9 의 판 3 fixture.
   **②**: `contract/` (render·request·response·b1_prompt) + `score/answers·f1·calibration·kosgd_slots` (판 3 보정 3: `labels` 는 ③ 으로 — 정답 규칙은 `io/sources` 가 정하는 원본 필드 구조를 알아야 한다)
3. **③a** `io/sources` + `data/grouping·pool·split` + `io/splits` + `run/make_splits.py` → 분할 파일 생성 (라벨만 — 질문 문구 불필요). **③b** `data/expand·items` + `score/labels` (task yaml 이 필요 — 합성 TaskSpec 으로 먼저 구현 가능)
4. `client/` (한 번의 시도) + `io/records`
5. `run/executor` (상태기계·resume) + `run/length` + `run/seal`
6. `score/tasks·threshold·risk·population·cost·bootstrap` + `run/cli` + `io/archive` + `reference/`

### 8-5. 자료형 필드 (판 3 — 판 2 의 SPEC_AMBIGUOUS 6곳)
모두 `frozen=True` 가능하면 frozen, `to_dict()`/`from_dict()` 왕복 (중첩 dataclass 도 복원). `| None` 이 아닌 필드는 null 을 받지 않는다.

```python
# types/specs.py
SourceRow(set: str, row_id: str, fields: dict)                     # 원본 한 행 (io/sources 출력, 메모리 전용)
BoundQuestion(id: str, role: str, type: str, instructions: str,
              options: dict[str, str] | None,                      # choice: {선택지 ID: 설명}
              criteria: dict[str, str] | None,                     # noul: {"true": ..., "false": ...}
              label: str,                                          # 정답 규칙 이름 (yaml 그대로)
              gold: str | None)                                    # 정답 클래스 ID 문자열, None = MISSING (§7-3)
Item(set: str, group_id: str, item_id: str,
     state_fields: dict | str,                                     # json_string 셋은 dict (task yaml keys 의 값), plain_text 는 str
     questions: list[BoundQuestion],                               # 펼친 뒤, 요청 순서
     meta: dict,                                                   # 닫힌 키: {"service": list[str] | None, "stratum": str | None, "flags": list[str]}
     baseline: dict | None)                                        # KoSGD: {"copy_prev": [칸1, 칸2]}, 그 밖 None
# Item 은 메모리 전용 — 파일로 쓰지 않는다. logical_id = f"{set}:{group_id}:{item_id}".
# meta.flags 값: "aspect_not_in_text" (KorFin 질문별이면 "aspect_not_in_text:aspect_2" 처럼 질문 ID 를 붙인다), "label_conflict_group".
# 질문 수·정답 클래스처럼 questions 에서 계산되는 값은 meta 에 중복 저장하지 않는다.

# types/results.py
Rendered(state: str, target_end_char: int)
ParsedAnswer(type: str, answer: str, probs: dict[str, float], confidence: float)   # §3-2. question_id 는 담지 않는다 (맵의 키)
LengthInfo(length_tokens: int, target_end: int, limit: int, fixed_tokens: int)     # §4-3, 호출마다
Threshold(tau: str, status: str, t_star: float | None, n_accepted: int | None,
          k_errors: int | None, coverage: dict)                                     # §7-5 by_tau 한 칸
ThresholdFile(schema, model, set, variant, run_id, rule, unit, dev_input: dict, by_tau: dict[str, Threshold])
RiskCell(...)                                                                       # §7-4 필드 그대로
ScoreTable(schema, model, set, variant, run_id, populations: dict[str, Population], cost: dict)   # §7-6
Population(...) · QStats(...) · Cost(...)                                           # §7-6 필드 그대로

# types/records.py
CallRecord(call_id, attempts, status, reason, warnings: list[str], request_sha256,
           length: LengthInfo | None, usage: dict | None,
           answers_parsed: dict[str, ParsedAnswer] | None,
           label_map: dict[str, str] | None = None, top_logprobs_raw: Any = None)     # §5-3

# types/outcomes.py (메모리 전용)
RequestOutcome(logical_id: str, group_id: str, stage: str,          # dev | test | extra
               status: str, valid: bool, mask_empty: bool,
               s: float | None,                                     # valid 일 때 min confidence (J_i 전체)
               wrong: bool | None,                                  # valid 이고 mask_empty 가 아닐 때 ℓ_i
               gold: dict[str, str | None], answer: dict[str, str] | None,
               length_max: int | None, meta: dict)

# 작업 ② 함수 결과 (판 3 보정 3, 메모리 전용 — 모두 JsonRecord)
Validated(reason: str | None, warnings: list[str], answers: dict[str, dict] | None)   # contract/response.validate — reason 이 None 일 때만 answers (원 답 객체, 질문 ID 키)
AnswerParse(parsed: ParsedAnswer | None, reason: str | None, warnings: list[str],
            label_probs: dict[str, float] | None)                                     # score/answers — systemone 은 label_probs None, B1 은 재정규화 라벨 분포
B1Config(system: str, labels: list[str], params: dict)                                  # configs/tasks/b1.yaml 을 읽은 것 — labels 62개 순서, params 는 §2-5 고정 매개변수
B1Call(call_qid: str, messages: list[dict], label_order: list[str],
       label_map: dict[str, str], params: dict)                                         # contract/b1_prompt — params = config params + top_logprobs(=선택지 수); allowed_token_ids 는 client 가 모델 yaml 의 라벨 토큰으로 채운다 (④)
F1Result(classes: list[str], per_class_f1: dict[str, float], macro_f1: float | None,
         class_stats: dict)                                                             # score/f1 — class_stats 는 QStats.classes 모양 그대로
CalibResult(ece: float | None, bins: list[dict], brier: float | None, log_loss: float | None)   # score/calibration — §7-1
SlotJudgement(fixed_gold: list[str], group_correct: bool, duplicate_non_none: bool, order_only: bool)  # score/kosgd_slots — §7-2

# 작업 ③a (판 3 보정 6, 메모리 전용)
Groups(row_to_group: dict[str, str], members: dict[str, list[str]])   # data/grouping — members 의 구성원은 item_id (KorFin 은 [group_id])
PoolResult(group_ids: list[str], allocation: dict[str, int])          # data/pool
```

---

## 9. 최소 fixture (`tests/fixtures/`, 코드보다 먼저)

| fixture | 확인 |
|---|---|
| `render/*.json` → 기대 state 문자열·요청 바이트·sha256 · **`target_end_char`** (판 3) | §2 직렬화 바이트 고정 · 대상 끝 위치 (KoSGD 는 catalog 앞, FunctionChat 은 tools 앞) |
| `responses/valid_*`, `invalid_*` (사유 코드마다 1개 이상, 중복 키·bool·추가 키 포함) | §3-1 — 반올림 있는/없는 응답 둘 다 통과. 합 0.9999 응답을 재정규화하지 않는다 |
| `answers/*.json` (판 3) | §3-2 — noul p=0.5 → `"true"` · choice `confidence` 그대로 · `choice_not_argmax` 경고 (확률표 최댓값보다 작은 `choice`) · Clef 동률(0.5/0.5, `choice`=B) 은 경고 없음 |
| `scoring/kosgd_slots.json` | 정답 0·1·2개, 같은 값 두 칸, 순서만 틀림, Codex 반례(고정 칸 정답 기준 Brier 1.9602) · **판 3**: 서비스가 다른 같은 이름 의도, 카탈로그 순 ≠ 사전순, 직전 정답 ≠ 현재 정답 |
| `scoring/f1_classes.json` | 미출현 클래스 제외 규칙 · 클래스별 recall `{num, den}` · 분모 0 |
| `scoring/calibration.json` (판 3) | ECE 15 bin 빈 것 포함 (n 합 == 채점 수) · noul Brier = 2(p−y)² · log loss clip |
| `scoring/risk_cases.json` | U(6,600)=1.964% · U(0,150)=1.977% · U(1,150)=3.123% · U(0,252)=1.18% · U(0,86) · $n_{\min}$ · $b_{\rm flip}$ · 네 상태 + 플래그 |
| `scoring/threshold_cases.json` (판 3) | 규칙 재계산 == `by_tau` · NO_THRESHOLD 는 `t_star`·`n_accepted`·`k_errors` null · 같은 점수 묶음째 · 시험 기록을 바꿔도 t\* 불변 · 묶음 단위 n_denom (FunctionChat 개발 21 묶음 대표 — 행 606 이 아님) |
| `scoring/missing_mask.json` (판 3) | MISSING 인 저확신 성공 질문이 $s_i$ 의 min 에 남는다 · `"false"`·`"NONE"` 은 MISSING 이 아니다 · 빈 마스크 요청은 분모에서 빠지고 `n_empty_mask` 에 센다 |
| `scoring/cohort_population.json` (판 3) | 모델별 실패 ID 가 다를 때 공통 코호트 == 정확한 교집합 · FunctionChat `test` 와 `all_rows` 가 구별된다 (크기가 다른 묶음) · KorFin `pooled.aspect` ≠ 질문별 평균 |
| `scoring/cost.json` (판 3) | B1 재시도·대기·부분 실패를 포함한 논리 완료 지연 · KoSGD B1 `n_calls == 12 × n_logical` · 파생 판 0 · usage 없음은 0 이 아니라 `n_calls_missing_usage` |
| `splits/*.json` | 합성 행으로 union-find·비례 할당(최대 나머지)·대표·분할 결정성 · **판 3**: `group_id` 가 원문이 아닌 ID · `label_conflict_groups` |
| `expand/korfin.json` (판 3) | 한 SRC 에 정답이 다른 aspect 두 개 → 질문 순서·ID·정답 연결 · `per_item_questions` 만 있는 TaskSpec 통과 · 정적 ID 와 겹치면 오류 |
| `records/roundtrip.json` (판 3) | ok · truncated(정상 응답, 맵 있음) · rejected · 검증 실패 · B1 일부 실패 를 직렬화 후 복원 → 같음 · `answers_parsed` 가 `ParsedAnswer` 로 복원 |
| `resume/*` | 끝 줄 깨짐 · 중간 줄 깨짐 · fingerprint 불일치 · 중복 ID · terminal 응답 뒤 끊김(다시 호출하지 않음, 복구 결과 == 최초) · 재시도 예산 누적 · **판 3**: 시험 resume 중 threshold 교체 거부 |
| `length/*.json` | $\ell = L_m$ (잘림 아님) · $\ell = L_m + 1$ · target_cut vs tail_cut (발화 **끝** 위치 기준) · **판 3**: 같은 논리 요청 안에서 `fixed_tokens` 가 다른 B1 호출 · 거부 우선 · mismatch 경고 |
| `seal/*.json` (판 3) | threshold 없이 시험 시작 거부 · seal 해시 불일치 → certify 실패 · 내용은 그대로 두고 mtime 만 바꾼 것은 재계산(b) 통과(경고만) · 시험 점수로 t\* 를 바꿔 내용을 고친 뒤 mtime 을 위장한 것은 (b)·(c) 에서 실패 |
| `temperature/pplx_path.json` | `reference/pplx_runner.py` 경로에 고정 logit($|z| ≈ 1.55$ 포함) → softmax(z/T) 한 번. 빼거나 두 번 적용하는 오류 주입 시 실패 |
| `b1/*.json` | 라벨 대응·재정규화·−9999·라벨 누락 → `error` · 대응을 바꾼 noul 의 p · **판 3**: 대응 교환(A→false, B→true) × 0.5/0.5 → `"true"` |
| `canary/*` (판 3) | 합성 state·정답에 고유 표식 문자열을 넣은 입력. 커밋 대상 파일(`fingerprint`·`threshold`·`seal`·`scores`·`risk`·`summary`·`compare`) 어디에도 표식이 없는지는 **출력이 생기는 작업 ⑥ 의 통합 검사**에서 본다 (②-0 은 입력만) |

---

## 10. P0 에서 확인해 이 문서를 고칠 것

- pplx: 길이 초과 응답 형태(422 메시지) · 반올림 · 문자열 state 처리 · `choice` 가 확률표 argmax 인지. Clef(SGLang): `usage.input_tokens` · 길이 초과 동작. 각 서버의 `served_name`.
- 모델별 인코더 규칙(래퍼 포함)·$L_m$·`fixed_tokens` 계산법·문자 위치 → 토큰 위치 변환.
- B1 진입 조건 (계획 §2-3) · 서버별 안전 동시성.
- 감사 v4 (§2-2) — 동결 때.

## 11. 판 이력

- 판 1 (10-13): 초안.
- 판 2 (10-13): Codex 반박 반영 — 잘림 판정 경계 오류(ℓ = L_m 오판, 발화 시작이 아니라 끝 위치) · state 키 이름을 datasets.yaml 로 · 감사 v4 필요 · noul criteria 명시 · 422 원인 분리 · 상태와 사유 분리 · 비공개 보존 · FunctionChat 도구 macro-F1 제외(정답 도구 25/100, 모든 행 6선택지) · KoSGD 칸 보정은 고정 칸 정답 · B1 선택지에 ID · 세 단계 식별자 · terminal 응답 복구 · 판 파생 · 설정 스키마 · 평가 풀 추출 · 코호트 · 검증기 문법 · score 범위 밖 · 원리적 부족은 플래그 · evalcommon 호환 · 상태기계 소유 · 작업 순서. yaml `label_source` 중복 키 수정.
- 판 3 (10-13): 작업 ① 의 SPEC_AMBIGUOUS 6곳(Item·ParsedAnswer·LengthInfo·threshold.json·ScoreTable·answers_parsed)을 채움. Claude 안 → Codex 반박(6분 34초) · grok 반박(1–4 는 1차 13KB 가 8분에 끊겨 절반, 5–6 은 8.6KB 로 다시 3분 30초) → Claude 가 근거를 계획·코드에서 재확인. 받아들인 것 — 질문을 펼치고 정답을 붙인 Item(KorFin 정답 연결·KoSGD `서비스/의도`·직전 정답·FunctionChat 선택지 단일 출처·묶음 뒤 Item) · 클래스 ID 문자열 · one-hot Brier · 호출별 LengthInfo·대상 끝 문자 위치·길이만 보는 classify · 인코더 규칙은 fingerprint(grok) · `answers_parsed` 타입·null 규칙 · 개발/시험 기록 분리·봉인·certify 의 t\* 재계산(grok)·mtime 은 보조 · NO_THRESHOLD null · τ 문자열 키 · 묶음 단위 분모 · 모집단 분리(FunctionChat 606 기술 통계)·공통 코호트는 compare.json · 클래스별 재현율·빈 bin 포함 ECE 15·`{num,den}`(grok) · KorFin pooled · 수락 클래스별 위험·길이 구간·사람 이관률 · 논리 요청 단위 비용 · summary 는 RiskCell 에서 · bootstrap 의 FunctionChat 107 묶음(계획과 어긋났던 판 2 고침) · 작업 ① 검사기의 KorFin 거부 결함 · MISSING 구분. 사용자 결정(10-13, 네 가지 모두 권고대로): B1 noul 동률 p ≥ 0.5 → true(grok 안, Codex 는 라벨 순서) · choice 확신은 API `confidence` + `choice_not_argmax` 경고 · 빈 마스크는 분모에서도 뺌 · 잘린 정상 응답의 답은 남김(Codex 안, grok 은 null). 데이터 확인(10-13): 6셋 정답 빠짐 0 · 8,192 초과 0 · K-MHaS 라벨 충돌 묶음 1 · KorFin aspect 미포함 71. 빼고 넣지 않은 것: KorSTS 등급 필드(첫 실행 범위 밖).
- 판 3 보정 (10-13, 작업 ②-0 명세에 대한 Codex 반박 10건 중 9 수용): 펼친 ID 충돌은 k 상한 없이 정규식 · `by_tau` 값에도 `tau` · 시도 기록 `session_id` · `Cost.derived_from`·백분위 보간·n=0 null · 채점 0 인 질문의 null 규칙 · seal fixture 문구 오류(mtime 만 바꾸면 재계산은 통과) 정정 · canary 누출 검사는 작업 ⑥ · score 질문은 task 검사기에서는 오류 목록(문구 분명히 — 반박 1건은 기각, 작업 ① 결정 유지). C3 재계산에서 나온 두 해석 차이 — `n_missing` 은 채점 코호트 안 · `n_calls_missing_usage` 는 응답 코드와 무관하게 usage 를 못 얻은 호출 전부. B(새 세션 중재) 지적으로 결정적 검사(합성 호출 3개: 422+usage · terminal 없음 · bool usage)에서 A 검사기 2 ≠ Codex 시험 1 → 판 3 보정 2: 마지막 terminal 응답의 정수 usage 는 코드와 무관하게 합에, 아니면 누락 (분할 불변식) + `n_missing_on_200`. 결정 기록 — 가정: 실패 응답이 usage 를 주면 그 토큰은 실제로 쓰였다 · 이유: 합이 하한임을 분명히 하고 모든 호출을 한쪽에 넣는다 · 다시 볼 조건: P0 에서 서버가 실패 응답에 usage 를 주지 않거나 오해를 주는 값을 준다고 확인되면.
- 판 3 보정 3 (10-13, 작업 ② 명세 전 Claude): 작업 ② 함수 결과 자료형 7개(§8-5 끝) · `labels` 를 ③ 으로 · B1 토큰 대조 규칙(strip 정확 일치, 중복은 큰 값+경고) · 선택지 ID casefold 충돌 금지·정렬은 코드포인트.
- 판 3 보정 4 (10-13, 작업 ② 명세에 대한 Codex 반박 10건 — 9 수용·1 해당 없음): 선택지 정렬은 B1 에서만(보정 3 의 §2-3 문장이 systemone 요청까지 정렬하는 것으로 읽혀 기존 render fixture 와 충돌 — Claude 실수) · snake_case 는 질문 ID 만 · usage 경고 이름 `usage_input_tokens_invalid` 와 경고 순서·보존 · 경계 입력 `ValueError` 규칙은 작업 ② 명세에.
- 판 3 보정 5 (10-13, ③a 명세 전 Claude): 셋별 `item_id`·`group_id` 정의 · 정확 일치 묶음 키 · 분할 파일 정렬·바이트 규칙 · KOTE 강등은 풀 대표 기준 · `notes` 필드 · ③ 을 ③a(분할)·③b(항목·정답)로 나눔. 규칙 값은 `configs/splits/rules.yaml`.
- 판 3 보정 6 (10-13, ③a 명세에 대한 Codex 반박 11건 — 실제 데이터 대조 포함, 전부 반영): KoSGD row_id·선정 검사 · FunctionChat 첫 user 는 role 로 찾기 · parquet 목록 열 변환 · KLUE 전체 행 · KorFin 행/항목 구별 · 비례 할당 경계 · `Groups`·`PoolResult` · 분할 파일 `sort_keys` · 한글은 강등 감정 이름만 · rules.yaml 의 KOTE 메타데이터 경로(`info` 누락 — Claude 실수). 기존 splits fixture 3개(정수 ID·정렬 전 순서·옛 notes 이름)는 계약에 맞게 고친다.
- 판 3 보정 7 (10-13): KOTE 정답을 평가자 과반수(3/5, raw.json)로 — dichotomized 가 사실상 '1명 이상' 이라 (Claude 집계: 2명 이상은 전부 1, 1명만 고른 것도 81.5% 가 1). 사용자 결정.
