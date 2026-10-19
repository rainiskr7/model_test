# SPEC: 판 8 — DISPLAY 이름 충돌 수정 + 정리 (2026-10-19, 판 2: X 반박 반영)

담당: A(Claude) 계획·검증·커밋·로컬 정리, X(Codex) 반박·구현. 판 7 명세(`SPEC_refactor_v7_lane_registry_20261019.md`)의 공통 규칙을 그대로 따른다
(동결 파일 금지, bash 3.2, 기능별 작은 파일, 운영 logs/results/data 쓰기 금지, commit/push 는 A, X 의 "통과" 는 PASS 아님).
근거: 10-19 push 전 새 맥락 검토(B) 보고 + A 재현.

## 1. DISPLAY → LANE_DISPLAY (결함)

### 문제(재현됨)
- 5b 에서 모델 표시명 키를 `DISPLAY` 로 정했다. `run_lane.sh:18` 이 laneconf 출력을 `eval` 하면서 셸 변수 `DISPLAY` 에 대입한다.
  운영 Mac 셸에는 `DISPLAY=/var/run/…/org.xquartz:0` 가 **export** 돼 있어, 대입하면 export 속성이 유지된 채 값만 바뀐다 → 모든 러너 자식이 `DISPLAY="qwen3.8 BF16"` 을 받는다.
- 비교 시험이 모두 `env -i` 로 환경을 비우고 돌아서 드러나지 않았다.
- A 감사: laneconf 가 만드는 22개 이름과 run_lane 이 직접 만드는 이름(HOST·TOK·ORCH·BASE·HERE·TRACK·LABEL·PREFIX 등) 중 지금 운영 셸에 export 된 것은 `DISPLAY` 하나.

### 결정
- conf 키와 셸 변수 이름을 `LANE_DISPLAY` 로 바꾼다. `models/*.conf` 4개, `laneconf/schema.py`, `run_lane.sh` 레이블 조합, 스모크, 시험 fixture 전부, 문서(README·tracks/README·smoke/README). 지난 명세(SPEC v6·v7)는 역사 문서라 고치지 않는다.
- 옛 키 `DISPLAY=` 가 conf 에 있으면 rc 2 + `run_lane: key renamed: DISPLAY -> LANE_DISPLAY`(알 수 없는 키보다 고칠 위치를 알려 주는 메시지).
- **재발 방지 규칙**: laneconf 출력 이름과 run_lane 이 만드는 이름은 잘 알려진 운영 환경변수와 겹치면 안 된다. 금지 목록(코드 한 곳, 시험이 사용): `DISPLAY HOME PATH USER LOGNAME SHELL TERM LANG LC_ALL TMPDIR PWD OLDPWD HOST HOSTNAME EDITOR PAGER PS1 IFS SSH_AUTH_SOCK XDG_CACHE_HOME PYTHONPATH VIRTUAL_ENV`.

### 수용 조건
- **CD1 결함 재현(FAIL→PASS)**: fixture 레인을 `env -i` 가 아니라 **sentinel 이 export 된 환경**(`DISPLAY=sentinel-x11`, `HOST=sentinel-host`, `LANG=C.UTF-8` 등)으로 dry-run·실실행(stub 러너) 해서 stub 자식이 받은 env 를 기록. 수정 전(HEAD 사본): 자식 `DISPLAY` 가 표시명으로 바뀜(FAIL). 수정 후: sentinel 그대로(PASS). 둘 다 기록.
- **CD2 이름 금지 시험**: laneconf `schema` 의 출력 변수 전부 + run_lane 이 대입하는 대문자 이름(정적 추출) ∩ 금지 목록 = ∅. 금지 이름을 schema 에 임시로 넣은 사본에서 시험이 FAIL 하는 음성 검증.
- **CD3 보존**: 레인 5개 dry-run stdout·stderr·rc 가 HEAD 와 byte 동일(로그 레이블 값은 같으므로 출력도 같아야 함). 옛 키 경우 rc 2 + 위 메시지. 등가성·full·호스트 잠금·registry·config 시험, pytest(바이트코드 허용·차단), 셸 묶음.

## 2. 필수 훅 조기 검사 (10-19 Codex 반박에서 권고, 같이 반영)

### 결정(Codex 권고 그대로)
- `run_lane.sh`: `track_dry_run`·`track_run` 기본 함수를 두지 않는다. 트랙 파일 `source` **전에** `unset -f track_dry_run track_run`(환경에서 상속한 같은 이름 함수가 누락을 가리지 않게), `source` **직후**·`track_validate` 전에 훅마다 `builtin declare -F "$hook" >/dev/null || bad "track $TRACK defines no $hook"`. 선택 훅 4개의 `:` 기본값은 유지.
- 효과: 활성화·키·잠금·preflight 보다 먼저, dry-run 에서도 누락을 잡는다.

### 수용 조건
- **CH1**: `track_run` 만 빠진 트랙 → dry-run 에서 rc 2 + 메시지(지금은 rc 0 통과 — 수정 전 FAIL 재현). `track_dry_run` 만 빠진 트랙 → rc 2.
- **CH2**: 실제 경로에서 누락이면 preflight·잠금·.env 읽기 전에 끝난다 — fixture 의 curl 기록·잠금 파일·.env 접근 0 을 단언.
- **CH3**: `export -f track_run` 된 환경에서 `track_run` 이 빠진 트랙도 rc 2(상속 함수가 가리지 않음).
- **CH4**: 새 트랙 국소성 시험(CB1)의 demo 트랙에 `track_run` 추가 — 의도된 계약 변경으로 기록. 정상 트랙 3개·레인 5개 dry-run byte 동일.

## 3. 문서의 상대경로 기동 예시

- `README_full.md:3` 등 `bash orchestration/lanes/…` 상대경로 예시를 `$N` 정규 절대경로 형식으로 통일(guard 는 절대경로 기동만 식별). X 가 `grep -rn "bash orchestration/lanes/" --include=*.md` 로 전부 찾아 고친다.
- **CR1**: 위 grep 이 운영 문서에서 0건(SPEC v6·v7 역사 문서는 제외, 태그).

## 4. 스모크 임시 폴더 정리

### 코드(재발 방지)
- `run_smoke.sh` 는 전체 결과가 PASS 면 자기가 만든 임시 BASE 를 지우고, FAIL·INCONCLUSIVE 거나 `--keep` 이면 남긴다. 지우는 대상은 **자기가 이번 실행에 만든 경로 하나**(main 이 받은 `base`, `/tmp/serving-smoke-` 접두·`outside(root)` 검증 통과한 것)만. 요약 JSON 에 `base_kept: true|false`.
- 시험(test_smoke_offline·test_smoke_units·memory_transport)이 남기는 임시 폴더도 끝나면 지운다(pytest `tmp_path` 또는 명시적 정리).
- **CS1**: 가짜 서버 PASS 실행 뒤 그 base 없음, FAIL 시나리오 뒤 base 있음, `--keep` 이면 있음. **CS2**: 셸 묶음·pytest 를 한 번 돌린 뒤 `/tmp/serving-smoke-*` 개수 증가 0.

### 기존 잔여물(A 가 1회 정리, 사용자 "정리하자" 승인)
- 대상: 이 저장소 시험·도구가 만든 접두만 — `/tmp/serving-smoke-*`(≈4.4G), `/tmp/lane_guard_check.*`, `/tmp/output-baseline-*`, `/tmp/lane_equivalence_*`, `/tmp/smoke-offline-*`, `/tmp/step4*`·`/tmp/step5*`·`/tmp/v7-*`(Codex 검증 기록). 합계 ≈4.5G.
- 절차: 목록·크기를 먼저 저장 → 각 항목이 디렉터리/파일이고 소유자가 사용자이며 열려 있는 프로세스가 없는지(`lsof +D` 대신 `ps` 로 smoke·guard 프로세스 0 확인) → 변수 없이 **리터럴 접두 glob** 으로 삭제 → 개수 0 확인. 다른 접두는 건드리지 않는다.

## 5. 브랜치

- 지금 브랜치 `fix/multimodal-publish-layer` 에는 원격에 이미 올린 R6 패키징 등 커밋과 오늘의 판 6·7 커밋 12개가 함께 있다. 이름 정리는 **사용자 결정**(원격 브랜치 삭제·이름 변경은 되돌리기 어려운 외부 작업). 결정 전에는 push 하지 않는다.

## 반박 반영 결정(판 2)

**항목 1**
- 금지 목록은 **운영 셸에서 흔히 export 되는 이름**으로 좁힌다: `DISPLAY HOME PATH USER LOGNAME SHELL TERM LANG LC_ALL TMPDIR PWD OLDPWD EDITOR PAGER SSH_AUTH_SOCK XDG_CACHE_HOME VIRTUAL_ENV`. `HOST`(zsh 셸 변수, export 안 됨 — A 감사로 확인)·`HOSTNAME`·`PS1`·`IFS` 는 뺀다. `PYTHONPATH` 는 run_lane·full 이 **명령 한정 접두**(`PYTHONPATH=… cmd`)로만 쓰므로 정적 추출은 단독 대입(줄 처음 또는 `;`·`&&` 뒤의 `NAME=`, `local`/`export`/`readonly` 포함)만 세고 명령 접두 대입은 제외한다. 이 추출 규칙과 한계(eval·간접 대입은 못 잡음)를 시험 상단에 적는다.
- 내부 `HOST` 변수와 dry-run 출력 `HOST=` 행은 그대로.
- 과거 기준 revision 을 쓰는 비교 시험(`laneconf_support.py` 4e4354e, `registry_support.py` 587919d 와 그 사용처)은 **기준본에는 옛 키 `DISPLAY`, 변경본에는 `LANE_DISPLAY`** 를 주는 fixture 변환을 둔다. `required key: DISPLAY`→`LANE_DISPLAY`, 접두 금지 메시지 등 이름이 바뀐 오류 문구는 **의도된 byte 차이**로 목록화해 따로 단언한다. `test_run_lane_full.sh:331,343,350` 기대값 갱신, `test_lane_config_units.py:67-71` 은 새 키 `FULL_LANE_DISPLAY` 접두 금지 시험으로.
- **CD1 방법**: `test_run_lane_full.sh` 격리 fixture 의 `run_lane()` 최종 환경에 sentinel `DISPLAY=sentinel-x11`·`LANG=C.UTF-8` 를 직접 넣는다. 실실행은 기존 stage dump 의 `env` 파일, dry-run 은 **loader stub 에 env 기록을 추가**해 읽는다. 수정 전 기준은 `015c3c5` 사본 + 옛 conf. 먼저 rc 성공·env 파일 존재를 단언하고 그 다음 sentinel 을 단언(파싱 실패를 FAIL 재현으로 세지 않음).

**항목 2**
- `test_registry_boundaries.py:60-70` 은 이름을 바꾸고 **조기 종료**를 단언(curl·잠금 기록 0). `test_registry_hook_order.py` 에 누락 변형 추가 — events 에 validate·activate·loader·lock·http 가 모두 없음.
- CH2 의 `.env` 접근 0 은 fixture `bin/grep`(또는 동등) 이 `.env` 인자 접근을 기록하는 방식으로 관측.
- CH3 는 부모 bash 에서 실제 `export -f track_run` 후 자식 run_lane 실행 + 상속 자체가 동작하는 대조군.
- `tracks/README.md:17,64-66` 훅 설명 갱신.

**항목 4**
- 삭제 조건(전부 만족할 때만): 이번 실행에서 `assemble()` 이 반환한 경로와 동일, `parent == Path("/tmp").resolve()`(macOS 는 `/private/tmp`), 이름이 `serving-smoke-` + 비어 있지 않은 접미, 실제 디렉터리이고 최상위가 symlink 아님, `outside(root)` 통과. 삭제는 `shutil.rmtree` 로 하되 내부의 `data/configs/shared/.venv*` **링크는 링크만 지우고 대상은 순회하지 않는다**(rmtree 기본 동작이 링크를 따라가지 않음을 시험으로 고정).
- 보존: 전체 결과 FAIL·INCONCLUSIVE, timeout, `--keep`. `KeyboardInterrupt` 는 자식 프로세스 그룹을 종료·회수한 뒤 base 를 **보존**하고 rc 130. `assemble()` 내부 부분 실패는 assemble 이 자기 디렉터리를 정리한다. ConfigError 처럼 트랙 실행 전 실패는 볼 것이 없으므로 base 삭제.
- JSON: `base_kept` 는 삭제 **성공 뒤에만** false. 삭제 실패면 true + `cleanup_error`, rc 는 판정 그대로. `--out` 저장 실패는 기존 처리 유지. `smoke/README.md` 에 `--keep`·`base_kept` 의미.
- 시험 수명: `memory_transport.py` 는 보고서를 부모 `tmp_path` 로 내보낸 뒤 정리, `test_smoke_units.py:144-145` 는 단언 뒤 정리, `offline_checks.py` 의 직접 `assemble/run` 경로와 fixture root 도 정리. `test_laneconf_acceptance.py:26` 의 스모크 호출도 남기지 않게(ConfigError 삭제 규칙으로 해결되는지 확인).
- **CS2 방법**: 실행 전후 `/tmp/serving-smoke-*` **경로 집합**을 비교해 이번 실행이 만든 것이 남지 않음(개수만 보지 않음). 셸 묶음·pytest 각각.

## 진행 순서

1~4 코드: X 반박(읽기 전용) → A 명세 수정 → X 구현 → A 검증 → 커밋. 4 의 기존 잔여물 정리는 A 가 코드 커밋 뒤 실행. 5 는 사용자 답 뒤.

| 항목 | 커밋 | C 결과 | 기록 |
|---|---|---|---|
| 1 DISPLAY | (git log) | CD1 PASS(015c3c5 실행 rc 0·sentinel 검사 rc 1 → 변경본 sentinel rc 0, A 셸 묶음에서 재현) · CD2 PASS(음성 검증 포함) · CD3 PASS(A: DISPLAY export 환경에서 레인 5개 stdout·stderr·rc HEAD 동일, 옛 키 rc 2 `key renamed: DISPLAY -> LANE_DISPLAY`) | conf 키·셸 변수 LANE_DISPLAY, 금지 이름 목록 schema.FORBIDDEN_VARIABLES. 의도된 byte 차이는 tests/README_v8.md |
| 2 필수 훅 | (git log) | CH1~CH4 PASS | unset -f 후 source, 직후 declare -F 검사 — dry-run 에서도·잠금/preflight 전에 실패. demo 트랙에 track_run 추가(계약 변경) |
| 3 문서 경로 | (git log) | CR1 PASS(운영 문서 상대경로 예시 0) | |
| 4 스모크 정리 | (git log) | CS1 PASS(A 환경에서 HTTP 정리 시험 3건 포함) · CS2 PASS(A: 셸 묶음+pytest 두 번 뒤 새로 남은 serving-smoke 0) · A 직접: 다른 경로·/tmp 문자열 경로 거부, 내부 링크 대상 보존 | PASS·설정 오류는 삭제, FAIL·INCONCLUSIVE·중단(rc 130)·--keep 은 보존, base_kept·cleanup_error |
| 4 잔여물 삭제 | | | |
| 5 브랜치 | | | |
