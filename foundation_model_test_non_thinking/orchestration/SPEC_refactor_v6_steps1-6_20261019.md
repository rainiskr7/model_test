# SPEC: 리팩터 판 6 — 1~6단계 (2026-10-19, 판 2: Codex 반박 반영)

담당: A(Claude) 요구·수용 조건·검증, X(Codex) 반박·구현. 판 6 순서의 1~6단계만 다룬다(7~10 은 별도 명세).
저장소 N = `foundation_model_test_non_thinking/`. 모든 경로는 N 기준. 판 1 에 대한 X 반박(10-19)을 반영한 결정은 **[결정]** 으로 표시.

## 0. 공통 규칙

- CONVENTIONS §11~§14 를 따른다: 절대 import, `sys.path` 전역 추가 금지, 함수 80줄·`main` 40줄, 분해로 뽑은 순수 함수마다 `test_<모듈>_units.py`, 기존 시험은 분해 때 수정하지 않는다.
- **동결 파일 수정 금지**: `shared/harness/*`(harness_lib.sh, run_harness.sh, tests/runner_checks.py 등), `configs/tests/*`. `runner_checks.py` 는 thinking 쪽과 `cmp` 동일해야 한다.
- `orchestration/` 은 N 전용(thinking 쪽에 없음). 이식 없음.
- 한 조각 = 한 커밋(커밋은 A). 순수 분해는 출력 차이 0, 결함·계약 변경은 의도된 차이를 커밋 메시지와 §7 표에 적는다.
- 시험은 서버·`data/`·`results/` 없이 돈다(3단계 기준선 도구는 시험이 아니라 개발 도구라 실제 `results/`·`data/` 를 **읽는다** — 예외). 운영 프로세스에 닿는 시험 금지: 시스템 전역 `pgrep -f`/`ps` 로 운영 이름과 맞추는 fixture 금지. **실프로세스 시험은 fixture 가 직접 띄운 PID 와 그 자손만** 대상.
- 파이썬 시험 묶음 실행 방식 **[결정]**: `PYTHONPATH=N python3 -m <패키지>` (§13). `python3 -I` 는 쓰지 않는다(스크립트 디렉터리·cwd 를 경로에 안 올려 다중 모듈이 안 됨).
- 스크립트는 기능 하나씩 작은 파일로. 셸은 bash 3.2 호환, 파이썬은 표준 라이브러리 + 저장소 모듈만.
- X 는 구현 뒤 돌린 명령과 rc 를 보고한다. PASS 판정은 A 가 재실행해서 낸다.

## 1. guard 시험 격리

### 문제(파일로 확인됨)
- `shared/harness/tests/runner_checks.py:470-484 guard_fixture` 는 운영 `orchestration/lanes.conf` 를 복사하고, `:602-610 guard_default_lanes(C8)` 는 `LANEGUARD_LANES` 를 지운 채 guard 를 돌려 `qwen38`·`qwenfp8` 이름으로 "root=없음" 을 기대한다.
- `orchestration/lane_guard.sh:183` 식별 `pgrep -f "^([^ ]*/)?bash [^ ]*/orchestration/lanes/${pat}\.sh$"` 와 `:191` 미지원 감지(부분 문자열 `index()`) 는 시스템 전역을 본다. fixture 로 복사된 guard 가 운영 레인을 식별·STOP 할 수 있다(10-15 사고). 191행은 `qwen35fp8` 검사에 `qwen35fp8_full` 도 걸린다.
- runner_checks.py 는 동결 → guard 자체의 범위 한정 + guard 전용 시험을 `orchestration/tests/` 에 새로 만든다.

### 산출물
1. `orchestration/lane_guard.sh` 경로 정책 **[결정]**: 식별(183)과 미지원 감지(191) 둘 다 "`<자기 lanes 디렉터리>/<pat>.sh`" 로 한정한다. 자기 디렉터리는 `$HERE/lanes`(논리 경로) 와 `$(cd "$HERE/lanes" && pwd -P)`(물리 경로) 두 문자열을 모두 허용(둘이 같으면 하나). 정규식에 넣을 때 `.`·`[`·`+` 등을 escape 한다. 191행은 디렉터리 + 파일명 경계까지 검사. 운영 기동 규칙은 README 에 "심볼릭 링크 없는 정규 절대경로로 기동" 으로 적는다. 그 외 guard 동작(health·온도·STOP/CONT·상태 파일·임계값)은 바꾸지 않는다.
2. 새 시험 패키지 `orchestration/tests/lane_guard_check/`(`__main__.py` + 기능별 모듈: fixture 구성, 합성 프로세스 어댑터, 실프로세스 케이스, 판정 집계) + 진입 `orchestration/tests/test_lane_guard_isolated.sh`(`PYTHONPATH=N python3 -m orchestration.tests.lane_guard_check`). 요구:
   - 합성 `lanes.conf` 만. 운영 `lanes.conf` 를 읽거나 복사하지 않는다.
   - **두 층** **[결정]**: (가) 합성 프로세스 어댑터 — fixture `bin/` 의 가짜 `ps`/`pgrep`/`kill` 이 `processes.json` 을 읽고 신호를 기록(runner_checks.py:646 의 방식과 같되 독립 구현, 동결 파일 import 금지). 상태 논리·결함 재현용. (나) 실프로세스 — fixture 가 띄운 합성 레인(sleep 자손)과 **fixture 가 띄운 미끼**(운영 레인 이름 `qwen38.sh` 를 fixture 밖 임시 경로에 두고 같은 기동 형태로 실행). 신호 증명은 "소유 PID 별 `ps -o stat` 의 T 여부 + 종료 여부", 미끼는 stat 가 T 가 된 적 없고 살아 있음.
   - 덮을 경로: 식별·중복(2개 이상)·미지원 형태·health 2회 실패→STOP→2회 성공→CONT·온도 임계(GPU ≥84 또는 센서 ≥96 → STOP, GPU ≤72·센서 ≤85 3회 연속 → CONT)·온도 읽기 실패 시 heat 유지·수동 STOP 관찰. 임계값은 `lane_guard.sh:208,221-222` 의 현재 값을 리터럴로.
   - health/온도는 `LANEGUARD_HEALTH_CMD`/`LANEGUARD_TEMP_CMD` 주입, `LANEGUARD_ONCE=1`·`LANEGUARD_STATE_DIR`·`LANEGUARD_LOG`·`LANEGUARD_LANES`·`LANEGUARD_RUNTIME_DIR` 등 기존 변수만. 새 변수가 필요하면 이유를 적는다. 네트워크 0.
3. `orchestration/tests/test_lane_guard.sh` 래퍼는 새 시험을 가리킨다. 동결 `runner_checks.py guard` 는 `orchestration/README.md` 에 "운영 레인이 하나도 없을 때만 직접 호출; 5b 이후 새 계약과 비호환" 으로 남긴다.
4. `orchestration/README.md` 시험 절·기동 경로 규칙 갱신.

### 수용 조건
- C1.1 새 시험 전체 PASS. 실프로세스 층에서 미끼 PID 의 stat 가 T 였던 적 0, 종료 0, guard 로그에 미끼 PID 0회.
- C1.2 결함 재현(합성 어댑터 층): 운영 이름 미끼 항목이 든 `processes.json` 으로 **수정 전** `lane_guard.sh`(`git show HEAD:…` 사본)는 미끼를 root 로 식별(FAIL), **수정 후**는 root=없음(PASS). 둘 다 기록.
- C1.3 보존(실프로세스 층): 정규 절대경로로 띄운 합성 레인을 수정 후 guard 가 식별하고 온도 fixture 로 STOP → 회복 CONT 한다(PASS→PASS). 물리 경로(`/private` 접두)로 띄운 경우도 식별.
- C1.4 `git diff --stat` 에 `shared/harness/`·`configs/tests/` 0건, `runner_checks.py` N==T cmp 유지.
- C1.5 동결 `runner_checks.py guard` suite 를 A 가 운영 레인 없는 상태에서 1회 실행 → 기존 PASS 수 유지(1단계 시점 한정; 5b 이후 퇴역).

## 2. 루트 시험 한 명령

### 현재
- 설정 파일 없음. 루트에서 `.venv/bin/python -m pytest shared configs reports orchestration` 수집 895 = 트랙별 합(agent 270, functionchat 98, taubench 121, multimodal 240, nlu 85, harness 24, jsonwrite 5, publish 26, resultspath 18, configs 8, reports 0). 10-19 합동 실행: 893 passed·2 skipped·rc 0(A 기록). 1단계가 `orchestration/tests/lane_guard_check/test_*_units.py` 7개를 더해 1단계 커밋 뒤 수집은 902 다. 902 가 2단계 시점 기준선이며 3단계가 `tools/output_baseline/tests/` 를 추가한다.
- 셸 시험은 pytest 밖: `orchestration/tests/*.sh`, `tests/test_run_full_eval.sh`, 동결 `shared/harness/tests/test_harness_runner.sh`(기본 대상이 `run_harness.sh.new` 라 호출부가 대상을 명시해야 함).

### 산출물
1. N 루트 `pytest.ini` 하나: `testpaths = shared configs reports orchestration tools`, `pythonpath = .`(N 루트만), 캐시는 `.gitignore` 된 경로, `-p no:cacheprovider` 는 쓰지 않아도 됨.
2. `tests/run_pytests.sh`: 인터프리터 `.venv/bin/python`, 인자 없으면 전체, 인자는 트랙 이름(매핑 표: agent→`shared/agent`, functionchat, taubench, multimodal, nlu, harness, jsonwrite, publish, resultspath, configs→`configs`, reports→`reports`, orchestration→`orchestration`, baseline→`tools/output_baseline`), 모르는 이름 rc 2. 30줄 안.
3. `tests/run_shell_tests.sh`: 셸 시험 목록(동결 harness 시험은 대상 파일 `shared/harness/run_harness.sh` 를 명시 전달), 각 rc 수집, 하나라도 실패면 rc 1. 30줄 안. 운영 레인이 도는 중 금지 항목(guard 실프로세스 시험)은 주석으로 표시.
4. `README.md`·`CONVENTIONS.md §13` 에 명령 한 줄.

### 수용 조건
- C2.1 합동 실행과 트랙별 실행의 **수집 node ID 집합**이 같고(합집합 = 합동, 중복 0), passed/skipped/xfail/error 수가 각각 같다(`--collect-only -q` 와 `-rA` 요약 비교).
- C2.2 `conftest.py` 2개·동결 시험 무수정.
- C2.3 저장소 밖 cwd 에서 `PYTHONPATH=<N 절대경로> <N>/.venv/bin/python -m pytest -c <N>/pytest.ini --rootdir <N> <N>/shared <N>/configs <N>/reports <N>/orchestration --collect-only -q` 의 수집 수 == 루트 실행 수집 수.
- C2.4 `pytest.ini` 의 `pythonpath` 항목은 `.` 하나.

## 3. §14 출력 불변 기준선 도구

### 요구(§14)
HEAD 복사본(`git archive`)과 작업 트리를 **연속으로** 돌려 산출 해시를 비교: agent 세션 `shared.agent.scoring.score_run --check`, taubench·functionchat 세션 임시 복사본 재채점 `summary.json`, 보고서 5개 산출, multimodal `derive_source`.

### 결정 사항 **[결정]**
- 세 루트를 분리: 코드 루트(HEAD 임시 폴더 / 작업 트리 N), 입력 루트(실행 시작 때 `results/` 의 지정 세션을 임시 폴더에 **한 번 복사**한 스냅샷 — 양쪽이 같은 복사본을 읽음), 출력 루트(쪽마다 별도 임시 폴더). HEAD 쪽 실행은 cwd·`PYTHONPATH` 모두 HEAD 루트로.
- agent `--check` 는 `MODEL_TEST_BASE/data/Ko-AgentBench/bench/runner/metrics.py` 가 필요(`score_run.py:378`, `bench_path.py:14`). 양쪽에 같은 `MODEL_TEST_BASE`(실제 N) 를 주고 `metrics.py` 의 sha256 과 인터프리터 경로를 매니페스트에 기록. `--check` 는 파일을 안 쓰므로 **stdout 전문 + rc** 를 비교 대상으로 삼는다(rc 0/1/3 모두 "실행됨"; 그 밖의 rc 와 예외는 실행 실패).
- 입력 목록 `tools/output_baseline/inputs.txt`: agent·taubench·functionchat 은 각 1~2 세션(X 가 고르고 이유를 주석에), multimodal 은 §14 대로 **전 세션 목록을 고정**(생성 시점의 `derive_source` 대상 전부를 나열; 목록은 파일에 박힌 것만 쓰고 자동 확장하지 않음). 보고서 5개는 입력 스냅샷이 아니라 실제 `results/` 를 읽으므로 레인이 돌면 harness 보고서 해시가 바뀐다는 §14 주석을 매니페스트에 플래그로 기록.
- derive 는 `configs/model_identity.json` 과 형제 `koffvqa` workbook·summary 를 읽는다(`derive.py:123`, `adapters.py:683`) → 입력 매니페스트에 이 파일들의 해시 포함, 스냅샷 복사 범위에 형제 디렉터리 포함.
- rc 매핑: 0 차이 없음, 1 차이 있음, 2 실행 실패·입력 누락·전제 조건 실패.
- 전제 조건: `tests/run_pytests.sh` 로 `-k runner_requests` 실행 결과(통과/실패 수)를 매니페스트에 기록. 기준선은 저장 결과 재채점이라 **요청 변경은 못 잡는다**고 README 에 적는다.
- 쓰기 경계: 실행 직전 마커 파일을 만들고 실행 뒤 `find results data configs -newer <마커>` 가 0건, `git status --short results/` 동일. "썼다가 복원" 은 범위 밖이라고 적는다.

### 산출물
`tools/output_baseline/`(기능별, `main` 40줄 안): `inputs.py`(목록·해시 매니페스트), `snapshot.py`(`git archive` 풀기, SHA·dirty 해시, 입력 복사), `run_agent_check.py`, `rescore_scoring.py`(tau·functionchat), `render_reports.py`, `derive_multimodal.py`, `compare.py`(누락·실패는 FAIL), `baseline.py`(CLI `--inputs --out <json>`), `README.md`, `tests/test_*_units.py`(합성 매니페스트로 동일/차이/누락 판정; 실제 results 불필요).

### 수용 조건
- C3.1 1·2단계 커밋 뒤 작업 트리에서 HEAD vs 작업트리 rc 0.
- C3.2 음성: **한쪽 출력 루트의 산출 하나**를 바꾼 뒤 compare 가 rc 1 과 그 이름을 출력.
- C3.3 입력 세션 하나를 목록에서 가리키되 스냅샷에 없게 하면 rc 2.
- C3.4 쓰기 경계 검사(마커 + git status) 통과.
- C3.5 실행 시간을 매니페스트에 기록.

## 4. full 레인 결함 4건 — 각각 별도 조각

공통: `orchestration/run_lane.sh` 를 손대되 kmmlu/taubench_std4 실행 argv·env·결과 경로·로그 문구는 바꾸지 않는다(4d 의 잠금 제외) → `test_run_lane_equivalence.sh` 103 PASS 유지. `test_run_lane_full.sh`·`fixtures_full/dry_run.txt` 는 동작 변경에 맞춰 갱신하고 바뀐 기대값마다 주석으로 이유. **예외 [결정]**: 4c 는 `shared/multimodal/benches/koffvqa_api_judge.py` 와 그 시험도 수정 범위. 4d 는 두 시험의 fixture 가 `shared/harness/harness_lib.sh` 를 복사·링크하도록 **fixture 준비 코드만** 수정(기대값 무변경).

### 4a. AGENT_REQUEST_TIMEOUT / AGENT_TASK_TIMEOUT 전달
- 현재: `full_invoke` 가 unset 후 재전달 안 함 → functionchat 60초(`run_functionchat.py:379`), taubench 60초(`run_taubench.sh:65`). functionchat 은 `task_timeout > request_timeout` 을 강제(`:401-405`, 기본 task 120)라 300 만 넣으면 rc 2. `run_functionchat.sh:40-42` 는 `AGENT_REQUEST_TIMEOUT`·`AGENT_TASK_TIMEOUT` 둘 다 전달. taubench 도 같은 대소 검사(`run_taubench.py:416`, task 기본 600).
- 요구 **[결정]**: conf 키 `AGENT_TASK_TIMEOUT` 추가(기본 900), `run_lane` 검증에 `AGENT_TASK_TIMEOUT > AGENT_REQUEST_TIMEOUT` 아니면 `bad`. functionchat·taubench 단계 argv env 에 두 값을 넣는다. nlu·multimodal 은 소비 없음(확인됨) → 넣지 않음.
- C4a.1 fixture stub 기록: functionchat·taubench env 에 두 값, nlu·multimodal 에는 없음. C4a.2 단위 시험: `run_functionchat._validate_args` 와 taubench 의 해당 검증 함수에 레인 기본값(300/900)을 넣어 통과, (300/120) 은 ValueError. C4a.3 `dry_run.txt` 갱신 기록. C4a.4 등가성 103 PASS.

### 4b. `RESUME_FROM=r<N>:derive`
- 현재: 반복마다 `FULL_KOFFVQA_RAN=0`(189) → derive skip rc 0. 시험 272~275 가 고정. `README_full.md:48` 이 skip 동작 설명.
- 요구 **[결정]**: 재개 반복(`N == FULL_RESUME_REP`)에서 재개 지점이 derive 이면 `$RD/$TS/vision/multimodal/koffvqa_api_judge/{results.json,summary.json}` 둘 다 존재할 때 derive 호출; 아니면 `log "[$TS] derive 재개 불가 — judge 산출 없음"` + rc 2. 다른 반복은 기존 흐름.
- C4b.1 산출 있음 → 재개 반복에서 derive 1회·이후 반복은 정상 흐름. C4b.2 산출 없음(디렉터리만 있거나 파일 하나만) → 호출 0·rc 2·로그. C4b.3 정상 흐름 무변경. C4b.4 README_full 갱신.

### 4c. judge 키 argv 노출
- 현재: `--judge-api-key "$judge_key"`(92~94). judge 의 `make_client`(`benches/client.py:21`) 는 명시 키 → `OPENAI_API_KEY` → `"EMPTY"`. 기존 시험 `test_koffvqa_judge_identity.py:61` 은 `SimpleNamespace` 로 args 를 만들어 새 속성이 없다.
- 요구 **[결정]**: judge 에 `--judge-api-key-env <이름>` 추가. 우선순위: `--judge-api-key` > `--judge-api-key-env`(지정했는데 변수 없음·빈 값이면 메시지 + rc 2, fallback 없음) > 기존 동작. 접근은 `getattr(args, "judge_api_key_env", None)` 로 기존 시험 보존. 레인은 `--judge-api-key-env TAUBENCH_USER_API_KEY`(235행에서 이미 export). `full_command_text` 의 마스킹 분기 제거.
- C4c.1 stub argv 에 합성 키 문자열 0회, env 에 변수 존재. C4c.2 judge 단위 시험: env 지정 경로가 그 값을 `make_client` 에 넘김(가짜 make_client 로 확인), 지정 변수 빈 값 → rc 2. C4c.3 기존 `--judge-api-key` 시험 무수정 통과.

### 4d. 같은 HOST 레인 배타
- 현재: guard 는 레인 이름별 중복만. HOST 는 `주소:포트` 문자열(228행). `harness_lock` 은 fd 9, 경합 rc 3, 도구/파일 오류 rc 4, 성공 시 stdout 메시지(`harness_lib.sh:3,20-26`). `run_lane.sh` 에 fd 9 사용 없음. 자식 harness 도 fd 9 로 자기 잠금을 잡음(`run_harness.sh:162`). `ORCH` mkdir 은 full 만(256).
- 요구 **[결정]**: 단위는 **endpoint 문자열 HOST**(문서에 "같은 서버라도 포트가 다르면 다른 잠금" 명시). 파일 `$ORCH/.lane_host_<HOST 의 [^A-Za-z0-9._-] 를 _ 로>.lock`. 모든 트랙에서 `ORCH` mkdir 뒤 preflight 전에 `harness_lock … >/dev/null`(성공 stdout 억제); rc 3 → `log "$PREFIX: 같은 호스트 레인 실행 중 — 시작 안 함"` + exit 2; rc 4 → `log "$PREFIX: 잠금 오류"` + exit 4. dry-run 은 잠금 없음. 평가 자식 3곳(145, 271, 282)에 `9>&-`. 부모가 종료되면 잠금 해제(TERM 은 운영대로 프로세스 그룹에 보냄).
- C4d.1 같은 HOST 두 fixture 레인 동시 시작 → 하나만 진입, 다른 쪽 rc 2·로그. C4d.2 다른 HOST 병행. C4d.3 프로세스 그룹 TERM 뒤 잠금 해제·자식 0. C4d.4 등가성 시험: 잠금 파일 생성과 stub 자식의 fd 9 부재 외 차이 0(fixture 에 `shared/harness/harness_lib.sh` 링크 추가는 준비 코드 수정으로 기록).

## 5. 레인 구조 2단계

### 5a. 트랙 구현 추출(출력 불변)
- `run_lane.sh` = 공통부(conf 파싱·검증·활성화·키·loader·잠금·preflight·log) + `orchestration/tracks/kmmlu.sh`, `tracks/taubench_std4.sh`, `tracks/full.sh`(함수 정의 파일, `source "$HERE/tracks/<track>.sh"`). 진입 링크·conf 형식·dry-run 출력·로그 문구 그대로.
- fixture **[결정]**: 등가성·full 시험의 fixture 가 `orchestration/tracks/` 를 함께 복사·링크하도록 준비 코드만 수정(기대값 무변경, 예외 기록).
- C5a.1 **[결정]** 같은 임시 경로에 5a 전 코드와 5a 후 코드를 교대로 배치해 5개 레인 `LANE_DRY_RUN=1` 출력 byte 동일(경로 치환 없음). C5a.2 등가성 103 PASS, full 시험 PASS(4단계 뒤 기대값). C5a.3 `tracks/*.sh` 각 200줄 안(주석 포함), 함수 80줄 안; 뽑힌 함수마다 full 시험 또는 등가성 시험에 호출 경로가 있음을 X 가 표로 제시.

### 5b. 모델 인자·guard 식별·conf 형식 전환(계약 변경, 기록)
설계(10-13 결정): **파일 = 트랙, 모델 = 인자**.
- 진입 `bash orchestration/lanes/<track>.sh <model_conf>`; `<track>` 은 기존 TRACK 이름 그대로 `kmmlu`·`taubench_std4`·`full`(별칭 없음) **[결정]**. `lanes/<track>.sh -> ../run_lane.sh` 링크 3개. 옛 파일 제거 목록(명시): `lanes/qwen38.sh·.conf`, `lanes/qwenfp8.sh·.conf`, `lanes/qwen35fp8.sh·.conf`, `lanes/qwen35fp8_full.sh·.conf`, `lanes/qwen36.sh·.conf`(10개).
- `<model_conf>` 규칙 **[결정]**: `^[a-z0-9_]+$`, `.conf` 확장자·`/` 거부(rc 2). 파일 `orchestration/models/<model_conf>.conf`: `DISPLAY`(표시명), `CONFIG/HOST_ENV/HOST_DEFAULT/KEYVAR/LANE_TOKENIZER`, 트랙별 `SESSION_KMMLU`/`SESSION_TAUBENCH_STD4`/`SESSION_FULL`(선택 트랙의 세션 키 없으면 rc 2), 기존 선택 키(REPS 등). LABEL/PREFIX/STOP_LABEL/END_LABEL 은 `DISPLAY` + 트랙으로 조합.
- 런타임 이름 `<model_conf>_<track>`: guard 상태 파일·nohup 로그 이름. **HOST 잠금은 4d 대로 HOST 기준 유지**(런타임 이름을 잠금에 쓰지 않음) **[결정]**.
- `lanes.conf` → `name|track|model_conf|hostname|keyvar|model`(name = 런타임 이름). guard 식별 패턴 `<자기 lanes 디렉터리>/<track>\.sh <model_conf>$`(1단계 경로 정책), 미지원 형태(인자 없음·다른 인자 수) 경고.
- 5개 레인 → 모델 conf 4개(qwen38, qwenfp8, qwen35fp8, qwen36) + lanes.conf 5행. 세션 값 보존.
- 시험: 등가성 시험은 "harness/taubench 호출 argv·환경·결과 경로 동일" 로 좁혀 개정(로그 문구 byte 조건 버림), full 시험의 conf 생성·진입 호출(85, 103행)을 새 계약으로 개정, 1단계 guard 시험에 "같은 트랙의 두 모델을 다른 레인으로 식별" 케이스 추가. 동결 `runner_checks.py guard` 는 비호환 → README 에 "실행 금지(퇴역)" 명시.
- 문서: `orchestration/README.md`(기동·재개 절차, 예 `nohup perl -e 'setpgrp; exec @ARGV' /bin/bash <abs>/orchestration/lanes/kmmlu.sh qwen35fp8`), `README.md:340`, `CONVENTIONS.md:14`, `README_full.md`.
- C5b.1 5개 레인의 새 형태 dry-run 에서 `BASE=`·`conf=` 행을 제외한 **모든 행**(`HOST=`·`SESSION=`·`COMMAND=`·`COMMAND[if-exists]=`·`SKIP=`)이 5a 커밋의 옛 형태 dry-run 과 동일. C5b.2 개정 등가성 시험 PASS, full 시험 PASS. C5b.3 guard 시험 추가 케이스 PASS. C5b.4 실프로세스(A): 합성 `lanes/kmmlu.sh a` 와 `lanes/kmmlu.sh b` 를 guard 가 서로 다른 root 로 식별. C5b.5 제거 목록 10개가 `git ls-files` 에 0건, 새 링크 3개 존재.

## 6. R8 트랙별 서빙 스모크(레인 재개 전 통합 완료 조건)

### 제약(확인됨)
- harness 는 과목 선택 불가(`run_harness.sh:74` 45과목 고정, `--limit` 미전달), 동결 → **fallback [결정]**: 모델 목록 + 템플릿 `enable_thinking=false` 검사 + 1토큰 chat 요청(guard health 와 같은 판정). 검사 범위가 다름을 결과에 `scope=preflight` 로 표시.
- `MODEL_TEST_BASE` 는 결과 루트만이 아니라 functionchat 입력 `data`·인터프리터(`run_functionchat.sh:14`), taubench venv·벤치·commit(`run_taubench.sh:14`, `run_taubench.py:453`) 경로도 바꾼다 → 스모크 BASE 는 임시 폴더에 `data`·`.venv*`·`configs` 를 **심볼릭 링크**, `results`·`logs` 는 실제 빈 디렉터리. KRETA 는 checkpoint 가 data 아래(`run_kreta.sh:56`) → **스모크에서 제외** 하고 `KRETA_OUTPUT_ROOT` 도 임시로.
- functionchat 셸 래퍼는 `--limit` 미전달 → 스모크는 파이썬 모듈을 직접 `--limit 1` 로 호출(래퍼 우회, 문서화). taubench 는 과제 선택 옵션 없음 → X 가 가장 작은 실행 단위(도메인·split·trials=1)를 조사해 표에 제시; 없으면 preflight 수준으로 낮추고 `scope` 표시.
- 트랙별 표(X 가 구현 전에 제시, A 승인): 진입점·입력 크기·예상 요청 수 상한·성공 산출 파일과 필수 키·허용 rc.

### 산출물
`orchestration/smoke/`: `smoke_lib.sh`(공통: BASE 조립·판정 집계), `smoke_harness.sh`, `smoke_nlu.sh`, `smoke_functionchat.sh`, `smoke_taubench.sh`, `smoke_multimodal.sh`(가벼운 벤치 하나, `--limit`), 진입 `run_smoke.sh <model_conf> [track…]`. 판정 PASS/FAIL/INCONCLUSIVE 분리, 전체 rc: FAIL 있으면 1, 아니면 INCONCLUSIVE 있으면 77, 아니면 0. 가짜 서버(표준 라이브러리 HTTP, 모델 목록·chat·completions 최소 응답)로 자체 시험 `orchestration/tests/test_smoke_offline.sh`.

### 수용 조건
- C6.1 가짜 서버로 전 트랙 PASS(harness 는 scope=preflight). 모델 목록 응답을 깨뜨리면 해당 트랙 FAIL, 추론 응답만 깨뜨리면 그 트랙 FAIL·나머지 PASS.
- C6.2 A 가 337f(qwen3.5 FP8)에 실제 실행 → 트랙별 rc 기대 일치, 소요 시간 기록.
- C6.3 쓰기 경계: 마커 뒤 `find <N> -newer <마커> -not -path '*/__pycache__/*' -not -path '<임시>/*'` 0건, `git status --short results/` 동일.
- C6.4 FAIL+INCONCLUSIVE 동시 → rc 1, INCONCLUSIVE 만 → rc 77.

## 7. 진행 순서와 기록

1 → 2 → 3 → 4a → 4b → 4c → 4d → 5a → 5b → 6. 조각마다: X 구현(workspace-write, 같은 cwd) → A diff·주변 코드 리뷰 → A 가 C 재실행 → 커밋.

| 조각 | 커밋 | C 결과 | 기록(의도된 차이) |
|---|---|---|---|
| 1 | (커밋 SHA 는 git log) | C1.1 PASS(새 시험 61 PASS/0 FAIL/0 INCONCLUSIVE, 미끼 T=0·종료 0·로그 0회) · C1.2 PASS(HEAD 사본 root=800009 → 수정 후 root=없음) · C1.3 PASS(논리·물리 경로 식별, STOP→3회 CONT) · C1.4 PASS(shared/harness·configs/tests diff 0, runner_checks N==T) · C1.5 PASS(동결 suite 수정 전후 모두 25 PASS) | guard 식별 범위가 자기 lanes 디렉터리(논리·물리 경로)로 좁아짐. 다른 체크아웃·상대경로 기동은 더 이상 식별 안 함(README 에 정규 절대경로 기동 규칙). 191행 미지원 감지가 파일명 경계 검사로 바뀜(qwen35fp8 검사에 qwen35fp8_full 안 걸림). 10-19 A 실행 |
| 2 | (git log) | C2.1 PASS(합동 902 수집·900 passed·2 skipped; 트랙별 합 902, node ID 집합 동일·중복 0, passed 합 900·skipped 2) · C2.2 PASS(conftest 2개·동결 diff 0) · C2.3 PASS(/tmp 에서 902) · C2.4 PASS(pythonpath = . 하나) · 셸 묶음 run_shell_tests.sh: guard 60 PASS, 등가성 103, full 6, run_full_eval 11(+1 INCONCLUSIVE 기존), harness 러너 35(+2 INCONCLUSIVE 기존) | 새 파일 pytest.ini·tests/run_pytests.sh·tests/run_shell_tests.sh. 부수: guard 시험 C1.2 '수정 전' 검사는 HEAD 가 수정 후 코드와 같으면 건너뜀(1단계 커밋 뒤 FAIL 1 이 나서 A 가 고침). 10-19 A 실행 |
| 3 | (git log) | C3.1 PASS(HEAD 732b0e8 vs 작업트리 216 산출 MATCH, 양쪽 rc 0, 44.0초) · C3.2 PASS(작업트리 쪽 보고서 출력 1개 변조 → rc 1 DIFF reports/report_nlu_tracks.stdout, 원본 재비교 rc 0) · C3.3 PASS(없는 입력 → rc 2) · C3.4 PASS(마커 뒤 results/data/configs 0건, results status 동일, metrics.py 해시 전후 동일) · C3.5 PASS(elapsed 기록) · 추가: 보고서 코드 1줄 임시 변경 → rc 1 DIFF(감지 확인 후 복원) · 단위 22 PASS · 전제 runner_requests 50 PASS | 신규 tools/output_baseline/ 21파일. 입력: agent·taubench·functionchat 각 1세션, multimodal derive 208 전부. 보고서 5개는 실제 results 를 읽음(플래그). 10-19 A 실행 |
| 4a | (git log) | C4a.1 PASS(full 시험 F1~F7 7 PASS; functionchat·taubench env 300/900, nlu·multimodal 부재, conf 350/1000 전달 F7) · C4a.2 PASS(두 러너 _validate_args 300/900 통과·300/120 ValueError, 4 passed) · C4a.3 PASS(dry_run.txt 6줄만 변경) · C4a.4 PASS(등가성 103) · 기존 레인 qwen38·qwenfp8·qwen35fp8·qwen36 dry-run HEAD 대비 byte 동일 · 전체 pytest 926 passed·2 skipped | full 의 functionchat·taubench 에 AGENT_REQUEST_TIMEOUT=300·AGENT_TASK_TIMEOUT=900 전달(전엔 60초 기본). conf 키 AGENT_TASK_TIMEOUT 추가(full 에서만 검증, 내부 변수 FULL_AGENT_TASK_TIMEOUT). kmmlu·taubench_std4 무변경. 10-19 A 실행 |
| 4b | (git log) | C4b.1 PASS(F8: r3:derive 에 두 파일 → derive 1회·rc 0; r1:derive REPS=3 → r1 derive 후 r2·r3 정상 흐름; 이후 judge 실패 반복은 derive 생략) · C4b.2 PASS(F5·F9: 디렉터리만/한 파일만/파일 대신 디렉터리 → 호출 0·rc 2·로그 문구) · C4b.3 PASS(정상 흐름 F1~F4 무변경) · C4b.4 README_full 갱신 · 등가성 103 · 레인 5개 dry-run HEAD 대비 byte 동일 · pytest 926 | `RESUME_FROM=r<N>:derive` 가 무동작 rc 0 → 저장 산출 확인 후 derive 또는 rc 2. 시험 F5 기대값 rc 0 skip → rc 2. 10-19 A 실행 |
| 4c | (git log) | C4c.1 PASS(full 시험 9 PASS; stub argv 에 합성 키 0회, judge env 에 TAUBENCH_USER_API_KEY) · C4c.2 PASS(새 단위 7: env 지정 값이 make_client 로, 미설정·빈 값 rc 2·호출 0·fallback 없음, --judge-api-key 우선) · C4c.3 PASS(기존 judge 시험 무수정 통과, multimodal -k koffvqa_judge 26 passed) · 등가성 103 · 레인 4개 dry-run byte 동일 · pytest 933 · 기준선 216 MATCH | judge 에 --judge-api-key-env 추가(main 이 rc 를 돌려주도록 SystemExit(main())), 레인은 키 값 대신 변수 이름 전달·마스킹 분기 제거. 후속: shared/multimodal/run_koffvqa.sh:110 은 여전히 --judge-api-key 로 argv 전달(범위 밖). thinking 쪽은 이미 192줄 차이 → 이식 때 함께. 10-19 A 실행 |
| 4d | (git log) | C4d.1 PASS(세 트랙 모두 같은 HOST 동시 시작 → 하나만 진입, 다른 쪽 rc 2·로그) · C4d.2 PASS(같은 서버 다른 포트 병행) · C4d.3 PASS(프로세스 그룹 TERM 뒤 자식 0·잠금 재획득, macOS lockf) · C4d.4 PASS(등가성 103, 새 쪽 잠금 파일 1개·stub 자식 fd9=closed 외 기대값 무변경) · 잠금 시험 16 passed · full 9 · 레인 5개 dry-run byte 동일 · pytest 949 · 기준선 216 MATCH · 운영 logs/resume_orch 잠금 0 | 모든 트랙이 preflight 전 `$ORCH/.lane_host_<HOST>.lock` 을 잡음(경합 rc 2, 잠금 오류 rc 4, dry-run 제외). 평가 자식 3곳 fd 9 닫음. 잠금 파일은 종료 뒤에도 남음(내용 없음). Linux flock 실측 없음. 10-19 A 실행 |
| 5a | (git log) | C5a.1 PASS(레인 5개 LANE_DRY_RUN=1 stdout+stderr+rc 가 HEAD 와 같은 경로에서 byte 동일) · C5a.2 PASS(등가성 103, full 9, 호스트 잠금 16 포함 pytest 949) · C5a.3 PASS(run_lane 88줄, tracks/full 180·kmmlu 32·taubench_std4 22, 함수 최대 29줄) | 순수 이동: run_lane.sh 공통부 + tracks/<track>.sh 의 track_validate/track_dry_run/track_run. A 가 옛 공통 꼬리 `[ TRACK != taubench_std4 ] \|\| exit rc` 를 트랙별로 풀어 씀(kmmlu return 0, taubench exit rc — 동작 동일). fixture 준비 코드만 tracks/ 복사·링크. 10-19 A 실행 |
| 5b | (git log) | C5b.1 PASS(새 형태 kmmlu.sh qwen38·qwenfp8·qwen35fp8·qwen36, full.sh qwen35fp8 의 dry-run 이 HEAD 옛 형태와 BASE/conf 행 외 전부·rc 동일) · C5b.2 PASS(개정 등가성 89, full 9) · C5b.3 PASS(guard 격리 82 PASS/0/0: 같은 트랙 두 모델 식별·상태 분리·STOP/CONT 소유·6필드 행 검증) · C5b.4 PASS(A 실프로세스: kmmlu.sh a / b 를 서로 다른 root 로 식별) · C5b.5 PASS(옛 10개 git ls-files 0, 새 링크 3개) · 셸 묶음 5개 rc 0 · pytest 969 · 기준선 216 MATCH | 계약 변경: 진입 `lanes/<track>.sh <model_conf>`, models/<model_conf>.conf(DISPLAY·SESSION_<TRACK>·트랙 접두 키 KMMLU_/TAUBENCH_STD4_/FULL_), lanes.conf 6필드, guard 식별 `<track>.sh <model_conf>`. 로그 레이블은 `<DISPLAY> <track>` 로 바뀜(옛 LABEL/STOP_LABEL 문구 버림). 등가성 시험은 로그 문구 비교 14개 제거·HTTP 를 fixture curl 로. 동결 runner_checks guard suite 퇴역. 10-19 A 실행 |
| 6 | (git log) | C6.1 PASS(A: 가짜 HTTP 서버로 5트랙 PASS, harness·taubench scope=preflight; 모델 목록 손상·추론 손상 각 5트랙 격리 FAIL — 12 PASS) · C6.3 PASS(마커 뒤 N 안 새 파일 0, results status 동일) · C6.4 PASS(FAIL+INCONCLUSIVE=1, INCONCLUSIVE 만=77) · 닫힌 포트 → 0.15초에 FAIL rc 1, 요약에 키 문자열 0 · pytest 989 · **C6.2 보류**(337f 미서빙 — 사용자 집 네트워크에서 실행 예정) | 범위: nlu carwash 1·functionchat 데이터셋별 1·K-DTCBench 1 은 full-run, harness·taubench 는 preflight(동결 harness 과목 선택 불가, tau 러너에 과제 수 제한 없음). 임시 BASE /tmp/serving-smoke-*, HF 캐시 복사·offline. A 가 smoke/requests.py → http_preflight.py 로 이름 변경. 6단계는 C6.2 PASS 뒤 닫는다 |
