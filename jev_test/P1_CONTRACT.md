# P1 계약 — 결정 모델 평가 코드의 입출력·채점·기록 규칙

작성 2026-10-13 · **판 2** (Codex 반박 1회 반영) · 상태: 구현 전 계약
상위 문서: [`JEV_TEST_PLAN.md`](JEV_TEST_PLAN.md) 개정 12. 이 문서와 계획이 다르면 계획이 기준이고, 이 문서를 고친다.
범위: **첫 실행 = A 묶음 + B1** (계획 §7). B·C·T2·WorkflowEvals·B2 는 이 판에서 정하지 않는다. **score 질문은 이 판의 범위 밖**이다 (A 묶음에 없다) — 검증기·채점은 score 를 만나면 `NotImplementedError` 로 멈춘다.

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
| FunctionChat 606행: 모든 행이 도구 5개(→ 선택지 6), 도구 이름 100종(이름 충돌 0), call 정답 도구 25종 | 10-13 집계 (Claude·Codex 각각) |

---

## 1. 설정 파일 (코드보다 먼저)

### 1-1. `configs/tasks/<set>.yaml` 스키마 (셋마다 하나, 동결 대상)

```yaml
set: kosgd                     # datasets.yaml 의 id
variant: full                  # 판이 있으면 판마다 파일 하나 (kosgd_full.yaml, kosgd_actions_only.yaml)
state:
  kind: json_string            # json_string | plain_text
  keys: [dialogue, catalog]    # json_string 일 때 키 순서 (이 순서로 직렬화, 정렬하지 않는다)
questions:                     # 순서 = 요청에 넣는 순서
  - id: ongoing_1              # ASCII snake_case, 정답 정보 없음
    role: success              # success | diagnostic
    type: choice               # noul | choice
    instructions: "..."        # 비울 수 없다
    options: catalog_intents_plus_none    # choice: 고정 목록 이름 | per_item (FunctionChat 도구처럼 항목마다)
    label: ongoing_slot_1      # 정답을 만드는 규칙 이름 (score/tasks 의 등록 함수)
  - id: act_inform
    role: success
    type: noul
    instructions: "..."
    criteria: {"true": "...", "false": "..."}   # noul 은 항상 명시 (§2-3)
    label: act:INFORM
per_item_questions: null       # KorFin 처럼 항목마다 질문 수가 다르면: {id_pattern: "aspect_{k}", template: "...{ASPECT}...", label: ...}
group_key: dialogue_id         # §6 묶음 키 규칙 이름
```
- 고정 목록(예: KoSGD 카탈로그·의도 선택지)은 `configs/tasks/lists/<name>.json` 에 실제 값으로 둔다. 코드는 목록을 만들지 않고 읽기만 한다 (목록 생성 스크립트는 따로, 라벨만 읽음).
- `configs/tasks/b1.yaml`: B1 시스템 문구 · 사용자 문구 틀 · 라벨 문자열 62개 순서 · 생성 매개변수 (§2-5).
- yaml 은 **중복 키를 거부하는 로더**로 읽는다 (`datasets.yaml` 에서 실제로 중복이 있었다 — 10-13 고침).

### 1-2. 동결 해시
fingerprint 에는 **파일별** sha256 을 넣는다: 쓰인 task yaml 들 · 목록 json 들 · `b1.yaml` · 분할 파일 · 입력 데이터 파일 해시 목록.

---

## 2. 요청 계약

### 2-1. 봉투
`{"model": <모델 yaml 의 served_name>, "state": <문자열>, "questions": {<id>: {...}}}` — 키는 이 셋뿐. 바이트 = `json.dumps(body, ensure_ascii=False, separators=(",", ":"))`, UTF-8. `request_sha256` 은 이 바이트로.

### 2-2. state 는 항상 문자열
- 이유: 모델마다 객체 state 를 렌더링하는 방식이 다르거나(Clef 는 키 정렬) 알 수 없다(pplx). 문자열로 보내면 **모든 모델이 같은 글자를 같은 순서로** 받는다. 계획 §1 도 state 를 "문자열 또는 JSON" 으로 허용한다.
- `json_string`: 내부 객체를 `keys` 순서로 `json.dumps(obj, ensure_ascii=False, separators=(",", ":"))`. `plain_text`: 원문 그대로.

| 셋 | kind | keys |
|---|---|---|
| KoSGD | json_string | `dialogue` (첫 턴~대상 USER 턴의 `{speaker, utterance}`), `catalog` (고정 목록) — `datasets.yaml` 이름 그대로 |
| FunctionChat | json_string | `input_messages` (정규화), `input_tools` — `datasets.yaml` 이름 그대로 |
| K-MHaS · KOTE · KorFin | plain_text | — |
| KLUE-MRC | json_string | `context`, `question` |

- 감사 v3 는 state 를 객체로 다뤘다(R4 가 dict·키를 검사, R7 이 `진행중_1/2` 를 하드코딩). 그래서 동결 때 **감사 v4** 를 따로 만든다: 실제 전송 문자열을 다시 파싱해 독립 원본과 비교하고, 길이는 서버 인코더 입력으로 잰다. 감사 v3 코드는 고치지 않는다 (보존본).

### 2-3. 질문
- 질문 ID·순서·instructions: task yaml 그대로. instructions 는 비우지 않는다.
- **noul 은 `criteria` 를 항상 명시**한다 (task yaml 의 한국어 `true`/`false` 설명). 모델 기본값은 모델마다 다르거나(Clef 영어) 알 수 없어(pplx) 같은 입력을 보장하지 못한다.
- choice `criteria` = `{선택지 ID: 설명}`. 1–255 개, ID 중복 금지, `NONE` 은 다른 ID 와 겹치지 않아야 한다.

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

- 최상위·답 객체의 **추가 키는 허용**하고 `extra_keys` 경고로만 남긴다 (`model`·`id`·`usage`·`provider` 등). `usage` 가 있으면 `input_tokens` 는 정수여야 하고 아니면 경고.
- 검증은 요청 단위로 전부 아니면 전무다 — 질문 하나라도 실패하면 그 요청은 `error`, 나머지 질문 값도 채점에 쓰지 않는다 (§7-3).

### 3-2. 답과 확신 (계획 §4-1)
- noul: p = `noul`. 답 = `true` iff p ≥ 0.5. 확신 = max(p, 1 − p).
- choice: 답 = `choice`. 확신 = `confidence`.
- B1: 라벨 후보 분포를 재정규화 → 답 = argmax (동률이면 라벨 순서 앞) → 확신 = 그 확률. noul 의 p = P(대응표에서 `true` 인 라벨).
- B1 검사: 모든 라벨 토큰이 `top_logprobs` 안에 유한값으로 있어야 한다 (≤ −9999 는 빠진 것). 하나라도 빠지면 그 호출은 `error/b1_missing_label`.

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

### 4-3. 잘림 판정 (계획 §4-2·§4-4)
- 보내기 전에 모델 yaml 의 인코더 규칙으로 **잘리기 전 길이** $\ell$ 와 **대상 발화 끝 토큰 위치** $e$ (state 안에서 질문 대상 발화가 끝나는 곳; 대상 발화가 없는 셋은 state 끝)를 잰다. 인코더 규칙(래퍼 포함)은 P0 에서 모델마다 확정해 모델 yaml 에 둔다.
- $\ell \le L_m$ → 잘림 아님 (`usage.input_tokens == L_m` 이어도).
- $\ell > L_m$ → `truncated`. 남는 state 길이 $r = L_m −$ 고정부 길이. $e > r$ 이면 `target_cut`, 아니면 `tail_cut`. 서버가 거부하면 `rejected/input_limit` 이 우선.
- `usage.input_tokens` 는 **일치 검사**로만 쓴다: $\ell \le L_m$ 인데 `usage.input_tokens ≠ ℓ` 이면 `length_mismatch` 경고 (인코더 규칙이 틀렸다는 신호 — 보고한다).

---

## 5. 기록·resume·보존

### 5-1. 위치
```
jev_test/results/<safe_model>/<run_id>/A/<set>/<variant>/
├─ fingerprint.json   # 커밋
├─ threshold.json     # 커밋 — 시험 점수를 읽기 전에 쓴다
├─ scores.json        # 커밋 (집계만, 문항 텍스트 없음)
├─ risk.json          # 커밋
├─ summary.json       # 커밋 — evalcommon 호환 요약 (§8-3)
├─ attempts.jsonl     # 커밋 안 함
└─ final.jsonl        # 커밋 안 함
```
`attempts.jsonl`·`final.jsonl` 은 `.gitignore` (데이터 라이선스 — 재배포 금지). 요청 원문은 저장하지 않는다 — 분할 파일 + task yaml + 입력 데이터로 다시 만들고 `request_sha256` 으로 대조한다.

### 5-2. 식별자 세 단계
- `logical_id` = `<set>:<group_id>:<item_id>` (§6).
- `call_id` = `logical_id` (결정 모델) 또는 `logical_id + "/" + question_id` (B1).
- `attempt` = `call_id` 안의 시도 번호 (1부터, resume 을 넘어 이어 센다).
- B1 의 논리 요청 해시 = `sha256("".join(sorted(call request_sha256)))`. 호출 하나가 `error` 여도 나머지 호출은 끝까지 돈다(진단용). 논리 상태는 호출 중 가장 나쁜 것 (`error` > `rejected` > `truncated` > `ok`).

### 5-3. 레코드
- `attempts.jsonl`: `{call_id, logical_id, attempt, started_at, ended_at, latency_ms, http_status, retry_after, transport_error, terminal, request_sha256, response_raw}` — `terminal` = 이 시도로 그 호출이 끝났는가 (200·422·재시도 없는 오류·재시도 소진). `response_raw` 는 UTF-8 문자열, 못 읽으면 `{"b64": ...}`.
- `final.jsonl`: `{logical_id, status, reason, answered_over_limit, warnings, calls: [{call_id, attempts, status, reason, request_sha256, length_tokens, target_end, usage, answers_parsed, label_map?, top_logprobs_raw?}]}`.

### 5-4. 판 파생 (KoSGD)
- 질문을 **따로** 채점하는 모델(pplx, B1)의 행동판은 전체판 레코드에서 행동 질문 10개(성공 8 + 진단 2)만 골라 만든다. 레코드에 `derived_from: <전체판 run 경로>` 를 적고 호출·비용은 0 으로 센다. 전체판 논리 요청이 `ok` 가 아니면 파생도 같은 상태·사유.
- 질문을 **함께** 채점하는 모델(Clef 계열)은 행동판을 따로 돌린다.
- 어느 쪽인지는 모델 yaml 의 `question_scoring: joint | separate`.

### 5-5. resume
1. 기존 `fingerprint.json` 이 `started_at` 을 빼고 같아야 한다. 다르면 거부 (C5).
2. `final.jsonl` 에 있는 `logical_id` 는 건너뛴다. 중복이면 거부.
3. 없는 ID 는 `attempts.jsonl` 에서 호출별로 복구한다: `terminal` 인 시도가 있는 호출은 **그 응답으로 결과를 다시 만든다 (다시 호출하지 않는다)**. terminal 이 없는 호출만 남은 재시도 예산 안에서 다시 시도한다.
4. 파일 끝 줄이 JSON 이 아니면(쓰다 끊김) 그 줄만 버리고 경고. 중간 줄이 깨졌으면 거부.
5. 줄마다 flush + fsync. final 줄은 그 논리 요청의 모든 attempts 줄 뒤에.

### 5-6. 비공개 보존 (커밋하지 않는 재현 자료)
- 실행이 끝나면 `jev_test/archive/<run_id>.tar.zst` (git 제외) 를 만든다: `attempts.jsonl`·`final.jsonl`·쓰인 task yaml·목록·분할 파일·`b1.yaml`·입력 데이터 파일 해시 목록 + 그 아카이브의 sha256 을 `fingerprint.json` 에 기록.
- 입력 데이터 자체는 `jev_test/dataset/<set>/` (git 제외)에 고정 revision 으로 두고, 파일별 sha256 을 `dataset/<set>/SHA256SUMS` 로 남긴다. 재채점은 아카이브 + 같은 해시의 데이터로 한다.
- 이 자료가 사라지면 재채점은 불가능하다 — 해시는 변경을 알려 줄 뿐 복구하지 못한다. 보관 위치는 이 Mac 의 작업 폴더 하나뿐이라는 한계를 결과에 적는다.

---

## 6. 평가 풀·묶음·분할 (계획 §4-3)

분할 파일 `configs/splits/<set>.json` = `{set, seed, pool_rule, allocation, groups: {group_id: [item_id…]}, representative: {group_id: logical_id}, dev: [group_id…], test: [group_id…], diagnostic_demotions: [...] }`. **라벨만 읽는 스크립트**가 만든다 (모델 호출 없음). seed = `datasets.yaml` 의 20261012.

| 셋 | 항목 | 묶음 키 | 평가 풀 (cap) |
|---|---|---|---|
| KoSGD | USER 턴 | `dialogue_id` | 10-12 선정 그대로 (`audits/kosgd_audit/audit_result.json`, 대화당 1턴 3,000) |
| FunctionChat | 행 (`serial_num`) | 연결요소 — 첫 user 메시지 `content` 일치 또는 `json.dumps(input_tools, sort_keys=True, ensure_ascii=False)` 일치로 union-find. **107 이 아니면 멈춘다.** `group_id` = 요소 안 최소 serial | 606 전부 |
| K-MHaS · KOTE | 행 | 원문 문자열 (같은 문장은 한 묶음) | 묶음 단위 단순 무작위 cap |
| KorFin-ASC | (SRC, aspect) 행 → SRC 하나가 요청 하나 | SRC 문자열 | SRC 묶음 단위 단순 무작위 1,000. aspect 질문은 원 데이터에 처음 나온 순서, ID `aspect_1…k` |
| KLUE-MRC | (context, question) | context 문자열 | `source` 별 **비례 할당**(최대 나머지 방식)으로 context 묶음 2,000 |

결정적 규칙:
- 단순 무작위 cap: `ids = sorted(group_ids)`; `random.Random(f"{seed}:{set}:pool").sample(ids, cap)`.
- 비례 할당: 층별 묶음 수 $G_h$, 할당 $\lfloor cap \cdot G_h / G \rfloor$ + 나머지는 소수부가 큰 층부터 (동률은 층 이름순). 층 안에서는 위 단순 무작위 (`…:pool:{h}`). 할당표를 `allocation` 에 적는다.
- 대표: `random.Random(f"{seed}:{set}:rep:{group_id}").choice(sorted(members))` (KoSGD 는 선정 그대로).
- 분할: `ids = sorted(풀의 group_id)`; `random.Random(f"{seed}:{set}:split").shuffle(ids)`; 앞 `floor(0.2·len)` 개발.
- KOTE 진단 강등: 평가 풀 전체 라벨에서 양성 < 50 인 감정을 `diagnostic_demotions` 에 적는다.

---

## 7. 채점

### 7-1. 셋별 적용표
요청 오류 $\ell_i$ = 성공 질문 중 하나라도 틀림 (KoSGD 칸 예외). 확신 $s_i = \min_{j \in J_i}$ 질문 확신 (성공 질문 전체). $v_i = 1$ iff 상태 `ok`.

| 셋 (판) | 성공 질문 | 진단 | 질문별 F1 | 보정 |
|---|---|---|---|---|
| KoSGD 전체판 | `ongoing_1·2` (묶음) + 행동 noul 8 | AFFIRM_INTENT·NEGATE_INTENT | noul: 2클래스 macro-F1. 칸: 고정 칸 정답 기준 macro-F1 (§7-2) | noul: 질문별. 칸: 고정 칸 정답 기준 칸별 |
| KoSGD 행동판 | 행동 noul 8 | 같음 | 같음 | 같음 |
| FunctionChat | 행동 choice 3 + 도구 choice 6 (도구 5 + NONE) | — | 행동: 3클래스 macro-F1. 도구: **macro-F1 을 내지 않는다** — call 행의 도구 정답률, 비호출 행의 `NONE` 정답률을 따로 | 행동: 3선택지. 도구: 6선택지 top-label ECE·Brier·log loss (모든 행이 6선택지) |
| K-MHaS | noul 9 | — | 질문별 2클래스 macro-F1 | 질문별 |
| KOTE | noul 8 − 강등 | 강등된 감정 | 같음 | 같음 |
| KorFin-ASC | aspect 마다 choice 3 | — | 모든 aspect 질문을 합친 3클래스 macro-F1 | 합쳐서 |
| KLUE-MRC | noul 1 | — | 2클래스 macro-F1 | 그 질문 |

- macro-F1 의 클래스 = **정답 또는 예측에 한 번이라도 나온 클래스**. 둘 다에 없는 클래스는 넣지 않는다.
- ECE: 15 등폭 bin `[0,1/15), …, [14/15, 1]` (마지막 닫힘), bin 마다 건수·정확도·평균 확신 함께. log loss clip `[1e-12, 1]`.

### 7-2. KoSGD 칸
- 정답 칸 고정: 정답 의도(`NONE` 아닌 것, 0–2개)를 **카탈로그 순서**로 정렬해 ①·② 에 넣고 모자라면 `NONE`. 질문 문구("서비스 목록에서 앞에 있는 서비스의 일 = ①")와 같은 규칙이다.
- **묶음 정답(요청 오류·위험에 씀)**: 순서 무관 — $\{a_1, a_2\}$ 다중집합 == 정답 다중집합, 그리고 `NONE` 아닌 같은 값이 두 칸에 없음.
- **칸별 F1·보정**: 위 **고정 칸 정답**으로만 계산한다 (예측을 보고 정답을 재배정하지 않는다 — 재배정하면 보정이 낙관적으로 치우친다, Codex 반례: Brier 1.96 → 0.0002).
- 진단 열: "순서만 틀린 묶음" 건수 (묶음 정답이지만 고정 칸 정답과 다른 것).
- 앞 턴 베끼기: 묶음 정답률만.

### 7-3. 코호트
- 모델별 채점 코호트 = 상태 `ok` 인 논리 요청 (질문 전부). `truncated`(③ 포함)·`rejected`·`error` 는 채점·보정에서 빠지고 처리율 분모에만 남는다.
- 공통 코호트 = 비교하는 모든 모델(B1 포함)이 `ok` 인 `logical_id`.

### 7-4. 위험 (`risk.json`, 계획 §4-2)
(모델 · 셋 · 판 · τ) 마다:
`{status: MEETS|FAILS|UNDERPOWERED|NO_THRESHOLD, insufficient_by_design: bool, t_star, dev: {groups, n, k}, test: {groups (=|T|), n, k, U, coverage, b_flip}, by_status: {ok, rejected, truncated, error}, accepted_mix: {class/service/question-count 분포}, diagnostic_error_in_accepted: {question_id: {n, wrong}}}`.
- `insufficient_by_design` = $|T| < n_{\min}(\tau)$ — **플래그일 뿐 계산은 그대로 한다** (상태는 정상 규칙으로 정해지며 MEETS 가 될 수 없다). 계획 §4-2 3번의 "따로 표시" 가 이 플래그다.
- `b_flip` 은 MEETS 일 때만, 아니면 null. NO_THRESHOLD 면 `t_star`·`test.n`·`k`·`U` 는 null, coverage 0.
- `threshold.json` (`t_star` 들) 은 개발 표본만으로 계산해 **시험 레코드를 읽기 전에** 쓴다. certify 단계는 `threshold.json` 이 시험 `final.jsonl` 보다 먼저 쓰였는지(mtime 과 내용 해시) 확인한다.

### 7-5. 통계 설정
- 모델 간 차이: 묶음 단위 paired bootstrap, 2,000 회, `random.Random(f"{seed}:boot:{set}")`, 시험 표본, 임계값은 고정(다시 고르지 않는다). 처리율·F1 차이에만.

---

## 8. 구현 구성 — 기능별, 바이브코딩하기 편하게

사용자 지시(10-13): **기능별로, 기능 하나씩 AI 에게 맡겨 고치기 편하게.**

### 8-1. 규칙
- **파일 하나 = 기능 하나.** 첫머리 docstring 에 "무엇 · 입력 · 출력 · 이 계약의 몇 절". 그 파일만 열어도 고칠 수 있게.
- **작게**: 파일 ≤ 200 줄, 함수 ≤ 50 줄 정도.
- **입출력은 정해진 곳에만**: 파일 읽기 `io/` (설정·데이터·분할·레코드), 네트워크 `client/`. 나머지(`contract/`·`data/`·`score/`)는 순수 함수 — 이미 읽은 객체를 받는다.
- **모듈 사이는 `types/` 의 dataclass 만**: `Item`(항목·정답) · `TaskSpec`·`QuestionSpec` · `Request`·`CallRecord`·`AttemptRecord`·`FinalRecord` · `ParsedAnswer` · `SplitPlan` · `LengthInfo` · `Threshold` · `RiskCell` · `ScoreTable`.
- **상태기계는 한 곳**: `run/executor.py` 만 시도 시작·재시도·terminal 판정·resume 복구를 소유한다. `client/` 는 **한 번의 시도**만 (재시도 안 함), `io/records.py` 는 줄 추가·읽기만.
- **기능마다 짝 테스트** `tests/<폴더>/test_<파일>.py` + 경계마다 통합 테스트 하나. GPU·서버 없이 fixture 로 돈다. 한 기능을 고치면 그 단위 테스트와 해당 경계 통합 테스트를 같이 돌린다.
- **설정은 코드 밖**: 문구·선택지·라벨·재시도·cap 은 yaml. 코드에 박지 않는다.
- **`jeveval/README.md` 기능 지도**: 파일마다 한 줄 + 의존 방향 `run → client/io → score/data/contract → types` (거꾸로 금지).

### 8-2. 구성
```
jev_test/jeveval/
├─ types/      records.py · specs.py · results.py
├─ io/         config.py (yaml, 중복 키 거부) · sources/<set>.py (원본 읽기) · splits.py · records.py · archive.py
├─ contract/   render.py (§2-2 state) · request.py (§2-1·2-3·2-4) · response.py (§3-1) · b1_prompt.py (§2-5)
├─ data/       items/<set>.py (원본 → Item, 순수) · grouping.py · pool.py · split.py (§6)
├─ score/      answers.py (§3-2) · labels.py (정답 규칙 등록) · tasks.py (§7-1) · kosgd_slots.py (§7-2) · calibration.py · f1.py · risk.py (§7-4) · bootstrap.py
├─ client/     systemone.py · vllm_chat.py (한 번의 시도)
├─ reference/  pplx_runner.py · clef_runner.py (참조 구현을 고치지 않고 부르는 얇은 층 — T0·C1 temperature 경로)
└─ run/        executor.py (상태기계) · length.py (§4-3) · cli.py (하위 명령: split · run · score · certify)
```

### 8-3. 결과 규약
새 결과(`scores.json`·`risk.json`)는 이 계약이 정하고, 최상위 집계와 맞추기 위해 `summary.json` 을 `reranker_test/evalcommon` 의 `make_score_summary` 로 추가로 쓴다: `metric = "coverage_at_risk_2pct"` (주 지표 판·τ 2%), `score` = 그 처리율 (NO_THRESHOLD·UNDERPOWERED 면 0), `extra = {status, insufficient_by_design}`.

### 8-4. 작업 순서 (각 작업 = 파일 몇 개 + 그 테스트, 따로 리뷰·실행)
1. `types/` + `io/config.py` + task yaml 스키마 검사 + §9 fixture
2. `contract/` + `score/answers·labels·f1·calibration·kosgd_slots`
3. `data/` (묶음·풀·분할) + `io/sources` + `io/splits` → 분할 파일 생성
4. `client/` (한 번의 시도) + `io/records`
5. `run/executor` (상태기계·resume) + `run/length`
6. `score/tasks·risk·bootstrap` + `run/cli` + `io/archive` + `reference/`

---

## 9. 최소 fixture (`tests/fixtures/`, 코드보다 먼저)

| fixture | 확인 |
|---|---|
| `render/*.json` → 기대 state 문자열·요청 바이트·sha256 | §2 직렬화 바이트 고정 |
| `responses/valid_*`, `invalid_*` (사유 코드마다 1개 이상, 중복 키·bool·추가 키 포함) | §3-1 — 반올림 있는/없는 응답 둘 다 통과 |
| `scoring/kosgd_slots.json` | 정답 0·1·2개, 같은 값 두 칸, 순서만 틀림, Codex 반례(고정 칸 정답 기준 Brier 1.9602) |
| `scoring/f1_classes.json` | 미출현 클래스 제외 규칙 |
| `scoring/risk_cases.json` | U(6,600)=1.964% · U(0,150)=1.977% · U(1,150)=3.123% · U(0,252)=1.18% · U(0,86) · $n_{\min}$ · $b_{\rm flip}$ · 네 상태 + 플래그 |
| `splits/*.json` | 합성 행으로 union-find·비례 할당(최대 나머지)·대표·분할 결정성 |
| `resume/*` | 끝 줄 깨짐 · 중간 줄 깨짐 · fingerprint 불일치 · 중복 ID · terminal 응답 뒤 끊김(다시 호출하지 않음) · 재시도 예산 누적 |
| `length/*.json` | $\ell = L_m$ (잘림 아님) · $\ell = L_m + 1$ · target_cut vs tail_cut (발화 **끝** 위치 기준) |
| `temperature/pplx_path.json` | `reference/pplx_runner.py` 경로에 고정 logit($|z| ≈ 1.55$ 포함) → softmax(z/T) 한 번. 빼거나 두 번 적용하는 오류 주입 시 실패 |
| `b1/*.json` | 라벨 대응·재정규화·−9999·라벨 누락 → `error` · 대응을 바꾼 noul 의 p |

---

## 10. P0 에서 확인해 이 문서를 고칠 것

- pplx: 길이 초과 응답 형태(422 메시지) · 반올림 · 문자열 state 처리. Clef(SGLang): `usage.input_tokens` · 길이 초과 동작. 각 서버의 `served_name`.
- 모델별 인코더 규칙(래퍼 포함)·$L_m$·고정부 길이 계산법.
- B1 진입 조건 (계획 §2-3) · 서버별 안전 동시성.
- 감사 v4 (§2-2) — 동결 때.

## 11. 판 이력

- 판 1 (10-13): 초안.
- 판 2 (10-13): Codex 반박 반영 — 잘림 판정 경계 오류(ℓ = L_m 오판, 발화 시작이 아니라 끝 위치) · state 키 이름을 datasets.yaml 로 · 감사 v4 필요 · noul criteria 명시 · 422 원인 분리 · 상태와 사유 분리 · 비공개 보존 · FunctionChat 도구 macro-F1 제외(정답 도구 25/100, 모든 행 6선택지) · KoSGD 칸 보정은 고정 칸 정답 · B1 선택지에 ID · 세 단계 식별자 · terminal 응답 복구 · 판 파생 · 설정 스키마 · 평가 풀 추출 · 코호트 · 검증기 문법 · score 범위 밖 · 원리적 부족은 플래그 · evalcommon 호환 · 상태기계 소유 · 작업 순서. yaml `label_source` 중복 키 수정.
