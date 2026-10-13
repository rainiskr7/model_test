# 레인 재개

이 디렉터리는 실행 코드와 conf를 보관한다. 런타임 상태와 로그는 기존
`logs/resume_orch/`에 이어 쓴다. 명령은 N 저장소 루트에서 실행한다.
아래 N은 실제 절대 경로로 설정한다.

```bash
N=/Users/rainis/Desktop/workspace/source/model_test/foundation_model_test_non_thinking
cd "$N"
# 1. 운영자가 서빙 상태를 확인한다.
bash check_servers.sh
# 2. qwen38 또는 qwenfp8을 각각 독립 프로세스 그룹으로 시작한다.
name=qwen38
nohup perl -e 'setpgrp; exec @ARGV' /bin/bash "$N/orchestration/lanes/$name.sh" >> "logs/resume_orch/$name.nohup.log" 2>&1 &
# 3. 기존 watchdog/temp_guard가 종료되었음을 확인하고 guard를 시작한다.
nohup perl -e 'setpgrp; exec @ARGV' /bin/bash "$N/orchestration/lane_guard.sh" >> logs/resume_orch/lane_guard.nohup.log 2>&1 &
```

4. 손으로 멈출 때는 **lane_guard PID에 먼저 TERM**을 보낸 뒤, 해당 레인의
   프로세스 그룹에 TERM을 보낸다. PID/PGID는 운영자가 확인한다.
   `kill -TERM <guard-pid>` 다음 `kill -TERM -- -<lane-pgid>` 순서다.
5. 상태는 `logs/resume_orch/.lane_guard/<name>.state`, 로그는
   `logs/resume_orch/orchestrator.log`, 잠금은 `.lane_guard.lock`이다.
   `LANEGUARD_RUNTIME_DIR`로 런타임 디렉터리를 바꿀 수 있다.
6. 새 레인은 `lanes/<name>.conf`, `ln -s ../run_lane.sh lanes/<name>.sh`,
   `lanes.conf` 한 줄을 추가한다. 레인은 인자 없이 `/bin/bash <절대경로>.sh`로
   실행한다. guard는 `/orchestration/lanes/<pat>.sh`와 이름이 정확히 일치하는
   bash 프로세스만 root로 인정한다.
7. 실행 전 해석 결과를 확인한다.

```bash
LANE_DRY_RUN=1 bash orchestration/lanes/qwen38.sh
LANE_DRY_RUN=1 bash orchestration/lanes/qwenfp8.sh
```

Dry-run은 cd, venv 활성화, config loader까지만 진행하며 `.env`를 읽지 않는다.
preflight, 로그 쓰기, harness/taubench 실행은 하지 않는다. `LANE_TOKENIZER`는
harness 인자에만 쓰며 loader가 export한 `TOKENIZER`는 유지한다.

conf는 빈 줄/`#` 주석과 `key=value`를 지원한다. 값 양끝의 한 쌍 따옴표는
제거하며 shell 확장이나 eval은 하지 않는다. 모르는 키/인자는 rc 2다.
필수 키는 CONFIG, HOST_ENV, HOST_DEFAULT, KEYVAR, TRACK, SESSION, LABEL,
PREFIX, END_LABEL이다. TRACK은 kmmlu 또는 taubench_std4다.
kmmlu는 LANE_TOKENIZER, STOP_LABEL도 필수이며
REPS=3, REQUIRE_NOTHINK=1, LM_EVAL_MODE=chat, NUM_CONCURRENT=8이 기본이다.
NUM_CONCURRENT는 1..8만 허용한다. std4 기본은
TAUBENCH_USER_MODEL=openrouter/openai/gpt-4.1-mini, TAUBENCH_TRIALS=4,
TAUBENCH_MAX_CONCURRENCY=4, AGENT_REQUEST_TIMEOUT=300이며 호출 시
TAUBENCH_MODE=standard를 설정한다. LABEL은 원본 시작 문구를 사용한다.
PREFIX는 오류 로그 접두, STOP_LABEL은 `harness 실패 — <STOP_LABEL> 레인 중단`,
END_LABEL은 `=== <END_LABEL> 레인 종료 ===`에 그대로 사용한다.
로그 문구를 LABEL이나 레인 이름에서 파생하지 않는다.

## 검증

```bash
bash orchestration/tests/test_lane_guard.sh
python3 -I ../foundation_model_test_thinking/shared/harness/tests/runner_checks.py guard "$PWD/orchestration/lane_guard.sh"
bash orchestration/tests/test_run_lane_equivalence.sh
cmp shared/harness/tests/runner_checks.py ../foundation_model_test_thinking/shared/harness/tests/runner_checks.py
```

시험은 임시 fixture에서만 가짜 레인/키/HTTP 및 harness 스텁을 사용한다.
legacy 파일은 원본을 `cp -p`로 보관한 비교 기준이며 수정하지 않는다.
실제 `.env`나 운영 로그를 시험 입력/출력으로 사용하지 않는다.
runner_checks.py의 모든 suite는 `.codex_work/harness_stop_guard/` 아래에
fixture를 만든다. 샌드박스가 fixture 생성이나 ps/TCP bind를 거부하면
해당 검증은 INCONCLUSIVE로 보고한다. 등가성 시험은 INCONCLUSIVE만 남으면
rc 77이다. runner_checks.py는 실패가 없을 때 PASS 없이 INCONCLUSIVE만 있으면
rc 77, PASS가 있으면 기존 계약대로 rc 0이다. guard의 MODEL PASS는
모의 프로세스 상태 검사이며 실제 프로세스 C7 PASS를 대신하지 않는다.

D8 아카이브 이동과 C4 manifest/상태 해시 확인은 A 담당이다. C2 PASS 뒤
이동하며 이 구현은 `logs/`를 변경하지 않는다. T 파일 패치가 샌드박스로
거부된 환경에서는 N의 runner_checks.py를 T의 같은 위치에 복사하고 cmp 후
T 시험을 실행해야 한다.
