# SPEC: 바이브코딩 입구 정리 — 트리 검토 1·2·4·7·8·9 (2026-10-20)

> 상태: 채택 작업 완료(`73c9540`) — 입구 문서·검색·보호 설정·시험 선택기 반영; 완료 뒤 상태 줄을 추가했으므로 아래 "미리 달지 않는다" 결정과 충돌하지 않는다.

담당: A(Claude) 계획·수용 조건·검증·커밋, X(Codex) 반박(read-only) → 구현(workspace-write).
근거: 10-20 트리 검토(A·X 독립 분석). 범위는 N(`foundation_model_test_non_thinking/`)만. thinking 사본·jev_test 는 건드리지 않는다.
**측정 코드·요청·채점·결과는 하나도 바꾸지 않는다.** 바뀌는 것은 문서, 검색·lint 설정, 시험 선택기(`tests/run_pytests.sh`)뿐이다.

공통 금지: 동결 `shared/harness/*`·`configs/tests/*` 수정, 운영 logs/results/data 쓰기, commit/push(A 담당), 운영 레인 프로세스에 신호.
**지금 qwen3.5 KMMLU 레인(pid 9405)이 정지 상태로 살아 있다 → `orchestration/tests/test_lane_guard.sh` 와 `tests/run_shell_tests.sh` 전체는 실행 금지.** 셸 시험은 guard 시험을 뺀 나머지만 개별 실행.

## 1. `AGENTS.md`(신규, N 루트) + `CLAUDE.md`(신규, `@AGENTS.md` 한 줄) + 낡은 문서 상태 표시
- AGENTS.md 는 **100줄 이하**, 규칙 본문을 복제하지 않고 링크한다. 담을 것:
  - 범위: 이 디렉터리(N)만. thinking 사본·`../jev_test` 는 별개.
  - 정식 수정 위치: 공통 코드는 `shared/`(CONVENTIONS 해당 절 링크), `llm/`·`slm/`·`vlm/`·`vsm/` 아래는 링크라 원본은 `shared/`. `orchestration/lanes/*` 링크는 호출 이름으로 트랙을 고르는 계약이라 실파일로 바꾸지 않는다.
  - 동결·금지: `shared/harness/*`·`configs/tests/*` 동결, 시험에서 운영 `results/`·`data/`·`logs/` 쓰기 금지, 외부 배치 코드(`shared/agent/gpustack_custom/`, `shared/serving/` 상대 import 등 CONVENTIONS §11 예외).
  - 확인 명령: `bash tests/run_pytests.sh [track]`(`--list`), `bash tests/run_shell_tests.sh`(운영 레인 중 guard 시험 주의), `python -B -m tools.output_baseline.baseline --out <tmp>`, 스모크 `orchestration/smoke/run_smoke.sh`(실서버). 무엇이 단위/격리 프로세스/실서버/실결과 기준선인지 한 줄씩.
  - 진입점: README 의 진입점 표(4번) 링크.
  - 문서 지도: 현행(CONVENTIONS, README, orchestration/README·README_full, MULTIMODAL_PUBLISH_CONTRACT, 생성 문서 2개는 손수정 금지) / 역사 기록(REFACTORING_PLAN, 완료된 SPEC).
  - 검색: `results/` 는 `.ignore` 로 기본 검색 제외 — 결과 조사 땐 `rg --no-ignore-dot … results/`.
  - (9번) N/T 관계: N 전용 디렉터리(예: `orchestration/`, `tools/output_baseline/` — X 가 실제 대조로 목록 확정), 의도된 차이는 `../foundation_model_test_thinking/THINKING.md`, 같아야 하는 파일(예: `shared/harness/tests/runner_checks.py` cmp — X 가 근거 있는 것만), 버그 수정 때 T 에 같은 경로가 있으면 "T 확인 필요" 를 보고에 적고 이식은 하지 않는다(사용자 결정: N 끝난 뒤).
- 낡은 문서: 제목 바로 아래 **상태 한 줄**만 추가(본문 무수정). `REFACTORING_PLAN.md` → "역사 기록 — 현행 규칙은 CONVENTIONS.md, '클래스 간 공유 금지' 결정은 `shared/` 통합으로 대체". `orchestration/SPEC_*.md` 각각 → 완료/진행/취소 + 대표 커밋(X 가 git log 로 확인). `MULTIMODAL_REPRO_PLAN.md` 는 현행 절차인지 X 가 판단해 근거와 함께 제안.

## 2. `.ignore`(신규, N 루트)
- `results/` 한 줄(+주석). `data/`·`logs/` 는 이미 `.gitignore` 라 rg 가 건너뛴다 — 중복 추가하지 않는다(X 가 반론 있으면 근거).
- git 추적·`.gitignore` 무변경.

## 4. README 진입점 표 + 틀린 사용법 정정
- README 맨 앞(1절 앞 또는 3절 첫머리 — X 제안)에 용도별 정식 진입점 표: config 기반 전체 실행(`run_full_eval.sh <config>`) / 반복 실행(`run_repeated_eval.sh`) / 운영 레인(`orchestration/lanes/<track>.sh <model_conf>`) / 실서버 스모크 / 단일 트랙. 열: 용도·명령·포함 단계·재개·실패 정책·자세한 문서 링크. 사실은 각 스크립트 usage·README_full 에서만 가져온다.
- README:175 "스크립트 상단 변수 수정 후 `bash run_full_eval.sh`" → 실제 usage(`run_full_eval.sh <model_config_name>`)로. 3.4 절 나머지 문장도 실제 코드와 대조.
- **알려진 결함은 고치지 않고 표에 적는다**: run_full_eval 경로는 functionchat·taubench timeout 을 넘기지 않아 기본 60초(트리 검토 3번, 별도 작업).
- 실행기 통합·이름 변경 금지.

## 7. `.pre-commit-config.yaml` 보호 경로 제외
- 최상위 `exclude:` 정규식. **pre-commit 의 파일 경로는 git 루트(`model_test/`) 기준**이므로 `^foundation_model_test_non_thinking/(shared/harness/|configs/tests/|results/|data/|logs/)` 형태(X 가 확인). 결과 JSON 에 end-of-file-fixer·trailing-whitespace 가 닿지 않게 results 도 포함.
- 이 설정 파일은 git 루트에 없어 `pre-commit install` 만으로는 안 쓰인다 → 머리 주석의 설치·실행법을 실제로 동작하는 형태(`pre-commit run -c foundation_model_test_non_thinking/.pre-commit-config.yaml …`, git 루트에서)로 정정. hook 설치는 하지 않는다.

## 8. `tests/run_pytests.sh` 트랙 목록
- `shared/<이름>` 트랙은 고정 목록 대신 **실제 디렉터리**에서 판정(이름은 `^[a-z0-9_]+$`, `shared/<이름>` 이 디렉터리이고 시험 파일이 있어야 함). `configs|reports|orchestration|baseline` 별칭은 그대로.
- `--list`: 받는 트랙 이름을 한 줄씩(정렬) 출력, rc 0.
- 기존 트랙 이름 전부 같은 디렉터리로 해석, 모르는 이름은 지금과 같은 문구·rc 2.
- `tests/run_shell_tests.sh:6` "운영 레인 실행 중 금지" 주석이 8dd8b82(guard 격리) 뒤에도 맞는지 대조해 맞게 고친다(시험 동작 무변경).
- 시험: X 가 run_pytests.sh 선택기 시험을 추가(위치 X 제안, 운영 경로 쓰기 없음, pytest 를 실제로 다 돌리지 않는 방식이면 좋음).

## 수용 조건
- **C1 문서 링크 실재**: AGENTS.md·README 진입점 표·상태 줄에 적힌 저장소 경로(백틱)가 전부 존재(스크립트로 추출·`test -e`, 예시 자리표시 `<…>` 제외). AGENTS.md ≤100줄, CLAUDE.md 는 `@AGENTS.md`.
- **C2 검색 제외**: N 에서 `rg --files | grep -c '^results/'` = 0, `rg --files --no-ignore-dot results | wc -l` > 0, `git status --short -- results` 변화 없음.
- **C3 pre-commit 제외**: `git ls-files` 의 `shared/harness/*`·`configs/tests/*`·`results/*` 전 파일(git 루트 기준 경로)이 exclude 정규식에 `re.search` 일치, 그 밖 N 의 추적 파일은 불일치(python+yaml 로 계산). yaml 파싱 OK.
- **C4 시험 선택기**: `jsonread`·`reproidentity` 트랙 rc 0, 기존 트랙 이름 전부 전과 같은 디렉터리(HEAD 판과 비교), 모르는 이름 rc 2·같은 stderr, `--list` rc 0. 새 선택기 시험 PASS.
- **C5 무변경**: `git diff --stat` 에 문서·`.ignore`·`.pre-commit-config.yaml`·`CLAUDE.md`·`tests/` 외 0, 동결 경로 0. pytest 전체(캐시 허용·차단) PASS, guard 시험 뺀 셸 시험 개별 rc 0, 출력 기준선 216 MATCH.

## 반박 반영 결정(판 2, 10-20 X 반박 → A 확인)
- **실행 제한 정정**: pytest 의 orchestration 시험(`test_registry_acceptance.py:26-38` 등)은 가짜 프로세스 표·임시 fixture 로 guard 를 돌리고 운영 lanes.conf·PID 를 쓰지 않는다(A 확인) → **pytest 전체 실행 허용**. 셸 `test_lane_guard.sh` 도 격리됐지만 정지 레인이 있는 동안은 A 판단으로 실행하지 않고 "미실행(변경 무관)" 으로 기록.
- **§1**: X 상태표 채택(아래). 클래스 디렉터리는 "공통 트랙 디렉터리가 링크, 클래스별 추천·평가계획은 실파일"로 정확히. 핵심 금지는 AGENTS.md 에 직접 쓰고, CONVENTIONS 는 "수정 전 해당 절을 읽는다" 로 링크. 생성 문서 `MULTIMODAL_TRACK_RESULTS.md`·`TAUBENCH_TRACK_RESULTS.md` 이름 명시, `shared/results_dir.sh` heredoc 예외도 링크. N/T 는 "동일성 계약(runner_checks.py 하나)" 과 "현재 관측(N 전용 디렉터리 목록)" 을 분리해 적는다. 이 SPEC 자체에는 상태 줄을 미리 달지 않는다(기록 표로).
  - SPEC_full_lane_20261015 → 역사 기록 — 초기 full 구현 완료(2944f67); 현행 계약은 orchestration/README_full.md 와 v6·v7·v8 후속 변경.
  - SPEC_refactor_v6_steps1-6 → 완료 — 1~6단계 구현(8dd8b82…4e4354e)·C6.2 실서버 검증(94707d2); 후속 계약 변경은 v7·v8.
  - SPEC_refactor_v6_step7_dedup → 완료(659a7e9) — 7e heredoc 추출은 동결 계약 때문에 취소.
  - SPEC_refactor_v6_step8_import_effects → 완료(0718b8b) — FunctionChat identity 실행별 객체화, 외부 배치 adapter 는 §12 예외.
  - SPEC_refactor_v6_step9_split → 부분 구현 후 종료 — 9-0·9-1a/b/c·9-2a/b 완료(17aec7b…d8c95c0), 9-3~9-6·10단계는 하지 않기로 결정.
  - SPEC_refactor_v7_lane_registry → 완료(587919d·015c3c5) — 필수 훅 조기 검사는 v8(e9dbd1c)에서 보강.
  - SPEC_fix_v8_display_cleanup → 코드 항목 1~4 완료(e9dbd1c) — 임시 잔여물·브랜치 정리 행은 완료 근거 미기록.
  - REFACTORING_PLAN.md → 역사 기록 — 클래스별 자급자족·공유 금지 전제는 shared 통합(6d62b93)으로 대체, 현행 규칙은 CONVENTIONS.md.
  - MULTIMODAL_REPRO_PLAN.md → 혼합 문서 — 재현성 정책은 현행, A/B 구현 완료(8c615f5 외), 현재 CLI(`--strict` 는 `--run` 필수)·채점 구현은 reports/report_multimodal_tracks.py·shared/multimodal/publish/ 가 기준.
- **§2**: `.ignore` 는 `/results/`. AGENTS.md 에는 "`--no-ignore-dot` 은 .ignore 만 해제, .gitignore 제외(llm_debug·artifacts 등)는 남는다" 로 정확히.
- **§4**: 표는 README 소개문 뒤·1절 앞. X 의 7행 표(config 일괄 / 반복 / KMMLU 레인 / tau standard 레인 / full 레인 / 실서버 스모크 / 단일 트랙) — 사실은 각 근거 행에서 다시 확인. 3.4 절: usage, "한 트랙 실패해도 계속" 에 rc 3·≥129 즉시 중단 예외, cleanup 문장은 조건부로. timeout 문구: "run_full_eval 은 timeout 기본값을 따로 주입하지 않아 `AGENT_*` 가 없으면 functionchat·taubench request 기본 60초".
- **§7**: 최상위 `files: ^foundation_model_test_non_thinking/` + `exclude: ^foundation_model_test_non_thinking/(shared/harness/|configs/tests/|results/|data/|logs/)`. 머리 주석은 git 루트에서 `pre-commit install -c …`·`pre-commit run -c … --all-files`.
- **§8**: 첫 인자 `--list` 를 `-*` 보다 먼저(추가 인자 있으면 rc 2), 별칭 우선, 동적 트랙은 `^[a-z0-9_]+$` + `shared/<name>` 디렉터리 + 하위 `test_*.py`/`*_test.py` 존재 — 목록과 선택이 같은 판정. `LC_ALL=C` 정렬. 기존 오류 문구·argv·rc 보존. 시험 `tests/test_run_pytests.py`(tmp_path 사본 + 가짜 `.venv/bin/python`) + `pytest.ini` testpaths 에 `tests` 추가. run_shell_tests.sh:6 주석은 X 안 3줄로.
- **C1**: 이번에 추가·변경한 안내의 저장소 경로만 검사(`<…>`·`file:line`·glob·URL 구분, 역사 본문 제외).
- **C3**: git 루트 `git ls-files --full-name` 전체로 files+exclude 를 함께 판정(T·상위 비선택, N 일반 선택, 보호 경로 제외) + data/logs 합성 경로.
- **C4**: 선택 해석(가짜 interpreter)과 실제 pytest 성공을 별도로: 13개 기존 이름 HEAD 판과 target·argv 동일 + `jsonread`·`reproidentity` 실제 pytest rc 0.
- **C5**: 시작 시점 대비 tracked·untracked·staged 모두 확인. 허용 변경: 문서(*.md), `.ignore`, `.pre-commit-config.yaml`, `CLAUDE.md`, `AGENTS.md`, `pytest.ini`, `tests/`.

## 기록
| 조각 | 커밋 | C 결과 | 기록 |
|---|---|---|---|
| 1·2·4·7·8·9 | (git log) | C1 PASS(추가·변경 안내 링크 68개 실재·행 범위, AGENTS 45줄, CLAUDE.md `@AGENTS.md`) · C2 PASS(기본 rg results/data/logs 0, `--no-ignore-dot` results 3033) · C3 PASS(git 루트 추적 3760개 판정 불일치 0, 선택 423, 합성 data/logs/results/harness·T·jev 비선택) · C4 PASS(기존 13개 이름·무인자·`-q`·모르는 이름 HEAD 대비 stdout·stderr·rc 차이 0 — 가짜 interpreter, `--list` 15개 rc 0·추가 인자 rc 2, jsonread 7·reproidentity 10 실제 PASS) · C5 PASS(pytest 1454 passed 2 skipped 캐시 허용·차단, 셸 4개+harness runner rc 0, 출력 기준선 216 MATCH, 동결 0·runner_checks cmp 동일, results 무변경) — 10-20 A 실행, diff 해시 a1ab9cd7e01c | guard 셸 시험은 정지 레인 때문에 미실행(변경 무관). 동작 차이 1건: 목록에 있던 shared 이름의 디렉터리가 사라지면 전엔 `Test track directory unavailable`, 이제 `Unknown test track`(둘 다 rc 2) |
