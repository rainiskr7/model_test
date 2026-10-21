# SPEC: 설정 로더 실패 원인 전달 — 트리 검토 5번 (2026-10-20)

> 상태: 채택 범위 완료(`405bc53`) — run_lane·smoke의 로더 실패 원인 전달·알려진 키 치환 구현, 성공 경로 보존.

담당: A 계획·검증·커밋, X 반박(read-only) → 구현(workspace-write). 범위 N 만. 동결·운영 쓰기 금지 규칙은 판 6 §0 그대로.

## 현재
- `orchestration/run_lane.sh:50` `loader=$(python "$BASE/configs/load_model_config.py" "$CONFIG" 2>/dev/null) || exit 1` — 실패 때 원인(`config 없음 …`/`사용 가능: …`, `serving_profile 없음` 등, `configs/load_model_config.py:35,39,55,108,120,194`)이 사라지고 rc 1 만 남는다.
- 성공 때도 로더는 stderr 에 `[config] endpoint override: …`(`load_model_config.py:153-157`)를 쓴다. run_lane 은 항상 `BASE_URL_*_OVERRIDE` 를 export 하므로 성공 경로에서 이 줄이 늘 나온다 → **그냥 `2>/dev/null` 을 지우면 dry-run·실행 stderr 가 바뀐다.**
- `orchestration/smoke/configuration.py:46-47` 는 stderr 를 받아 두고 `Unavailable("model config loader failed")` 만 낸다.

## 요구
- run_lane: 로더 stderr 를 임시로 받아 두었다가 **실패 때만** `run_lane: model config loader failed (CONFIG=<값>, rc=<rc>)` + 로더 stderr 를 그대로 stderr 로. 성공 때 stdout·stderr·rc 는 지금과 byte 동일. 실패 rc 는 지금처럼 1(호환) — X 가 rc 1 을 기대하는 호출자·시험을 확인.
  - 임시 파일을 쓴다면 `LANE_DRY_RUN=1` 의 "logs 쓰기 없음" 계약(`run_lane.sh:42` 주석)을 지킨다 — 변수 캡처(`{ … 2>&1 1>&3; } 3>&1` 류) 또는 `mktemp` 를 $TMPDIR 에(결정은 X 제안).
  - 키 값이 메시지에 들어갈 경로가 있는지 X 가 확인(로더는 키를 읽지 않는 것으로 보이나 근거 필요).
- smoke: `Unavailable` 메시지에 CONFIG 이름·rc·로더 stderr 마지막 몇 줄(길이 제한). 판정 코드(INCONCLUSIVE 77 등) 무변경.
- 시험(X 작성): 잘못된 CONFIG 로 run_lane dry-run → rc 1, stderr 에 로더 원인 포함, stdout 빈 것. 성공 dry-run 은 기존 등가성 시험이 앵커. smoke 는 단위 시험.

## 수용 조건
- C5.1(결함 재현, FAIL→PASS): 존재하지 않는 CONFIG 를 가리키는 합성 model conf 로 `LANE_DRY_RUN=1` run_lane → 수정 전 stderr 에 `config 없음` 없음(FAIL), 수정 뒤 있음·rc 1.
- C5.2(보존): 레인 5개 dry-run stdout·stderr·rc HEAD 대비 byte 동일, `orchestration/tests/test_run_lane_equivalence.sh`·`test_run_lane_full.sh` rc 0.
- C5.3: smoke 실패 메시지에 원인 포함(단위 시험), `test_smoke_offline.sh` rc 0, pytest 전체(캐시 허용·차단), 동결 0.

## 반박 반영 결정(판 2, 10-20 X 반박 → A 확인)
- **비밀 치환**: "그대로" 대신 CONFIG 헤더·로더 stderr 에서 **알려진 키 값**(환경의 OPENAI_API_KEY·TAUBENCH_USER_API_KEY 등 run_lane 이 읽은 값, 빈 값 제외)을 `***` 로 치환한 텍스트 진단. YAML 파싱 오류가 입력 줄을 담을 수 있음(load_model_config.py:42,56). 임의 비밀 판별은 보장하지 않는다고 주석.
- **rc**: 헤더에 실제 로더 rc, 레인 종료는 1(현행 유지).
- **캡처**: 임시 파일 없이 중첩 command substitution + FD 3 분리. 성공이면 진단 폐기·stdout·stderr·rc byte 동일, 실패면 부분 stdout 을 eval 하지 않음. 끝 LF 는 sentinel 로 보존, 텍스트 진단 한정.
- **smoke**: 원인은 최상위 JSON `reason`(main.py:28, rc 77·INCONCLUSIVE·BASE 보존 정책 무변경). 순서: 키 치환 → 제어문자 정리 → 마지막 20줄 → 4,096자 제한(잘림 표시). 빈 stderr 는 대체 문구.
- **범위**: run_lane.sh·smoke/configuration.py + 새 시험만. run_full_eval.sh:76 은 stderr 를 삼키지 않음(보고만), legacy 3개는 역사 기준이라 제외. 로더(configs/load_model_config.py)는 수정하지 않음.
- **시험**: `orchestration/tests/test_loader_stderr_units.py`·`test_smoke_configuration_units.py`, tmp_path 합성 checkout(유효 conf 의 CONFIG 만 없는 YAML, `.env` 없음, 로더는 실제 코드 복사본, 운영 configs 링크에 쓰기 금지). 사례: missing CONFIG / 성공하며 stderr 쓰는 로더 / stub rc 7 / 빈·LF 없음·여러 LF·긴 줄·한글·제어문자·경계 걸친 키 / dry-run 무쓰기 / smoke reason·rc 77·키 비노출.
- **C5.1**: 같은 assertion 을 수정 직전 HEAD `73c9540` 의 run_lane.sh 에 적용해 FAIL, 수정본 PASS(둘 다 기록).
- **C5.2**: 기존 acceptance 시험(test_v8_acceptance·test_registry_acceptance 의 실제 로더 5개 dry-run)은 고정 과거 커밋 대비 — 그에 더해 **73c9540 대비** 레인 5개 dry-run stdout·stderr·rc byte 동일을 A 가 따로 확인.
- **실행 제한**: pytest 전체는 허용(A 확인: orchestration 시험은 가짜 프로세스 표). 셸 guard 시험만 정지 레인 동안 미실행.

## 기록
| 조각 | 커밋 | C 결과 | 기록 |
|---|---|---|---|
| 5 | (git log) | C5.1 PASS(같은 assertion: 73c9540 run_lane.sh 에서 rc 1 FAIL — stderr `b''`, 수정본 rc 0; 실제 레인 사본에 없는 CONFIG 로 dry-run → 원인·`사용 가능:` 목록 출력, 합성 키 가림, rc 1) · C5.2 PASS(레인 5개 dry-run stdout·stderr·rc 73c9540 대비 byte 동일, stderr 0 bytes) · C5.3 PASS(pytest 1487 passed 2 skipped 캐시 허용·차단, 셸 4개+harness runner rc 0, 기준선 216 MATCH, 동결·로더·legacy 0, results 무변경) — 10-20 A 실행, diff 해시 412536fbb5ef | 정지 레인(9405)이 run_lane.sh 를 fd 255 로 읽고 있어 편집 전에 경로를 새 inode 로 교체(레인은 옛 inode 유지 확인). guard 셸 시험 미실행(변경 무관) |
