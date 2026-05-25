# 코드 리팩토링 계획

> 향후 참고용. 우선순위·시간 추정·구체 변경 내역 기록.

## 현재 상태 요약

- 4 클래스 폴더 (llm/slm/vsm/vlm) — 자급자족 분리 (사용자 결정, DRY 강제 X)
- 클래스 별 트랙: harness · nlu · agent (텍스트), multimodal (vsm/vlm 만 비전)
- `data/` — 외부 repo (KRETA / KOFFVQA / KO-VLM-Benchmark / Ko-AgentBench / lm-evaluation-harness) 중앙 집중
- `results/` — 통합 (timestamp 폴더 단위)
- `.eval_session` — 자동 세션 (시작 timestamp 보존)
- 12 버그 fix 완료 (소스 6 + 통신 2 + 테스트 4)

## 리팩토링 가치 영역

| 영역 | 중복도 / 복잡도 | 영향 |
|---|---|---|
| Shell utilities (timestamp, base_dir, safe_model_name) | 6 sh + 3 py 중복 | 수정 시 9곳 동기 |
| BASE_DIR depth 계산 | sh 마다 자체 (`../`, `../..`) | Bug 1 의 원인 |
| Bench 모듈 (multiple-choice 패턴) | k_dtcbench / k_mmbench 중복 | 신규 bench 추가 부담 |
| Argparser | `standard_argparser` ↔ 자체 ↔ 혼합 | 일관성 없음 |
| Result schema | bench 마다 미세 다름 | 리포트 자동화 어려움 |
| 외부 repo 패치 | install.sh 의 `patch_kreta_infer_gpt` ad-hoc | 새 패치 시 패턴 정립 X |

## 7 Phase 계획

### Phase 1: Shell utilities 통합 (HIGH, ~30-45min)

**목표**: 각 클래스 폴더 내 공통 sh 로직 lib 으로 추출.

```
<class>/scripts/lib/eval_common.sh
  resolve_base_dir()        # MODEL_TEST_BASE > script depth fallback
  resolve_eval_timestamp()  # EVAL_TIMESTAMP > .eval_session > now+save
  safe_model_name()         # / - : → _
  make_results_dir()        # results/<model>/<ts>/<cat>/<track>/<bench>
  load_run_metadata()       # run_config.json 작성
```

각 `run_*.sh` 상단에 `source ../scripts/lib/eval_common.sh` → ~30줄을 ~5줄로 압축.

**효과**: sh 코드량 -40%, 신규 sh 추가 비용 ↓

**파일 영향**:
- 신규: `<class>/scripts/lib/eval_common.sh` × 4
- 수정: `run_kreta.sh`, `run_koffvqa.sh`, `run_harness.sh`, `run_all.sh` (×4 클래스)

---

### Phase 2: Python helper 표준화 (HIGH, ~15min)

**목표**: nlu / agent runner 의 자체 `get_timestamp` / `get_base_dir` 를 multimodal/common.py 패턴으로 통일.

**옵션**: 클래스 폴더 안에서 `<class>/lib/common.py` 또는 트랙별 `<track>/common.py` 자율.
사용자 메모리 ("자급자족 분리") 와 정합 → **클래스 폴더 안에서는 자유로이 import**.

**파일 영향**:
- `vsm/nlu/nlu-gpustack.py` — `get_timestamp` 단일화
- `vsm/agent/gpustack_custom/run_gpustack_benchmark_with_logging.py` — 동일
- 4 클래스 sync

---

### Phase 3: Bench class 추상화 (MEDIUM, ~1-1.5h)

**목표**: multiple-choice / free-form / streaming-eval 벤치마크 패턴 추상화.

```python
# <multimodal>/benches/_base.py
class Bench:
    BENCH_NAME = ""
    def __init__(self, args): ...
    def load_data(self): raise NotImplementedError
    def run(self): ...        # 공통 loop
    def summarize(self): ...

class MultipleChoiceBench(Bench):
    DATASET_ID = ""
    def build_prompt(self, row): ...
    def get_gold(self, row): ...
    def extract_pred(self, response): ...

class FreeFormBench(Bench):
    def is_match(self, pred, gold_list): ...
```

각 bench 는 20줄로 축소:
```python
class KDTCBench(MultipleChoiceBench):
    BENCH_NAME = "K-DTCBench"
    DATASET_ID = "NCSOFT/K-DTCBench"
    def build_prompt(self, row): return PROMPT_TEMPLATE.format(...)
```

**효과**: 신규 multiple-choice 벤치 30분 안에 추가
**리스크**: 추상화가 각 bench 의 특수성 (K-MMBench stratified 샘플링, MTVQA qa_pairs 파싱) 가릴 수 있음 — overrideable hook 으로 해결

**파일 영향**:
- 신규: `vsm/multimodal/benches/_base.py`
- 수정: `k_dtcbench.py`, `k_mmbench.py`, `mtvqa_kr.py`, `b3_structured_output.py`, `b4_latency_profile.py`, `koffvqa_run.py`

---

### Phase 4: Result schema 표준화 (MEDIUM, ~30min)

**목표**: 모든 summary.json 동일 키 구조 → 향후 리포트 자동화 기반.

```json
{
  "schema_version": 1,
  "benchmark": "K-DTCBench",
  "model": "...",
  "metrics": {
    "primary": {"name": "accuracy", "value": 0.854},
    "by_category": {...}
  },
  "totals": {"correct": 205, "total": 240},
  "run_config": {...},
  "errors_count": 0,
  "raw_results_path": "results.json"
}
```

**파일 영향**:
- common.py 에 `make_summary_template()` 추가
- 각 bench 가 그것 사용

---

### Phase 5: 외부 repo 패치 일반화 (LOW, ~30min)

**목표**: `patch_kreta_infer_gpt` 같은 ad-hoc 패치를 declarative 로.

```
<multimodal>/patches/
├── kreta.sed       # BASE_URL / WORKERS env-aware
├── koffvqa.sed     # (필요시 추가)
└── apply_patches.sh
```

`install.sh` 가 자동 적용.

**파일 영향**: install.sh + patches/ 디렉토리 신규

---

### Phase 6: Sanity tests 추가 (LOW, ~1h, codex 병렬)

**목표**: 프레임워크 자체 회귀 테스트.

```
tests/
├── test_safe_model_name.py
├── test_extract_choice.py
├── test_is_match.py
├── test_normalize_text.py
├── test_eval_session.py
└── test_run_config_meta.py
```

**효과**: 향후 변경 시 회귀 빠른 발견.

---

### Phase 7: 문서 정리 (LOW, ~30min, codex 병렬)

- 루트 `ARCHITECTURE.md`: 디자인 결정 (4 클래스, .eval_session, data/ 중앙화)
- 각 클래스 평가계획.md 검증
- 트랙별 짧은 README

---

## 시간 추정 (Claude + Codex 병렬)

| Phase | 시간 | 위험 | 효과 |
|---|---|---|---|
| 1. sh lib | 30-45min | 낮 | sh -40% |
| 2. py helper | 15min | 낮 | 일관성 |
| 3. bench class | 1-1.5h | 중 | 신규 bench 빠름 |
| 4. schema | 30min | 낮 | 리포트 자동화 |
| 5. patch | 30min | 낮 | 외부 통합 표준 |
| 6. tests | 1h (병렬) | 낮 | 회귀 안전망 |
| 7. docs | 30min (병렬) | 낮 | 가독성 |
| **합계** | **~3-4h** | | |

## 권장 실행 순서

```
Day 1 (~1h):  Phase 1 (sh) + Phase 2 (py)  ← 동시 가능
Day 1 (~30min): Phase 4 (schema)
Day 2 (~1.5h): Phase 3 (bench class)        ← 신중, 디자인 검토
Day 2 (~1h):  Phase 6 (tests) + Phase 7 (docs) ← codex 병렬
Day 3 (~30min): Phase 5 (patch)              ← 외부 trigger 시점에
```

## SKIP 항목 (의도적)

- **클래스 간 코드 공유 (cross-class DRY)**: 사용자 결정 — 자급자족 분리 유지
- **결과 폴더 구조 변경**: `results/<model>/<ts>/<cat>/<track>/` 안정적, 변경 X
- **외부 repo (KRETA/KOFFVQA 등) fork·자체 유지**: 비용 큼, 별도 검토

## 옵션 (작업 시점에 선택)

| 옵션 | 범위 | 시간 |
|---|---|---|
| A) HIGH 만 (1+2) | 즉시 효과 큼 | ~1h |
| B) HIGH + 4 (schema) | 리포트 기반 | ~1.5h |
| C) 1+2+3+4 (구조 정비) | 핵심 | ~3h |
| D) 전체 (1~7) | 완전 | ~3-4h |
