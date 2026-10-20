# SPEC: 판 7 — 설정 파서 통일(급함) + 트랙 등록 정리(5a·5b 마저) (2026-10-19, 판 2: X 반박 반영)

> 상태: 완료(`587919d`·`015c3c5`) — 공통 설정 파서·파일 기반 트랙 등록 구현; 필수 훅 조기 검사는 [v8](SPEC_fix_v8_display_cleanup_20261019.md)(`e9dbd1c`)에서 보강([run_lane.sh:26](run_lane.sh#L26)).

담당: A(Claude) 계획·수용 조건·검증·커밋, X(Codex) 반박·구현. 근거는 10-19 바이브코딩 평가(준비도 2/5)와 A 의 파일 검증.
N = `foundation_model_test_non_thinking/`. 판 6 명세(`SPEC_refactor_v6_steps1-6_20261019.md`)의 공통 규칙(§0)을 그대로 따른다:
동결 파일(`shared/harness/*`, `configs/tests/*`) 수정 금지, CONVENTIONS §11~§14, bash 3.2, 함수 80줄·main 40줄, 기능별 작은 파일,
운영 `logs/resume_orch`·`results/`·`data/` 쓰기 금지, git commit/push 금지, X 의 "통과" 보고는 PASS 가 아니며 A 가 재실행해 닫는다.

순서: **A(급함) → B**. 각 묶음은 X 반박(읽기 전용) → A 명세 수정 → X 구현 → A 리뷰·재실행 → 커밋. B 뒤 push 전에 새 맥락 검토(B 역할, 같은 계열 새 세션)를 한 번 돌린다.

## 묶음 A — 설정 파서 하나로 + 스모크 결함 (실서버 스모크 C6.2 전에 끝낸다)

### 문제(재현됨)
- 같은 `models/<m>.conf` 를 레인(`run_lane.sh:22-60` 셸 파서)과 스모크(`smoke/configuration.py:25-38` `literals`, `setdefault`)가 **따로** 읽는다.
  같은 키가 두 번 있으면 레인은 마지막 값, 스모크는 첫 값 → 재현: `HOST_DEFAULT=first` / `second` 에서 레인 `second`, 스모크 `first`.
  스모크를 통과한 서버와 레인이 붙는 서버가 달라질 수 있다.
- 스모크의 트랙 접두 처리도 부분적이다(`configuration.py:71` 은 `KMMLU_LANE_TOKENIZER` 만 본다).
- `orchestration/smoke/*.py` 상대 import 16개(CONVENTIONS §11 "항상 절대 경로" 위반, 예외 목록에 없음).
- `orchestration/tests/test_smoke_offline.sh` 가 `tests/run_shell_tests.sh` 목록에 없다.

### 결정
1. **파서는 파이썬 모듈 하나**: `orchestration/laneconf/`(패키지) — 순수 함수 `parse(text) -> 항목 목록`, `resolve(entries, track) -> 해석 결과(dict)`, 키 표(공통 키·접두 금지 키·선택 키와 기본값)를 **한 곳**에.
   - CLI `python -m orchestration.laneconf <model_conf> <track>` 는 `shlex.quote` 로 감싼 `NAME=value` 줄만 출력(`configs/load_model_config.py` 의 export 출력과 같은 방식). 오류는 stderr 한 줄 + rc 2.
   - `run_lane.sh` 의 셸 파서(`config_setting`·`read_config`, 22~60행 부근)를 지우고 이 CLI 출력을 받아 쓴다. 인터프리터는 `"$BASE/.venv/bin/python"` 직접 경로(활성화 전에 호출되므로), `PYTHONPATH="$BASE"`.
   - 스모크 `configuration.py` 는 `literals` 를 지우고 같은 모듈의 `resolve` 를 쓴다.
2. **중복 키는 오류**(rc 2, "duplicate key: <KEY>" — 같은 범위·같은 키). 지금 README 의 "같은 키·같은 범위에서는 마지막 값이 우선" 을 바꾸는 계약 변경이다. 현재 `models/*.conf` 4개에 중복 없음(X 가 확인). 범위 간 우선순위(기본값 → 공통 → 선택 트랙 접두)는 그대로.
3. 따옴표 처리·키 이름 규칙·접두 금지 키(DISPLAY·CONFIG·HOST_ENV·HOST_DEFAULT·KEYVAR·SESSION_*)·알 수 없는 키 rc 2 는 현재 `run_lane.sh` 동작을 그대로 옮긴다. 셸 평가 없음.
4. 스모크가 쓰는 값(CONFIG·HOST_ENV/HOST_DEFAULT·KEYVAR·LANE_TOKENIZER)은 **kmmlu 트랙으로 해석한 결과**를 쓴다(토크나이저는 harness 스모크가 kmmlu 레인과 같은 템플릿을 검사해야 하므로). 접속 식별 키는 접두 금지라 트랙과 무관하게 같다.
5. 스모크 상대 import → 절대 import(`from orchestration.smoke.x import …`). `tests/run_shell_tests.sh` 에 `orchestration/tests/test_smoke_offline.sh` 추가.

### 반박 반영 결정(판 2, 10-19 X 반박 → A 결정)
- **호출 위치·환경**: `run_lane.sh` 의 현 파서 자리(67행 `source tracks` 이전)에서 `PYTHONPATH="$BASE" PYTHONDONTWRITEBYTECODE=1 "$BASE/.venv/bin/python" -B -m orchestration.laneconf --tracks-dir "$HERE/tracks" <model_conf> <track>` 를 **그 명령에만** 환경을 붙여 호출하고 출력을 `eval`. 전역 export 금지(full 시험의 PYTHONPATH 부재 검사·등가성 env 비교 보존).
- **출력 형식**: `export` 없는 셸 변수 대입 `NAME=<shlex.quote(값)>` 만. 변수 이름은 지금 셸 파서가 만드는 이름 그대로(AGENT_TASK_TIMEOUT·KRETA_WORKERS·KRETA_RESUME·RESUME_FROM → `FULL_*`, 그 외 동명) + `SESSION`(선택 트랙의 세션 키 값). LABEL 류 조합은 run_lane 에 남긴다.
- **laneconf 가 맡는 검증**(지금 run_lane 이 하던 것 그대로): 키 이름·접두 금지 키·알 수 없는 키·두 번 읽기 우선순위(기본값 → 공통 → 선택 접두)·필수 키(CONFIG HOST_ENV HOST_DEFAULT KEYVAR DISPLAY)·세션 키 필수·환경변수 이름 검사(run_lane.sh:66 규칙). **HOST 형식 검사는 스모크에만 남긴다**(별도 계약). 새로 추가: 중복 키 오류.
- **오류 형식**: 설정 오류는 stderr 한 줄 `run_lane: <메시지>` + rc 2, traceback 없음. 기존 오류 경우의 메시지는 지금 셸과 byte 동일. 새 메시지 `duplicate key: <KEY>`(범위 접두 포함한 원래 키 이름).
- **API**: `parse(text)`(줄 → 항목, 중복 검사 포함), `resolve(entries, track, tracks, require_session=True)`, 예외 `ConfigError`. 스모크는 `resolve(…, track="kmmlu", require_session=False)` 로 CONFIG·HOST_ENV/HOST_DEFAULT·KEYVAR·LANE_TOKENIZER 를 얻고, 스모크 `Context` 에 config·keyvar 를 추가.
- **스모크 rc**: `ConfigError` 는 rc 2 + stderr `smoke: <메시지>` 한 줄(레인과 메시지 본문 동일), 그 밖의 전제 부족만 rc 77.
- **fixture 준비 코드 수정 허용(기대값 무변경)**: `test_run_lane_full.sh`(`.venv/bin/python` 에 실제 인터프리터 링크, loader·judge 스텁은 유지), `test_run_lane_equivalence.sh`(fixture 에 `orchestration/laneconf` 복사), `host_lock_fixture.py`·`host_lock_worker.py`(실제 인터프리터 + laneconf 복사), `smoke/offline_checks.py` fixture(DISPLAY·SESSION_KMMLU 추가)와 그 전파 경로(`memory_transport.py`, `test_smoke_units.py` 의 복사 root 에 laneconf).
- **중복을 덮어쓰기 수단으로 쓰던 기존 시험**은 "추가" 대신 "기존 줄 교체" 로 바꾸고 원래 검증 목적(우선순위·비평가·재개 출력·timeout 전달)을 유지: `test_lane_config_units.py:51-63,73-78`, full F4(:196-204)·F7(:323-330). **F6(:307-319)** 은 교체 방식 + 경우별 오류 메시지를 확인(rc 2 만 보면 중복 오류로 통과해 원래 검증이 사라짐). 중복 자체는 새 시험으로: 공통 중복, 접두 중복, 같은 값 반복도 오류, 비선택 트랙 접두 중복도 오류, 메시지 키 표기.
- **CA2 관측 방법**: 프로덕션 dry-run 출력은 늘리지 않는다. (가) `LANE_DRY_RUN=1` 의 `HOST=` 행 == laneconf CLI 의 HOST 해석, (나) fixture 의 loader 스텁이 받은 CONFIG 인자 기록 == laneconf CONFIG, (다) 스모크 `configuration()` 결과의 host·config·keyvar·tokenizer == laneconf(kmmlu) — 실제 `models/*.conf` 4개 전부.
- **CA3 비교 방식**: HEAD 사본과 변경본을 같은 절대경로에 교대 배치, stdout·stderr 를 각각 bytes 로, rc 를 따로 비교.
- 함수 내부 상대 import(`memory_transport.py:70,82`)도 절대 import 로.

### 수용 조건(묶음 A)
- **CA1 결함 재현(FAIL→PASS)**: 합성 conf(중복 `HOST_DEFAULT`)로 수정 전(HEAD 사본) 레인 dry-run 과 스모크 해석이 **다른 값**(FAIL), 수정 후 둘 다 rc 2 + 같은 메시지 "duplicate key: HOST_DEFAULT"(PASS). 둘 다 기록.
- **CA2 일치 시험(신규)**: 실제 `models/*.conf` 각각 × 그 모델에 세션 키가 있는 트랙 각각에 대해, 스모크가 해석한 HOST·KEYVAR·CONFIG 가 `LANE_DRY_RUN=1 lanes/<track>.sh <m>` 의 `HOST=` 와 loader 입력과 같다. 합성 conf 로도 접두·따옴표·기본값 경우를 표로.
- **CA3 보존**: 레인 5개(`kmmlu.sh qwen38|qwenfp8|qwen35fp8|qwen36`, `full.sh qwen35fp8`) dry-run stdout+stderr+rc 가 HEAD 와 같은 경로에서 byte 동일. 등가성 89·full 9·호스트 잠금 16·`test_lane_config_units.py`(기존 기대값 무수정, 단 "마지막 값 우선" 을 고정한 케이스가 있으면 계약 변경으로 기록하고 갱신)·전체 pytest.
- **CA4 스모크**: `test_smoke_offline.sh` PASS(A 실행), `grep -rnE "^\s*from \.|^\s*import \." orchestration/smoke` 0건(태그: 동적 import 는 못 잡음), `bash tests/run_shell_tests.sh` 전체 rc 0(목록에 스모크 포함).
- **CA5 문서**: `orchestration/README.md` 설정 절(중복 키 오류로), `smoke/README.md`(같은 파서 사용, any-cwd 예제를 절대경로로).

## 묶음 B — 트랙 등록을 `tracks/<track>.sh` 하나로 (5a·5b 마저)

### 문제(파일로 확인됨)
- 트랙 이름이 공통부에 박혀 있다: `run_lane.sh` 허용 목록(9행)·세션 변수 초기화·세션 키 허용·접두 해석·세션 선택(15·25·44·57행 부근 — 묶음 A 뒤에는 laneconf 로 옮겨짐), `lane_guard.sh:197` 허용 목록.
- 공통부에 트랙별 분기 4곳: `run_lane.sh:72-73`(트랙별 export), `:82`(tau 사용자 키는 taubench_std4·full 만), `:105`(kmmlu 만 템플릿 검사).
- 트랙 파일은 run_lane 이 만든 전역 11~17개에 기대는데 그 목록이 어디에도 없다.
- `lanes.conf` 의 keyvar·model 이 `models/*.conf`·모델 yaml 과 중복 관리된다(어긋나도 아무도 모른다).

### 결정
1. **트랙 = `tracks/<track>.sh` 파일의 존재**. 트랙 이름 규칙 `^[a-z0-9_]+$`. `run_lane.sh`·`lane_guard.sh`·laneconf 는 고정 목록 대신 `"$HERE/tracks/$track.sh"` 존재로 판정(laneconf 는 `orchestration/tracks/*.sh` 목록으로 접두·세션 키를 만든다: 접두 `<TRACK 대문자>_`, 세션 키 `SESSION_<TRACK 대문자>`).
   - 함정: 새 트랙 이름이 기존 공통 키 앞부분과 겹치면(예: 트랙 `taubench` → 접두 `TAUBENCH_` 가 `TAUBENCH_USER_MODEL` 을 잡음) 남은 이름이 알 수 없는 키가 되어 rc 2 로 **시끄럽게 실패**해야 한다. 이 경우를 시험으로 고정.
2. **트랙별 훅**: 각 트랙 파일이 아래 함수를 정의(없으면 공통부의 빈 기본값): `track_export`(활성화 뒤 export, 72-73행 대체), `track_secrets`(키 읽기, 82행의 tau 사용자 키 대체), `track_pre_http`(잠금 뒤·HTTP preflight 전, 105행 템플릿 검사 대체), 기존 `track_validate`·`track_dry_run`·`track_run`. 공통부에 `$TRACK" =` 비교 0.
3. **입력 계약 문서화 + 시험**: `run_lane.sh` 상단(또는 `orchestration/tracks/README.md`)에 트랙 파일이 읽어도 되는 전역 목록을 한 번 적는다. 각 트랙 파일 머리 주석에 그 트랙이 쓰는 입력을 적는다. 시험: 각 `tracks/*.sh` 가 참조하는 대문자 전역(자기 파일에서 만드는 것·bash 내장 제외) ⊆ 문서 목록.
4. **lanes.conf 일치 시험**: 각 행의 keyvar == `models/<m>.conf` 의 KEYVAR, model == 그 모델 CONFIG 를 loader 로 푼 MODEL, name == `<m>_<track>`, track 파일 존재. (형식은 바꾸지 않는다 — guard 가 쓰는 hostname 은 models conf 에 없음.)
5. 범위 밖(이번에 안 함): `full_stage_index` 의 전역 반환 개선, 스모크 트랙별 모듈 재구성·합성 데이터 시험, output_baseline `--ref`, 등가성 heredoc 분리. 판 7 뒤 별도.

### 반박 반영 결정(판 2)
- **훅 위치·시점**: `track_export` = 지금 72-73행 자리(활성화·`MODEL_TEST_BASE` export 직후, loader 이전 — loader 가 LM_EVAL_MODE 를 다시 쓸 수 있으니 순서 유지). 쓸 수 있는 것: laneconf 결과 변수·TRACK·BASE·HERE·bad. `track_secrets` = 지금 82행 자리(dry-run 이 아닐 때만), 쓸 수 있는 것: + read_key·KEYVAR. `track_pre_http` = 잠금 뒤·curl 전(105행 자리), 모든 변수·log 사용 가능. 공통부는 `track_pre_http || exit "$?"`. 빈 기본 훅은 `:` 로 성공. kmmlu 의 템플릿 검사는 log 뒤 `return 1`.
- **등록부 위치**: 언제나 **실행 중인 체크아웃의** `$HERE/tracks` — run_lane·guard 는 HERE, laneconf 는 `--tracks-dir` 인자(파이썬 `__file__` 기준 탐색 금지), 스모크는 자기 root 의 `orchestration/tracks`.
- **등록 규칙**: 이름 `^[a-z0-9_]+$`, `-f`(일반 파일 또는 일반 파일을 가리키는 링크), 디렉터리 무시. 접두 판정은 `SESSION_*` 를 먼저 공통 키로 처리한 뒤 트랙 접두를 **최장 일치**로(`a` 와 `a_b` 공존 시 `A_B_` 우선).
- **함정 시험**: 합성 conf 에 `TAUBENCH_USER_MODEL=x` 를 명시하고 `tracks/taubench.sh` 를 임시로 둔 경우 rc 2(알 수 없는 키 메시지) — 조용히 다른 키로 해석되지 않음.
- **guard fixture**: `lane_guard_check/fixture.py` 가 합성 `tracks/kmmlu.sh`(및 시험에 쓰는 트랙)를 만든다. guard 는 존재만 확인하고 source 하지 않는다. `.venv`·laneconf 는 guard 에 불필요.
- **CB1 방법**(X 반박 8단계 채택): 임시 실행 트리 → 공통 파일(run_lane.sh·lane_guard.sh·laneconf/*.py) 목록·SHA-256 기록 → `tracks/demo.sh`(특징적 dry-run 한 줄)·`lanes/demo.sh` 링크·합성 conf `SESSION_DEMO` 추가 → 저장소 밖 cwd 에서 dry-run rc 0·demo 줄·SESSION 확인(공통 BASE·conf·HOST 줄도 있음) → .env·logs·잠금·preflight 미생성 → guard 에 합성 6필드 demo 행 + JSON 어댑터 프로세스 `/bin/bash <fx>/orchestration/lanes/demo.sh <m>` → 한 주기 뒤 정확한 PID 로그와 `<m>_demo.state` instance → 음성: `tracks/demo.sh` 제거 시 runner rc 2·guard rc 4·신호 0 → 공통 파일 해시·목록 전후 동일.
- **입력 계약(CB4)**: 변수뿐 아니라 함수(bad·log·read_key)와 단계별 사용 가능 시점을 `orchestration/tracks/README.md` 표로. 검사기: 각 트랙 파일의 대문자 전역 참조 ⊆ (계약 목록 ∪ 같은 트랙 파일에서 대입하는 이름). 한계(읽기 전 초기화 누락은 못 잡음)를 시험 상단에 적고, 미등록 전역을 넣은 임시 사본에서 시험이 FAIL 하는 음성 검증을 둔다.
- **lanes.conf 일치(CB5)**: model 비교는 CONFIG 문자열이 아니라 `configs/load_model_config.py` 의 `load()` 로 푼 MODEL(qwenfp8 은 CONFIG 소문자·MODEL 대문자 FP8).
- **문서**: orchestration/README.md(트랙 목록·세션 키·접두·중복·활성화 전 파서·fixture 의존), README_full.md(재개 예시가 기존 FULL_KRETA_RESUME 를 교체함·등가성 fixture 의 laneconf), smoke/README.md(malformed conf rc 2), 새 `orchestration/tracks/README.md`(트랙 추가 절차: 파일·링크·세션 키·lanes.conf 행, 입력 계약 표, 훅 실패 처리).

### 수용 조건(묶음 B)
- **CB1 새 트랙 국소성(신규 시험)**: 임시 복사본에서 `tracks/demo.sh`(dry-run 1줄 출력) + `lanes/demo.sh` 링크 + 합성 model conf 의 `SESSION_DEMO` 만 추가하고 `run_lane.sh`·`lane_guard.sh`·laneconf 를 **건드리지 않은 채** `LANE_DRY_RUN=1 lanes/demo.sh <m>` rc 0, guard 가 `demo` 행(`<m>_demo|demo|<m>|…`)을 받아 식별.
- **CB2 하드코딩 0**: `grep -nE "kmmlu|taubench_std4|\bfull\b" orchestration/run_lane.sh orchestration/lane_guard.sh orchestration/laneconf/*.py` 가 주석·문서 문자열 외 0건(태그: 문자열 조립으로 만든 이름은 못 잡음). `grep -nE '\$TRACK" (=|!=)' orchestration/run_lane.sh` 0건.
- **CB3 보존**: CA3 와 같음(레인 5개 dry-run byte 동일 + 등가성·full·잠금·pytest) + guard 격리 시험 82 PASS(A 실프로세스 포함) + 함정 시험(트랙 `taubench` 가정 시 rc 2).
- **CB4 입력 계약 시험** PASS, **CB5 lanes.conf 일치 시험** PASS(현재 5행).

## 진행 기록

| 묶음 | 커밋 | C 결과 | 기록(의도된 차이) |
|---|---|---|---|
| A | (git log) | CA1 PASS(HEAD: 레인 second·스모크 first → 수정 후 둘 다 rc 2, `run_lane:`/`smoke: duplicate key: HOST_DEFAULT`) · CA2 PASS(실제 모델 4개·5쌍 HOST·loader CONFIG·스모크 Context 일치) · CA3 PASS(레인 5개 같은 경로 교대 stdout·stderr·rc byte 동일 + A 의 오류 설정 12종×2트랙 24경우 byte 동일 — CR·마지막 줄 개행 없음·값 안 `=`·앞 공백·빈 값 포함) · CA4 PASS(스모크·laneconf 상대 import 0, 셸 묶음 6개 rc 0 — guard 82·등가성 89·full 9·스모크 오프라인 포함) · CA5 문서 · pytest 1081(바이트코드 허용·차단 양쪽) · 기준선 216 MATCH | 계약 변경: 같은 범위 중복 키 → rc 2. 레인·스모크가 orchestration/laneconf 하나를 씀. A 수정 1건: 수용 시험 fixture 가 소스의 __pycache__ 까지 복사해 기본 pytest 에서 27 실패 → 복사 시 제외 |
| B | (git log) | CB1 PASS(demo 트랙: tracks/demo.sh·lanes 링크·SESSION_DEMO 만으로 dry-run·guard PID 식별, 공통 파일 SHA 전후 동일, 제거 시 runner rc 2·guard rc 4) · CB2 PASS(run_lane·lane_guard·laneconf 에 트랙 이름 0, `$TRACK =` 비교 0) · CB3 PASS(A: 레인 5개 + 오류 경로 11개 HEAD 587919d 대비 stdout·stderr·rc byte 동일 16/16, 셸 묶음 6개 rc 0 — guard 82·등가성 89·full 9·스모크, pytest 1125 바이트코드 허용·차단, 기준선 216, taubench 접두 함정 rc 2) · CB4 PASS(입력 계약, 음성 검증 포함) · CB5 PASS(lanes.conf 5행) | 트랙 = tracks/<t>.sh 존재. 훅 track_export·track_secrets·track_pre_http 를 원래 위치에. A 수정: 필수 훅 track_dry_run·track_run 의 기본값을 `:` → `bad`(rc 2)로 — 빠뜨린 트랙이 조용히 rc 0 으로 끝나던 구멍. 회귀 시험 2개(되돌리면 FAIL 확인), tracks/README 반영 |
| 새 맥락 검토 | | | |
