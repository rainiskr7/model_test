# SPEC: 공식 방식 재채점 + 모델 간 paired 통계 (2026-10-20, 판 2 — X 반박 반영)

담당: A 계획·검증·커밋, X 반박(read-only) → 구현(workspace-write). 범위 N 만(T 확인 필요는 보고만). 동결(`shared/harness/`·`configs/tests/`) 금지, 시험은 운영 `results/`·`data/`·`logs/` 에 쓰지 않음, 네트워크·서버 없음.
작업 종류: **새 기능(읽기 전용 분석)**. 기존 점수·sidecar·발행 판정·보고서 생성물은 바꾸지 않는다.

## 배경 (10-20 웹 확인, 원문 인용)
- K-MMBench 카드: "we adopt the CircularEval Strategy as proposed by the MMBench benchmark" — 우리 `shared/multimodal/benches/k_mmbench.py` 는 행별 정답률.
- MTVQA lmms-eval `mtvqa_process_results`: `pred=prediction.strip().lower().replace(".", "")`, `answer=str(doc["answer"]).strip().lower().replace(".", "")`, `score = 1.0 if answer in pred else 0.0` — 우리 `adapters_accuracy.py:_mtvqa_match` 는 `pred in expected`(부분 답)도 정답.
- 통계: 평균·범위·뒤집힘은 있으나 같은 문항 기준 모델 간 차이·구간이 없음(Anthropic "Adding Error Bars to Evals" 의 paired·clustered SE 권장).
- 저장 데이터로 가능: K-MMBench results.json 행에 `index`(순환 사본 = index % 1,000,000 같음, 예 세션 4329행 → 1164묶음), `predicted`·`correct`·`error`. MTVQA 행에 `row_idx`(이미지)·`qa_idx`·`gold`(list)·`response`·`error`.

## 아키텍처 (바이브코딩: 파일 하나 = 기능 하나, ≤200줄, 첫 docstring 에 입력·출력, 순수 함수와 IO 분리, 모듈마다 짝 시험)

### 묶음 1 — 공식 방식 재채점 `shared/multimodal/rescore/`
| 파일 | 기능 | 순수? |
|---|---|---|
| `__init__.py` | 표식만 | - |
| `README.md` | 기능 지도·명령·"기존 점수와 다른 지표" 설명 | - |
| `kmmbench_circular.py` | 행 목록 → 묶음(index % 1e6)별 통과(모든 사본 correct, error 사본 있으면 실패) + 요약(groups, passed, accuracy, 사본 수 분포, 불완전 묶음 수) | 순수 |
| `mtvqa_lmms.py` | lmms-eval 판정 함수(위 원문 그대로) + 행 목록 → 요약. gold list 처리 규칙은 X 가 데이터·upstream 확인 후 제안(기록) | 순수 |
| `sessions.py` | results 트리에서 대상 벤치 폴더 찾기·results.json 읽기 | IO |
| `output.py` | 요약을 JSON 문자열로(키 정렬, 방법·upstream 근거·입력 SHA 포함). `--write` 일 때만 `<bench>/_derived/official_rescore.json` 기록 | IO |
| `__main__.py` (얇은 진입점) | `python -m shared.multimodal.rescore [--base .] [--source <bench_dir>] [--write]` — 기본 dry-run(표준 출력만) | 조립만 |

- `_derived/publish.json`·derive·report·adapters 는 건드리지 않는다. `official_rescore.json` 은 별도 파일이며 발행 게이트의 입력이 아니다(X: derive 의 `_derived` 스캔·NATIVE 보호가 새 파일에 반응하는지 확인).
- 행 정답 판정은 다시 하지 않는다: K-MMBench 는 저장된 `correct`·`error` 를 쓴다(답 추출 규칙 변경은 범위 밖).

### 묶음 2 — 모델 간 paired 통계 `shared/stats/`
| 파일 | 기능 | 순수? |
|---|---|---|
| `__init__.py`, `README.md` | 표식·지도 | - |
| `item_scores.py` | (세션 목록, 벤치) → 문항키 → 반복 평균 점수, 묶음키(cluster). 벤치별 키 규칙은 표 하나(K-DTC·K-MMBench(circular 묶음)·MTVQA(row_idx)) | 순수(행 입력) |
| `paired.py` | 두 모델의 문항 점수 → 공통 문항만, 차이 평균, cluster bootstrap 95% 구간(seed 고정, 반복 수 인자), 공통 문항·묶음 수 | 순수 |
| `selection.py` | 비교 대상 세션 고르기: 기존 `shared/multimodal/publish/select.py`·sidecar `publishable` 재사용(발행 불가 세션 제외) | IO |
| `render.py` | 결과 → Markdown 표/JSON | 순수 |
| `__main__.py` | `python -m shared.stats --a <model_dir> --b <model_dir> --bench <k> [--cohort …] [--json]` 읽기 전용, 파일 쓰기 없음 | 조립만 |

- 반복(rN) 은 문항별 평균으로 합친 뒤 비교(반복 간 분산은 기존 범위 지표가 담당). 코호트 키가 다른 세션끼리는 비교 거부(X: 기존 cohort_key 재사용 방법).
- 의존성: 표준 라이브러리만(numpy 없이 random.Random(seed)). 

### 묶음 3 (이번 범위 밖, 다음 SPEC) — 보고서에 공식 방식 열·paired 구간 표시, KOFFVQA judge 변형(공식 기본 gemma-2-9b-it)·vLLM `--generation-config` 서빙 조건 표시. 생성 문서 재생성이 따라오므로 별도.

## 진행 방법
1. A: 이 SPEC → X 반박(read-only, 가정·누락·실제 데이터·upstream 대조) → A 판 2 확정.
2. X 구현 묶음 1 → A 검증·커밋 → X 구현 묶음 2 → A 검증·커밋. 묶음마다 모듈 순서: 순수 함수 + 짝 시험 → IO → 진입점 → README.
3. 시험은 X 작성: 합성 행(tmp_path), upstream 판정 사례표, 실제 추적 세션은 **읽기만**(복사해 tmp 에서).

## 수용 조건
- C1(묶음 1): 단위 — circular: 전부 맞음 통과 / 하나 틀림 실패 / error 실패 / 사본 누락 묶음 불완전 집계; MTVQA: lmms-eval 판정과 사례표 일치(우리 `_mtvqa_match` 와 다른 사례 포함). 파일마다 짝 시험.
- C2(묶음 1): git 추적 K-MMBench·MTVQA 세션 전부에 dry-run → rc 0, 불변식 circular accuracy ≤ 행 accuracy, lmms 정답 수 ≤ 기존 정답 수 아님은 보고만(둘 다 기록), 실행 전후 `git status --short` 동일(쓰기 0).
- C3(묶음 2): 단위 — 같은 seed 재현, 합성 차이 0 → 구간이 0 포함, 큰 차이 → 0 미포함, 묶음 단위 재표집(묶음 하나 = 함께 뽑힘) 검사, 공통 문항만 사용, 코호트 다름 → rc 2. CLI 를 추적 세션 두 모델에 실행 rc 0·쓰기 0.
- C4(보존, 묶음마다): pytest 전체(캐시 허용·차단), 셸 시험 4개+harness runner rc 0, 기준선 216 MATCH, publish·derive·report·benches diff 0, 동결 0, results 무변경, 새 파일 전부 ≤200줄.

## 판 2 결정 (X 반박 10-20 → A 확인; 아래가 판 1 아키텍처 표보다 우선)
A 확인: 추적 세션 예(Qwen3.5 122B 20260720) 저장 판정 기반 circular 63.4% vs 행 80.6%; HF 캐시에 K-MMBench·K-DTCBench·MTVQA 있음; X 의 "셸 시험 test_run_full_eval 누락" 주장은 틀림(A 실행 5개 = guard 제외 전부).

- **쓰기 위치**: results 트리에 아무것도 쓰지 않는다. 기본 stdout, `--out <path>` 는 results/ 밖만(안이면 rc 2). `_derived/official_rescore.json` 철회(session_sanity·_derived 전수 시험·baseline manifest 노출).
- **고정 dataset manifest**: `shared/multimodal/rescore/manifests/<bench>_<revision>.json` — 예상 index 집합, circular 묶음, 이미지 클러스터 id(이미지 SHA 앞자리), revision, 생성 근거. 생성은 `python -m shared.multimodal.rescore.manifest --build <bench>`(HF 캐시 오프라인 읽기, 1회, A 가 실행·커밋). 시험·재채점은 manifest 만 읽는다(data 불필요). K-MMBench 4선택지·3사본 묶음 59개 같은 배포 데이터 특성은 manifest 가 정답.
- **circular**: 지표명 `kmmbench_circular_stored_judgement`. 묶음 통과 = manifest 예상 사본 전부 존재 + 모두 `correct is True` + error 없음. 저장 행 집합 ≠ manifest(누락·중복·추가 index) → 해당 세션 rc 2 거부(현재 추적 31경로는 limit=null 로 완전). 답 추출은 저장 판정 그대로.
- **MTVQA**: 지표명 `mtvqa_lmms_eval`. gold 는 길이 1 list → `gold[0]`; 길이 ≠1 은 행 거부(기록·rc 2). error 행·정규화 후 빈 gold 는 실패+집계. NFKC·thinking 태그 제거 없음(lmms 원문 그대로). upstream 파일 경로·commit 을 README·출력에 기록.
- **통계 클러스터**(manifest 또는 검증된 규칙): K-DTC 문항키 = index, 클러스터 = 이미지(revision 매핑, 이미지당 2문항); K-MMBench 문항 = circular 묶음, 클러스터 = 이미지(1164→1121); MTVQA 문항 = (id, qa_idx), 클러스터 = 이미지 id. bootstrap 은 이미지 클러스터를 통째로, 두 모델에 같은 재표집, 문항 가중 평균.
- **반복·코호트**: 검증된 sidecar → `select_representatives` → `_selection.cohort_runs` 로 반복 묶기(.bad 사본 접힘). 모델 간 비교 가능 조건 = `cohort_key(...)[:3]` 같음 + 같은 지표명 + 같은 문항 집합(다르면 rc 2, "공통 문항만" 철회). 구간 설명: "관측한 반복 평균에 조건부인 문항 표집 불확실성"(반복 간 변동 미포함).
- **파일 구성(최종)**:
  - `shared/multimodal/rescore/`: `kmmbench_circular.py`(순수), `mtvqa_lmms.py`(순수), `manifest.py`(manifest 읽기·검증 + `--build` 빌더; 빌더 순수부는 행→manifest 함수), `sessions.py`(results 읽기, --out 쓰기), `__main__.py`(조립), `README.md`, `manifests/*.json`.
  - `shared/stats/`: `item_scores.py`(벤치별 문항·클러스터 점수; 위 두 채점 함수 재사용, 요약 JSON 역해석 금지), `paired.py`(순수 bootstrap), `selection.py`(sidecar·select 재사용, 코호트 검사), `__main__.py`(조립 + 표 출력 함수), `README.md`. `output.py`·`render.py` 별도 파일은 만들지 않는다.
  - 시험 이름: `shared/multimodal/tests/test_rescore_*_units.py`, `shared/stats/tests/test_stats_*_units.py`. pytest.ini·선택기 수정 불필요(동적 발견).
- **CLI 인자**: rescore `--base`, `--source <bench_dir>`(반복 가능), `--bench`, `--out`; stats `--a/--b <model_dir>`, `--bench`, `--seed`(기본 0), `--resamples`(기본 2000), 선택이 모호하면 rc 2 + 후보 목록.

### 수용 조건 판 2 (판 1 C1~C4 대체)
- C1(단위, 묶음 1): circular — 2·3·4사본 정상, 4선택지/3사본(manifest), 기본 행 누락, 중간 사본 누락, 중복 index, correct 비정상(None·문자열), error → 기대 결과. MTVQA — singleton unwrap, multi-gold 거부, 빈 답, NFKC 미적용, thinking 태그 미제거, 오류 dict 문자열 매칭 금지, lmms 원문 판정 사례표(우리 `_mtvqa_match` 와 갈리는 사례 포함).
- C2(실데이터, 묶음 1): 추적 K-MMBench·MTVQA 세션 전부 dry-run rc 0(손상 세션은 rc 2 로 명시 목록), 묶음별 `all(correct) ≤ 묶음 내 평균` 검사, 실행 전후 `results/` 파일 목록·SHA256 동일, `-B`.
- C3(단위, 묶음 2): seed 재현·입력 순서 무관, 동일 모델 비교 → 차이 0·구간 0 포함, 기대값 명확한 fixture 의 구간, 이미지 클러스터 통째 재표집·두 모델 같은 재표집·가변 크기 가중, 문항 집합 불일치·빈 교집합·반복 수 불일치·코호트 불일치 → rc 2.
- C4(실데이터, 묶음 2): 추적 세션 두 모델 비교 CLI rc 0, results 전후 SHA 동일.
- C5(보존, 묶음마다): pytest 전체(캐시 허용·차단), 셸 5개(guard 제외)+rc 0, 기준선 216 MATCH, publish·derive·report·benches·adapters diff 0, 동결 0, 새 Python 파일 ≤200줄(manifest json 제외).

## 기록
| 조각 | 커밋 | C 결과 | 기록 |
|---|---|---|---|
| 묶음 1 | (git log) | C1 PASS(rescore 단위 63 passed) · C2 PASS(추적 K-MMBench·MTVQA 63경로 전부 accepted, 묶음 불변식 위반 0, results 59,612파일 SHA 전후 동일) · C5 PASS(pytest 1644 passed 2 skipped 캐시 허용·차단, 셸 5개 rc 0, 기준선 216 MATCH, 보호 경로 diff 0, 새 .py ≤200줄) — 10-20 A 실행, 새 파일 해시 c55092662a32 | upstream commit 은 A 가 GitHub API 로 확인해 기입(lmms-eval d8fcb9c 98–102행 = lmms_match). 예: Qwen3.5 122B circular 63.40 vs 행 80.60, MTVQA lmms 39.61 vs 기존 51.97 — 우리 기존 MTVQA 판정이 더 후함 |
| 묶음 2 | (git log) | C3 PASS(stats 단위 69 passed) · C4 PASS(qwen3.8 BF16 vs FP8 r1~3, qwen3.5 35B vs FP8 r1 — K-MMBench circular·MTVQA lmms·K-DTC 6비교 rc 0, gemma 26B vs diffusiongemma 코호트 불일치 rc 2, results SHA 전후 동일) · C5 PASS(pytest 1713 passed 2 skipped 캐시 허용·차단, 셸 5개 rc 0, 기준선 216 MATCH, 보호 경로 diff 0, 새 .py ≤200줄) — 10-20 A 실행, 새 파일 해시 0a920d5ef314 | 예: qwen3.8 BF16−FP8 circular +0.14pp [−0.71, +0.99] — 6비교 모두 구간이 0 포함(차이 근거 없음) |

## 묶음 3 (판 1, 10-20 사용자 지시 "묶음 3 진행") — 보고서 표시
작업 종류: **보고서 기능 추가**. 기존 보고서 절·발행 판정·점수는 byte 그대로, 새 절을 **뒤에 덧붙인다**. 생성 문서 `MULTIMODAL_TRACK_RESULTS.md` 는 코드로 재생성(손수정 금지).

### 아키텍처
| 파일 | 기능 |
|---|---|
| `shared/multimodal/rescore/report_section.py`(순수) | 발행 가능 대표 코호트별 [모델·protocol·반복 수·기존 지표·공식 방식 지표·차이] 표 Markdown. 입력은 이미 채점된 값(파일 읽기 없음) |
| `shared/multimodal/rescore/report_inputs.py`(IO) | base 의 결과에서 K-MMBench·MTVQA 발행 가능 코호트를 고르고(기존 select·stats.selection 재사용) cohort_runs 를 rescore 로 채점해 위 함수 입력을 만든다 |
| `shared/stats/report_pairs.py`(순수+작은 IO) | `reports/paired_pairs.yaml`(비교 쌍 목록: a·b 모델 폴더, 벤치) 을 읽어 stats CLI 와 같은 계산 → 표(차이·95% 구간·문항/이미지·반복). 비교 불가 쌍은 사유 한 줄(rc 영향 없음) |
| `reports/paired_pairs.yaml` | 초기 쌍: qwen3.8 27B BF16↔FP8, qwen3.5 35B↔FP8, qwen3.6 27B↔FP8, qwen3.5 27B↔FP8 (X 가 추적 결과로 실제 가능한 쌍 확인) |
| `configs/serving_conditions.yaml` | 모델별 서빙 조건 선언: vLLM `--generation-config`(`vllm`/`auto`/미기록), 그 밖 기록할 것. 기본 전부 미기록. 모델 yaml·로더 무변경 |
| `shared/multimodal/rescore/conditions_section.py`(순수) | "평가 조건 — 공식과 다른 점" 절: KOFFVQA judge(공식 기본 `google/gemma-2-9b-it`, 우리 sidecar 의 judge), K-MMBench·MTVQA 기존 지표가 공식과 다름, tau2 subset·solo, vLLM generation-config 선언 표 |
| `reports/report_multimodal_tracks.py` | `render_markdown` 뒤에 위 세 절을 덧붙이는 조립 몇 줄만 (`--no-official` 로 끌 수 있게 — 기존 출력 byte 비교용) |

- `shared/multimodal/publish/*`(report.py 포함)·derive·adapters·benches 무변경. 새 절 문구는 "참고 지표 — 발행 게이트 판정과 별개, 공식 리더보드 점수와 동등하지 않음(저장 판정 기반)" 명시.
- 구간 설명 문구는 묶음 2 그대로.

### 수용 조건
- C6(보존): `--no-official` 출력이 HEAD 보고서 출력과 byte 동일. 새 출력은 HEAD 출력이 **접두**(앞부분 byte 동일)이고 뒤에 새 절만. 기준선 도구가 multimodal 보고서 차이를 낸다면 그 차이가 접두 규칙과 일치함을 A 가 확인(나머지 출력 MATCH).
- C7(단위): report_section·conditions_section·report_pairs 짝 시험 — 빈 입력, 거부 코호트 제외, 비교 불가 쌍 사유, 미기록 표시, 문구 고정. yaml 잘못된 형식 → 명확한 오류(rc 2).
- C8(실데이터): 재생성한 `MULTIMODAL_TRACK_RESULTS.md` 의 새 절 숫자가 rescore·stats CLI 출력과 일치(A 가 2개 이상 대조), results SHA 전후 동일.
- C9(보존): pytest 전체(캐시 허용·차단), 셸 5개 rc 0, 보호 경로 diff 0, 새 .py ≤200줄.

### 묶음 3 판 2 결정 (X 반박 10-20 반영; 판 1 표·조건보다 우선)
- **조립**: CLI 에서 `old = render_markdown(...)` 그대로 두고 `old + "\n" + appendix`. strip·splitlines 재조립 금지. 새 절 입력은 CLI 가 이미 모은 sidecar 범위(`--run` 이면 그 세션 범위, `--strict` 비교 규칙 동일)만 사용 — 전역 재수집 금지.
- **대표·반복**: `_display_cohorts` 는 표시 순서만, 대표는 `select_representatives`, 반복은 `_selection.cohort_runs`. 기존 지표와 공식 지표는 **같은 cohort_runs 집합의 평균끼리** 비교. stats.selection.load_cohort 를 그대로 쓰지 않고, 필요한 순수 함수(sidecar 바인딩 확인 등)를 공개 함수로 최소 추가하거나 report_inputs 에서 같은 검증(artifact SHA 바인딩)을 수행.
- **`--no-official`** 유지: YAML 읽기·재채점 전부 건너뛰고 기존 출력과 byte 동일.
- **비교 쌍** `reports/paired_pairs.yaml`: Qwen3.8 27B(`qwen_qwen3.8_27b`↔`qwen_qwen3.8_27B_FP8`), Qwen3.5 35B A3B(`qwen_qwen3.5_35b_a3b`↔`qwen_qwen3.5_35b_a3b_fp8`), Qwen3.6 27B(`qwen_qwen3.6_27b`↔`qwen_qwen3.6_27b_fp8`), Qwen3.5 27B(`qwen3.5_27b`↔`qwen_qwen3.5_27b_fp8`) × 3벤치(12조합; Qwen3.6 FP8 K-DTC 는 REJECTED → 사유 표시). 비교 불가는 `SelectionError`(검증 거부)만 사유 표시, 그 밖 예외는 그대로 실패(rc ≠ 0).
- **서빙 조건** `configs/serving_conditions.yaml`(`--base/configs` 에서 읽음): 기본 빈 선언 = 전부 "미기록". 선언 항목은 모델·적용 세션(또는 기간)·근거 필수 — 과거 실행 전체 조건으로 표시하지 않음. YAML IO 는 보고서 조립 쪽(rescore 패키지)에 두고 `shared/stats` 는 표준 라이브러리 유지.
- **조건 절 범위**: multimodal 만 — KOFFVQA judge 는 선택 코호트 `protocol.recorded.judge_model` 표시 + 공식 기본 `google/gemma-2-9b-it`; K-MMBench·MTVQA 기존 지표의 공식과 다른 점; vLLM generation-config 선언. tau2 subset·solo 는 제외(taubench 보고서 몫).
- **파일**: `report_section.py`(순수), `conditions_section.py`(순수), `report_inputs.py`(IO: 코호트·재채점·YAML), `shared/stats/report_pairs.py`(순수: 쌍 결과 → 표; 계산은 paired 재사용), CLI 조립. 범용 loader/render 파일 추가 없음.
- **기존 시험 변경 허용 목록**: `shared/multimodal/tests/test_report_multimodal_cli.py`(기본 출력·usage 고정 — 새 옵션·부록 반영, 기존 고정값은 `--no-official` 사례로 보존). 그 밖 기존 시험 변경 금지.

### 수용 조건 판 2 (C6~C9 대체)
- C6(보존): 기준 커밋 610e8b1 대비 — (a) working CLI `--no-official` 출력 == 610e8b1 CLI 출력 byte 동일(전체·`--run` 대표 2건), (b) 기본 출력 `startswith(old)` 이고 부록 비어 있지 않음, (c) 기준선 도구는 multimodal 보고서 1개만 DIFF·나머지 215 MATCH·양쪽 rc 0, 실행 전후 results SHA 동일.
- C7(단위): report_section·conditions_section·report_pairs·report_inputs 짝 시험 — 빈 입력, 거부 코호트, `--run` 범위, 별칭 폴더 접힘, sidecar 누락·revision 불일치, 비교 불가 사유 vs 구현 오류 전파, YAML 구조·필수 키·중복 쌍·벤치명·경로 검증(오류 시 rc 2·출력 파일 미변경), 미기록 표시, 문구 고정.
- C8(실데이터): 재생성 `MULTIMODAL_TRACK_RESULTS.md` 의 **모든** 공식 지표 값이 rescore CLI 반복 평균과 일치, 11개 가능 비교가 stats CLI 와 일치·거부 1개 사유 표시, 대표·반복 출처 일치(A 가 스크립트로 전수 대조).
- C9(보존): pytest 전체(캐시 허용·차단), 셸 5개 rc 0, 보호 경로(publish·derive·adapters·benches·harness·configs/tests) diff 0, 새 .py ≤200줄.
| 묶음 3 | (git log) | C6 PASS(610e8b1 worktree CLI 대비 전체·`--run 20260927_232851_r1`·`--run 20260720_235721`: `--no-official` byte 동일, 기본 출력 startswith(old)+부록 25386/4583/4612 bytes, 기준선 multimodal 보고서 1개만 DIFF, results 전후 SHA 동일, 재생성 문서 == CLI 출력) · C7 PASS(새·허용 시험 64 passed) · C8 PASS(공식 표 28행 전부 rescore CLI 반복 평균과 소수 4자리 일치 — gemma 2행은 표·근거 순서 대조, paired 11개 stats CLI 와 차이·구간 문자열 일치, 거부 1개는 CLI rc 2) · C9 PASS(pytest 1774 passed 2 skipped 캐시 허용·차단, 셸 5개 rc 0, 보호 경로 diff 0, .py ≤200줄) — 10-21 A 실행, diff 2069d58da2ca·새 파일 c93132e9e1f4 | A 의 첫 C6 실행은 working CLI 에 PYTHONPATH 누락(ImportError rc 1)이라 무효 → 같은 조건으로 재실행. 검증 중 KMMLU 레인이 guard CONT(10-20 23:27)로 재개돼 r3 폴더에 쓰기 — 분석 코드 쓰기 아님 |
