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
    "mode": "direct"
  },
  "inferred": {"max_tokens": {"value": 32, "basis": "run_kreta.sh: direct -> KRETA_MAX_TOKENS=32"}},
  "unknown": ["temperature", "seed"],
  "complete": false
}
```

판정:
- `unknown` 이 **비교 결과를 바꿀 수 있는 항목**(dataset item digest, mode, split,
  category filter, limit)을 포함하면 → `INSUFFICIENT_PROVENANCE`.
- `unknown` 이 그 외 항목(temperature/seed 등 decoding 세부)만 포함하고
  나머지 검증을 통과하면 → `LEGACY_REVALIDATED` + 경고.

근거: KRETA 깨끗한 런 11개(direct 9 + default 2)는 오류 0건이고 mode와
산출물의 문항 집합을 복원할 수 있다.
이걸 통째로 버리면 2577샘플짜리 최대 벤치가 보고서에서 사라져 도구가 무시된다.
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

`git_commit` / `huggingface_id` / `revision` 등 dataset provenance는 정보용으로
sidecar에 계속 기록하지만 protocol fingerprint 계산에서는 제외한다. 같은 코호트에서
repo commit이 갈리면 보고서 표 아래에 문항 집합은 동일하다는 각주를 남긴다.

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
| KRETA | JSONL **1개 = 1 source 단위**, 2577 unique id와 item digest, 오류 0, unresolved 0, mode 기록됨, raw 재집계 == results.json |
| KOFFVQA 생성 | 항상 `UNSCORED` — 채점이 없다 |
| KOFFVQA 판정 | 275건 전부 채점, judge error 0, 모든 score 가 **정수 0–10**, prediction SHA 일치 → `provisional=true` |
| B3 | `total>0`, manifest 전 항목 시도, 오류 0. **기존 7개는 total=0 이므로 전부 REJECTED** |
| B4 | 전 condition·rep 완주, 실패 0. latency 축별 발행. **점수가 아니므로 strict/conditional 없음** |

---

## 6. 대표 런 선정

선정 키: `(benchmark_id, variant, protocol.fingerprint, model)`

1. sidecar 없는 디렉토리 → 점수 없이 "게이트 기록 없음" 으로만 보고.
2. `publishable=true` 인 sidecar 만 후보.
3. **원자적 선택** — overall / category / System1·2 축은 한 런에서 통째로 가져온다.
   카테고리별로 다른 런을 고르면 모델마다 유리한 카테고리가 조합된 모자이크가 된다.
4. 후보가 여럿이면 신뢰 가능한 `completed_at_utc` 최신 하나.
5. **점수·분모·런 이름 문자열을 tie-break 로 쓰지 않는다.**
   (`report_agent_tracks.py:125` 가 `(den, run_name)` 튜플 비교라 동일 분모에서
   문자열 정렬로 떨어지는 버그가 남아 있다. 여기서는 반복하지 않는다.)
6. 결정 불가(timestamp null 이 둘 이상, 동시각 동률) → 자동 선정하지 않고
   후보 목록만 점수 없이 표시. `--strict` 에서 exit 1.

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

---

## 8. 알려진 오염 (회귀로 고정한다)

KRETA jsonl 21개 중 10개가 오류 응답을 정답으로 채점했다. 오염은 전부
`default` 모드에서만 나왔다:

| 모드 | 깨끗함 | 오염 |
|---|---|---|
| `direct` | 9 | 0 |
| `default` | 2 | 10 |

**단, 판정은 모드가 아니라 데이터로 한다.** `default` 라서 거부하는 것이 아니라
오류 레코드가 있어서 거부한다 — 깨끗한 `default` 런 2개
(`qwen_qwen3.5_35b_a3b_fp8_default`, `qwen_qwen3.6_35b_a3b_fp8_default`)는 통과해야 한다.

깨끗한 런 11개는 전부 `measured=2577/2577` 이고, 재집계값이 저장된
`overall_accuracy` 와 소수점 4자리까지 일치함을 실측 확인했다 (독립 재계산).

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

## 9. KOFFVQA 판정기는 현재 실행 불가

xlsx 컬럼: `['index','question','answer','category','l2-category','prediction']`

`koffvqa_api_judge.py` 의 `crit_col` 후보 `["criteria","rubric","grading"]` 가
하나도 매치하지 않아 `:130` 에서 `SystemExit` 한다. 실제 채점기준은 `answer`
컬럼에 있고, `resp_col` 후보에도 `answer` 가 있어 기준을 응답으로 오인 결합할
위험까지 있다. 진짜 응답인 `prediction` 은 후보에 없다.

v1 에서 고친다: fuzzy substring 감지를 제거하고 `question` / `answer`(기준) /
`prediction`(응답) 으로 고정, `--question-column` 등 명시 override 제공,
동일 컬럼 중복 결합 시 즉시 실패. 점수는 `int` 이고 `0 <= s <= 10` 만 수용
(bool 거부). **v1 에서 judge 를 실제 호출하지는 않는다.**
