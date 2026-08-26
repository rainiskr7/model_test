# multimodal 발행 계약 (v1)

이 문서가 **어떤 multimodal 수치를 인용해도 되는지에 대한 유일한 기준**이다.
`results/` 에는 오염된 런과 진단용 런이 섞여 있으므로, 여기 규칙을 통과하지 못한
숫자는 인용하지 않는다.

agent 트랙(`../AGENT_TRACK_CLOSEOUT.md`)과 같은 교훈에서 출발한다: 문서에
"인용 금지"를 적어두는 것만으로는 부족했다. 그래서 규칙을 코드로 옮긴다.

```
python3 derive_multimodal_publish.py --base . --write   # 산출물 -> sidecar
python3 report_multimodal_tracks.py  --base .           # 발행 가능한 수치만 출력
python3 report_multimodal_tracks.py  --base . --run <session> --strict  # CI
```

---

## 0. 불변 원칙

1. **원본 불변.** `results.json` / `summary.json` / `*.jsonl` / `run_config.json` 을
   절대 수정하지 않는다. 파생물은 `_derived/` 하위에만 쓴다.
   derive 실행 전후로 원본 SHA-256 이 전부 동일해야 한다.
2. **재추론 금지.** 기존 산출물만으로 오프라인 재집계한다.
3. **축 합산 금지.** `aggregation_allowed` 는 v1 에서 항상 `false`.
   50/30/20 종합 점수는 폐기한다.
4. **native 단위로 표시한다.** 0–1 일괄 정규화를 하지 않는다.
   `1850/2577 = 71.79%` / `7.4/10 — PROVISIONAL` / `TTFT P50 0.48s`.
5. **거부된 런의 점수는 stdout·Markdown 어디에도 출력하지 않는다.** 사유만 적는다.
6. **derive 는 NATIVE 를 강등하지 않는다.** bulk/passive derive는 유효한 기존
   `NATIVE` sidecar를 기본적으로 건너뛰고 승격만 허용한다. `--force`로만 덮어쓸 수
   있으며, 이때 손실될 완료 시각과 protocol provenance를 먼저 경고한다.

v1 sidecar 실제 경로:

- 일반 벤치 source 디렉터리: `<bench>/_derived/publish.json`
- KRETA source(JSONL 1개 단위): `kreta/_derived/<jsonl-stem>.publish.json`

파일명 대신 내부 `schema_version`으로 형식 버전을 판별한다.

---

## 1. 오류 판정 술어 (실측 근거 기반)

KRETA jsonl 21개 54,117 레코드를 실측한 결과 `response` 필드 타입이 정확히
두 갈래로 갈린다:

| 타입 | 건수 | 의미 |
|---|---|---|
| `str` | 44,579 | 모델 텍스트 |
| `dict` | 9,538 | 예외 반환값 |

`dict` 는 전부 `{'error': ...}` 두 형태뿐이다:
- `{'error': "Error code: 404 - ... Model not found ..."}` — 5,154건
- `{'error': 'Request timed out.'}` — 4,384건

정상 응답 중 dict 는 **0건**이다. 따라서 판정은 **문자열 prefix 가 아니라 타입**으로 한다.
모델이 답변 본문에 `{'error': ...}` 라고 써도(실제로 `{B}`, `{A}` 같은 출력이 있다)
`str` 이므로 오탐하지 않는다.

```python
def classify(record) -> Literal["MEASURED", "ERRORED", "UNRESOLVED"]:
    if record.get("error"):                       # 레코드 레벨 error 필드
        return "ERRORED"
    resp = record.get("response", _MISSING)
    if isinstance(resp, Mapping):
        return "ERRORED" if resp.get("error") else "UNRESOLVED"
    if isinstance(resp, str):
        return "MEASURED"                         # 빈 문자열도 MEASURED (모델 무응답)
    return "UNRESOLVED"                           # 누락 / None / 그 밖의 타입
```

- `ERRORED` 와 `UNRESOLVED` 는 따로 집계하되 **둘 다 발행을 차단**한다.
- **기존 `if_right` / `parsed_pred` / `correct` / 도메인 집계를 신뢰하지 않는다.**
  `MEASURED` 레코드에 대해서만 채점기를 다시 적용한다.
  (오염 런은 오류 문자열에서 선택지를 뽑아 `if_right=true` 를 만들었다.)

---

## 2. 두 수치를 분리한다

분모를 바꾸지 않는다. 공식 published 점수와 대조 가능해야 하기 때문이다.

```
strict      = correct_measured / attempted    <- 공식 비교용. 분모 고정.
conditional = correct_measured / measured     <- 운영 참고용.
attempted = measured + errored + unresolved
```

`errored > 0` 이면 **strict/conditional 둘 다 출력하지 않는다.** sidecar 에는
진단용으로 기록하되 reporter 는 숨긴다.

---

## 3. 상태 enum

| 상태 | 의미 | publishable |
|---|---|---|
| `NATIVE` | 러너가 계약을 지켜 직접 쓴 sidecar | ✅ |
| `LEGACY_REVALIDATED` | 기존 산출물을 재집계해 검증 통과 | ✅ |
| `REJECTED` | 오염·불완주·검증 실패 | ❌ |
| `INSUFFICIENT_PROVENANCE` | 프로토콜 복원 불가 | ❌ |
| `UNSCORED` | 채점이 존재하지 않음 | ❌ |

우선순위: `REJECTED` > `UNSCORED` > `INSUFFICIENT_PROVENANCE` > `LEGACY_REVALIDATED` > `NATIVE`.
`UNSCORED`는 채점 없는 **KOFFVQA / generation**에만 허용한다. 다른 벤치나 variant가
UNSCORED를 내면 schema 위반이며 `--strict` 성공 예외가 아니다.

publishable sidecar의 `counts`는 `attempted` / `measured` / `errored` /
`unresolved` / `correct_measured` 비음수 정수를 모두 가져야 한다.
`correct_measured <= measured <= attempted` 및
`attempted = measured + errored + unresolved`를 단언한다. 정확도 벤치가 아닌 B3,
B4, judge에서 `correct_measured`는 각각 schema 통과, 완주 latency, 유효 judge 점수처럼
그 벤치의 계약상 유효한 primary measurement 수를 뜻한다.

**`provisional=true`** (판정기 기준, 인간 검증 없음) 는 publishable 과 직교한다.
발행 가능해도 반드시 PROVISIONAL 딱지를 붙인다.

---

## 4. 프로토콜 지문 — 기록된 것과 추론한 것을 구분한다

지문에 모델명·run ID 를 넣지 않는다(모델 간 동일 프로토콜 비교가 목적).
정렬된 canonical JSON 의 SHA-256.

**핵심 결정:** 메타데이터가 null 이라고 무조건 발행 불가로 두지 않는다.
`recorded`(산출물에 있음) 와 `inferred`(러너 규약에서 복원) 를 나눠 기록하고,
`inferred` 항목을 보고서에 각주로 노출한다.

```json
"protocol": {
  "fingerprint": "sha256:...",
  "recorded": {
    "dataset_item_digest": "0cc4ed8281009d38",
    "dataset_provenance": {"git_commit": "c273302...", "revision": null},
    "mode": "direct",
    "max_tokens": 32,
    "answer_parser_version": "kreta-response-choice-v2",
    "answer_parser_hash": "sha256:..."
  },
  "unknown": ["temperature", "seed"],
  "complete": false
}
```

판정:
- `unknown` 이 **비교 결과를 바꿀 수 있는 항목**(dataset item digest, mode, split,
  category filter, limit)을 포함하면 → `INSUFFICIENT_PROVENANCE`.
- `unknown` 이 그 외 항목(temperature/seed 등 decoding 세부)만 포함하고
  나머지 검증을 통과하면 → `LEGACY_REVALIDATED` + 경고.

KRETA는 독립 response parser의 결과만 채점에 사용한다. 상류 `pred_indexs` /
`if_right` / `results.json.overall_accuracy`는 비교용 provenance일 뿐이다. 상류 parser와
불일치해도 발행을 막지 않고 `upstream_comparison`과 `warnings`에 기록한다.
반대로 dataset item digest가 불명이면 무엇과 비교하는지 자체가 불명이라 버린다.

dataset 정체성은 외부 원본 데이터셋의 expected-ID가 아니라 **우리 산출물에 기록된
문항 key 집합**으로 계산한다. key를 문자열로 만든 뒤 정렬하고 개행으로 join하여
SHA-256을 계산하며, 앞 16자를 `dataset_item_digest`로 기록하고 지문에 포함한다.

| 벤치 | 산출물 문항 key |
|---|---|
| KRETA | JSONL의 `id` |
| K-DTCBench | `results.json`의 `index` |
| K-MMBench | `results.json`의 `index` |
| MTVQA-KR | `results.json`의 `(row_idx, qa_idx)` |
| KOFFVQA API judge | judge `results.json`의 prediction 원본 `dataset_item_id` (xlsx `index`) |

`git_commit` / `huggingface_id` / `revision` 등 dataset provenance는 정보용으로
sidecar에 계속 기록하지만 protocol fingerprint 계산에서는 제외한다. 같은 코호트에서
repo commit이 갈리면 보고서 표 아래에 문항 집합은 동일하다는 각주를 남긴다.
KOFFVQA `prediction_sha256`도 judge 결과와 모델별 prediction artifact의 결합 검증에만
쓰며 protocol fingerprint에서는 제외한다.

향후 NATIVE 런은 러너 인자가 아니라 `apply_serving_constraints()` 적용 **후** 실제
전송된 decoding 설정을 `run_config.decoding`과 protocol fingerprint에 기록한다.
원래 요청값은 `decoding_requested`에 보존한다. 제거된 파라미터 목록,
`SERVING_MAX_OUTPUT_TOKENS`의 유효 상한, 최종 `skip_special_tokens` 값도
`serving_constraints`로 지문에 포함한다. 명시적으로 제거된 파라미터는 `unknown`이
아니며, 서로 다른 serving constraint를 같은 프로토콜로 비교하지 않는다.

**지문은 값을 어떻게 알았는지가 아니라 실효 프로토콜 값으로 계산한다.**
`recorded`(산출물에 있음)와 `inferred`(러너 규약에서 복원)의 구분은 sidecar와
보고서 각주에 그대로 남지만, 지문 입력에서는 하나로 합친다. `inferred`는 `value`만
들어가고 `basis` 문자열은 빠진다. 같은 key가 양쪽에 있고 **값이 같으면** 하나로
합치고, **값이 다르면 실패시킨다** — 한쪽이 no-op으로 버려지고 다른 쪽이 적용된
제약을 주장하는 경우도 불일치다. 자기 프로비넌스와 모순되는 프로토콜 정체성을
발행하느니 산출물을 거부하는 쪽이 낫다.

근거: 프로비넌스 기록을 늘리면 그 순간 모든 코호트가 과거 런과 갈라진다. 실측 두 건:

- `serving_constraints` — 옛 산출물에는 키가 없고, 새 러너는 `SERVING_*` 미설정
  시에도 전부 비어 있는 스냅샷을 기록한다. `shared/serving/constraints.py`는 env
  미설정 시 자기 자신을 no-op으로 규정하므로 두 런은 같은 요청을 보냈다. 따라서
  **전부 no-op인 스냅샷은 키가 없는 것과 동일하게 취급한다.** 알려진 다섯 필드는
  `None`만 미설정으로 세며, `force_skip_special_tokens=false`는 적용된 제약이므로
  코호트를 가른다. 이 코드가 모르는 필드는 값이 있으면(`None`/`[]`/`{}`/`""`가
  아니면) 적용된 제약으로 본다 — 모르는 제약을 부재로 읽으면 제약이 걸린 런과
  안 걸린 런이 같은 코호트에 들어간다.
- KRETA `max_tokens` — 레거시 9개 런은 `inferred {"value": 32, "basis": ...}`,
  새 러너는 `recorded 32`. 실제 요청값은 같다.

이 원칙은 이미 `dataset_provenance`에 적용돼 있던 것과 같다 — 레거시 KRETA direct
9런은 repo commit이 제각각인데도 문항 집합이 같아 한 코호트다. 프로비넌스 필드가
늘어난다고 프로토콜 정체성이 바뀌어서는 안 된다.

지문 정의가 바뀌면 발행된 지문 문자열이 전부 바뀐다. 기존 NATIVE sidecar는 저장된
지문과 재계산 지문을 대조하므로 무결성 검사에 걸려 `REJECTED`가 된다. 정상 동작이며,
`--native`로 재생성해야 한다(수동 편집 금지).

문항 집합 digest와 별도로 **기대 건수**도 벤치별 상수로 단언한다
(KRETA 2577, K-MMBench 4329, K-DTCBench 240, KOFFVQA 275, MTVQA-KR 558).
건수가 다르거나 문항 key가 누락·중복되면 `REJECTED`.

---

## 5. 벤치별 publishable 규칙

| 벤치 | 조건 |
|---|---|
| K-DTCBench | 240건 완주, `errored=0`, `unresolved=0`, raw 재집계 == summary |
| K-MMBench | 4329건 완주, 오류 0, category filter/limit 이 variant 와 일치. 전체 vs 선별은 **별도 코호트** |
| MTVQA-KR | 558건 완주, 오류 0, raw 재집계 == summary |
| KRETA | JSONL **1개 = 1 source 단위**, 2577 unique id와 item digest, 오류 0, unresolved 0, mode 기록됨. 고정 parser로 `response`를 독립 채점하며 상류 파생 필드·summary 일치는 발행 조건이 아님 |
| KOFFVQA 생성 | 항상 `UNSCORED` — 채점이 없다 |
| KOFFVQA 판정 | 275건 전부 채점, judge error 0, 모든 score 가 **정수 0–10**, prediction SHA 일치 → `provisional=true` |
| B3 | `total>0`, manifest 전 항목 시도, 오류 0, raw `parse_ok`/`schema_check`/`value_check` 재집계 == summary. **기존 7개는 total=0 이므로 전부 REJECTED** |
| B4 | 전 condition·rep 완주, 실패 0, `runs.json` 재계산 percentile == summary. latency 축별 발행. **점수가 아니므로 strict/conditional 없음** |

---

## 6. 대표 런 선정

선정 키: `(benchmark_id, variant, protocol.fingerprint, model_identity.canonical_id)`

`model`은 산출물에 기록된 서빙명을 그대로 보존한다. `configs/model_identity.json`에
명시된 이름만 canonical id로 합치며, 미매핑 이름은 추측하지 않고 자기 이름을
canonical id로 사용하면서 보고서에 경고한다. 특히 fp8과 non-fp8은 별개 모델이다.

1. sidecar 없는 디렉토리 → 점수 없이 "게이트 기록 없음" 으로만 보고.
2. `publishable=true` 인 sidecar 만 후보.
3. **원자적 선택** — overall / category / System1·2 축은 한 런에서 통째로 가져온다.
   카테고리별로 다른 런을 고르면 모델마다 유리한 카테고리가 조합된 모자이크가 된다.
4. 같은 코호트에서 **정규화한 session identity**(`.bad` 접미사만 제거),
   source-relative artifact role/path와 SHA-256 쌍의 집합 및
   `counts`·`metrics`·`provisional` 측정 payload가 모두 같으면 동일 런의 복사본으로
   접는다. session이 다르면 바이트와 payload가 같아도 독립 재실행이므로 접지 않고
   재현성 비교에 남긴다. payload가 같고 status만 다르면 `NATIVE`를 먼저 유지하며, 그 다음
   `.bad` 접미사 없음, 짧은 경로, 사전순으로 정한다. SHA만 같거나 payload가 다르면
   절대 접지 않는다.
5. 복사본을 접은 뒤 후보가 여럿이면 신뢰 가능한 `completed_at_utc` 최신 하나.
   완료 시각이 **없는** 런은 최신임을 보일 수 없으므로, 시각이 있는 런이 같은
   코호트에 있으면 **대표 자격에서만** 빠진다. 코호트에는 그대로 남아 재현성 산포에
   참여하며, 보고서가 어느 런이 왜 빠졌는지 각주로 남긴다. 레거시 KRETA sidecar는
   완료 시각이 전부 `null`이라, 이 규칙이 없으면 레거시 기준선을 재현할 때마다 그
   모델이 표에서 통째로 사라진다 — 유효한 측정을 잃고 아무것도 새로 말하지 못한다.
   후보가 **전부** 무시각이면 종전대로 자동 선정하지 않는다.
6. **점수·분모·런 이름 문자열을 tie-break 로 쓰지 않는다.**
   (`report_agent_tracks.py:125` 가 `(den, run_name)` 튜플 비교라 동일 분모에서
   문자열 정렬로 떨어지는 버그가 남아 있다. 여기서는 반복하지 않는다.)
7. 결정 불가(후보가 전부 timestamp null, 동시각 동률) → 자동 선정하지 않고
   후보 목록만 점수 없이 표시. `--strict` 에서 exit 1.

복사본을 접은 뒤 같은 코호트에 런이 둘 이상 남으면 가장 오래된 런을 기준, 최신
선정 런을 대표로 두고 재현성 산포를 표시한다. `fraction` 축은
`max(분자)-min(분자) <= ceil(0.01 × 분모)`를 건수와 %p로 함께 표시한다.
`score/10` 축은 평균 점수 산포 `<= 0.10/10`을 허용한다. 축 누락·미지원 단위·분모
불일치는 `비교 불가 — FAIL`이다. B4 latency는 검증된 허용 정책이 없어 재현성 strict
대상에서 제외한다.

`completed_at_utc` 출처:
- `NATIVE`: sidecar 기록 시각
- 기존 Python 벤치: `summary.run_config.timestamp_utc` (= `SUMMARY_POSTRUN_TIMESTAMP`)
- 기존 KRETA: `run_config.json` 은 **추론 전에** 쓰이므로 사용 금지 → `null` / `UNKNOWN`
- **디렉토리명·파일 mtime·git 시각은 완료 시각으로 쓰지 않는다.**
  실측: `20260525_145725/.../kreta/run_config.json` 의 `timestamp_utc` 는
  `2026-06-21T11:32:06Z` 로 한 달 어긋난다.

---

## 7. `--strict` 범위

`--strict` 는 `--run <session>` 없이는 사용 오류(exit 2)다.
전체 역사 트리를 검사하면 과거 거부 런 하나 때문에 CI 가 영구 실패한다.
과거 거부 런은 보고만 하고 현재 CI exit 에 넣지 않는다.
단, 현재 세션과 같은 코호트의 과거 발행 가능 런은 재현성 기준선으로 읽는다.
이 비교에서 허용 편차를 넘는 것은 현재 세션의 strict 실패로 센다.

**완료 시각이 섞인 코호트는 더 이상 자동 실패가 아니다.** 예전에는 시각 있는 런과
없는 런이 한 코호트에 있으면 대표 선정을 포기하고 `--strict` 가 무조건 exit 1 이었다.
두 런이 완벽히 일치해도 실패했으므로 아무것도 잡지 못하면서 울리는 경보였다. 지금은
§6-5 대로 시각 있는 런이 대표가 되고, **산포 검사가 그 자리를 대신하는 게이트**다.
산포가 허용을 넘으면 그때 strict 가 실패한다. 후보가 전부 무시각이면 종전대로 실패한다.

**런이 하나뿐인 코호트는 `UNVERIFIED` 로 표시하되 발행은 막지 않는다.** 비교 대상이
없다는 것은 산출물이나 채점 계약이 무효라는 뜻이 아니다. 다만 침묵은 "검사했고
괜찮다"와 구분되지 않으므로 보고서가 명시한다. 재현성 판정과 발행 가능 여부는 직교한다.

---

## 8. 알려진 오염 (회귀로 고정한다)

KRETA jsonl 21개 중 10개가 오류 응답을 정답으로 채점했다. 오염은 전부
`default` 모드에서만 나왔다:

| 모드 | 깨끗함 | 오염 |
|---|---|---|
| `direct` | 9 | 0 |
| `default` | 2 | 10 |

**단, 오류 판정은 모드가 아니라 데이터로 한다.** 오류 0건인 11개는 고정 parser로
독립 재채점하여 발행한다. parser는 다음 순서로 선택지를 찾는다.

1. `Answer:` / `정답:` / `답:` / `The correct answer is` / `option X` 등 명시 표지의
   **마지막 출현**
2. markdown을 제거한 5자 이하 짧은 응답의 첫 선택지 (`A`, `**B**`, `B.` 등)
3. 제한된 마지막 줄 선택지 형식

긴 본문의 맨몸 `\b([ABCD])\b`는 영어 관사 `a`를 오인하므로 사용하지 않는다.
`response='E'`처럼 A–D 밖의 답이나 최종 답 표지 전에 잘린 응답은 `''`로 두며,
이는 불확정 레코드가 아니라 **측정된 무답 오답**이다. parser version/hash는 protocol에
기록한다.

상류 parser 불일치는 실패가 아니라 다음 비교 정보로 sidecar에 남긴다.

```json
"upstream_comparison": {
  "upstream_accuracy": 63.60,
  "parser_disagreement_rows": 551,
  "disagreement_ours_empty": 545,
  "disagreement_different_choice": 6,
  "note": "상류 파생 필드는 채점 근거로 쓰지 않음"
}
```

`no_answer_rate`는 KRETA의 일급 발행 필드다. 무답률이 10%를 넘으면 발행을 거부하지
않고 `warnings`와 보고서 표 아래에 “응답이 지시된 형식을 벗어나 절단됨. 점수를 능력
차이로만 해석하지 말 것”이라고 표시한다. 거부하지 않는 이유는 모든 모델이 같은
direct/32-token protocol을 받았고 지시 준수와 제한 안에서 답을 완결하는 능력도 측정
대상이기 때문이다. `Qwen3.5_122B_A10B_GPTQ_Int4`는 545건의 무답으로 57.97%지만,
하네스 실패가 아니라 모델 응답이 최종 선택지 전에 잘린 유효한 측정이므로 발행한다.

| 경로 | 전체 | 오류 | 오류인데 정답처리 |
|---|---|---|---|
| `gemma_4_31b_it/20260505_130752/…/gemma_4_31b_it_default.jsonl` | 2577 | **2577** | 629 |
| `google_gemma_4_31B_it/20260505_130752/…/gemma_4_31b_it_default.jsonl` | 2577 | **2577** | 629 |
| `gemma_4_31b_it/20260505_130752/…/gemma_4_26b_a4b_it_default.jsonl` | 2577 | 548 | 156 |
| `google_gemma_4_31B_it/20260505_130752/…/gemma_4_26b_a4b_it_default.jsonl` | 2577 | 548 | 156 |
| `gemma_4_26b_a4b_it/20260503_122218/…` | 2577 | 548 | 144 |
| `gemma_4_26b_a4b_it.bad/20260503_122218/…` | 2577 | 548 | 144 |
| `gemma_4_26b_a4b_it/20260505_124246/…` | 2577 | 548 | 136 |
| `gemma_4_26b_a4b_it.bad/20260505_124246/…` | 2577 | 548 | 136 |
| `google_gemma_4_26B_A4B_it/20260505_124246/…` | 2577 | 548 | 136 |
| `google_gemma_4_26B_A4B_it/20260505_124246.bad/…` | 2577 | 548 | 136 |

`gemma_4_31b_it_default` 의 저장된 `24.41%` 는 모델 성능이 아니라
**오류 문자열 파서의 4지선다 우연 적중률**이다. 2577건 전부 404 오류다.

---


### 9-1. 외부 판정기 프로비넌스

판정기를 외부 API 로 돌리면 **점수의 재현 가능성은 우리 저장소 밖에 있다.**
`openai/gpt-4.1-mini` 같은 alias 는 문자열이 그대로여도 서빙되는 리비전이 바뀔 수
있다. 따라서 sidecar 는 다음을 기록한다:

| 필드 | 뜻 | 지문 |
|---|---|---|
| `judge_model` | 요청한 alias | **포함** — 판정기가 다르면 다른 프로토콜 |
| `judge_prompt_version` | 손으로 유지하는 버전 문자열 | **포함** |
| `judge_base_url` | 엔드포인트/제공자 | 정보용 |
| `judge_served_identity` | 응답이 보고한 `model`·`system_fingerprint`·`provider` | 정보용 |
| `judge_prompt_template_sha256` | 프롬프트 템플릿 **본문의 해시** | 정보용 |

뒤의 셋을 지문에서 빼는 이유는 §4 의 원칙 그대로다 — **프로비넌스를 더 기록한다고
프로토콜 정체성이 바뀌어선 안 된다.** 실측으로 겪은 일이다: 이 세 필드를 지문에
넣었더니 2026-08-26 판정 런이 필드가 없던 2026-08-25 런과 코호트가 갈려 재현성
비교가 성립하지 않았다. dataset provenance 에 이미 적용돼 있던 규칙과 같다.

**대신 템플릿 드리프트는 코호트 안에서 잡는다.** 같은 코호트의 두 런이 서로 다른
`judge_prompt_template_sha256` 을 기록하면 보고서가 경고한다 — `judge_prompt_version`
은 손으로 유지하므로 본문이 바뀌어도 그대로 남지만 해시는 그럴 수 없다. 지문을
가르는 대신 "같은 측정의 반복이 아니다"라고 말하는 쪽이, 비교를 살리면서 드리프트도
잡는다. 해시가 없는 옛 산출물은 `judge_prompt_template_hash` 를 `unknown` 으로 남긴다.

판정 요청에는 벤치 질문·채점기준·대상 모델의 응답이 실려 나간다(이미지는 보내지
않는다). 외부 전송이므로 실행 전 승인이 필요하다.

### 9-2. 판정 재현성의 측정 대상

판정 런은 서로 다른 두 질문에 답할 수 있다. 하나의 허용치로 섞으면 산포가
서빙 탓인지 판정기 탓인지 귀속되지 않는다. variant 로 가른다:

| variant | 뜻 | 지문에 prediction SHA |
|---|---|---|
| `api_judge_end_to_end` | 응답 생성부터 다시 하고 판정 — **재현성의 기본 정의** | 아니오(정보용) |
| `api_judge_rejudge` | 저장된 응답을 다시 판정 — 판정기 비결정성만 보는 진단용 | 예 |

판별은 선언이 아니라 산출물로 한다: 예측 파일이 판정 산출물과 **다른 세션**에 있으면
`rejudge` 다. 계획서 §3 의 `평균 0.10/10` 허용치는 `api_judge_end_to_end` 에만
적용한다. `rejudge` 는 별도로 보고하고 end-to-end 판정에 합산하지 않는다.

**같은 세션에 판정을 다시 돌리지 않는다.** 판정기는 `results.json` 을 덮어쓰므로
첫 측정을 파괴한다. 코호트 구성원을 늘리려면 새 세션이어야 한다.

## 9. KOFFVQA 판정기 컬럼 및 점수 계약

xlsx 컬럼: `['index','question','answer','category','l2-category','prediction']`

`koffvqa_api_judge.py` 의 `crit_col` 후보 `["criteria","rubric","grading"]` 가
하나도 매치하지 않아 `:130` 에서 `SystemExit` 한다. 실제 채점기준은 `answer`
컬럼에 있고, `resp_col` 후보에도 `answer` 가 있어 기준을 응답으로 오인 결합할
위험까지 있다. 진짜 응답인 `prediction` 은 후보에 없다.

v1 에서 고쳤다: fuzzy substring 감지를 제거하고 `question` / `answer`(기준) /
`prediction`(응답) 으로 고정, `--question-column` 등 명시 override 제공,
동일 컬럼 중복 결합 시 즉시 실패. 점수는 `int` 이고 `0 <= s <= 10` 만 수용
(bool 거부). 회귀 검증에서는 judge를 실제 호출하지 않는다.

---

## 10. 운영 안전장치와 한계

- reporter와 passive derive는 sidecar의 모든 `source.artifacts` 경로·SHA-256을
  원본과 다시 대조한다. 하나라도 없거나 달라지면 기존 NATIVE를 신뢰하거나 발행하지 않는다.
- publish 계층 writer는 sidecar별 POSIX advisory lock과 atomic replace를 함께 쓴다.
  passive derive는 lock 안에서 NATIVE를 재확인하므로 runner의 NATIVE 승격을 강등하지 않는다.
  publish 계층을 우회해 파일을 직접 쓰는 외부 프로세스에는 이 lock 보장이 적용되지 않는다.
- KRETA resume은 `.resume_context.json`이 현재 세션·모델·모드·endpoint뿐 아니라
  요청/유효 decoding, 제거 파라미터, 출력 상한, 최종 `skip_special_tokens`까지
  정확히 같을 때만 checkpoint를 재사용한다. checkpoint와 context는 중앙
  `data/KRETA/eval/output/` 및 해당 세션의 `results/.../kreta/`에 함께 보존하며,
  중앙 사본이 지워졌으면 동일 세션의 results 보존본에서 복구한다.
- raw preflight 실패가 일시 오류라면 **동일 환경·동일 세션**으로
  `run_kreta_resume.sh`를 실행한다. diffusion 응답 `None`이 반복되면 기존 checkpoint에
  다른 규약을 섞지 말고 **새 세션**에서
  `SERVING_FORCE_SKIP_SPECIAL_TOKENS=false run_kreta.sh`를 실행한다. serving constraint가
  달라진 checkpoint resume은 거부된다. 이 규칙 도입 전 context 없는 checkpoint도
  resume하지 않고 새 `run_kreta.sh`로 시작한다.
