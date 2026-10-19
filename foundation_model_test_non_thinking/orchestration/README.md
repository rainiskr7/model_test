# 레인 재개

이 디렉터리는 실행 코드와 conf를 보관한다. 런타임 상태와 로그는 기존
`logs/resume_orch/`에 이어 쓴다. 명령은 N 저장소 루트에서 실행한다.
아래 N은 디렉터리 심볼릭 링크가 없는 정규 절대경로로 설정한다.
guard와 레인을 같은 정규 경로로 기동한다(`/tmp`는 macOS에서 `/private/tmp`).
레인 진입 파일 자체의 `../run_lane.sh` 링크는 유지하며 resolve하지 않는다.

```bash
N=/Users/rainis/Desktop/workspace/source/model_test/foundation_model_test_non_thinking
N=$(cd "$N" && pwd -P)
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
   실행한다. guard는 자기 `$HERE/lanes`의 논리 경로와 `pwd -P` 물리 경로
   두 문자열만 인정한다(같으면 하나). 경로와 `<pat>.sh`가 정확히 일치하고
   추가 인자가 없는 bash 프로세스만 root다. 다른 체크아웃은 식별·미지원
   경고에서 제외하며, 임의의 다른 심볼릭 링크 별칭까지 탐색하지 않는다.
   `nohup perl ... exec` 이후에는 bash가 같은 PID를 이어받으므로 이 형식과 호환된다.
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
# 같은 guard 시험의 직접 진입점:
bash orchestration/tests/test_lane_guard_isolated.sh
bash orchestration/tests/test_run_lane_equivalence.sh
cmp shared/harness/tests/runner_checks.py ../foundation_model_test_thinking/shared/harness/tests/runner_checks.py
```

guard 시험은 표준 라이브러리 패키지 `orchestration.tests.lane_guard_check`를
`PYTHONPATH=N python3 -m`으로 실행한다. 운영 `lanes.conf`를 읽거나 복사하지
않으며, 합성 conf와 임시 guard/helper 사본만 사용한다. 동결 시험을 import하지 않는다.
기존 래퍼의 선택 인자 및 `LANEGUARD_TARGET`은 검사할 guard 파일 선택용으로 유지한다.

합성 층은 fixture `bin/`의 `ps`/`pgrep`/`kill`이 `processes.json`만 읽는다.
실프로세스 층도 같은 어댑터를 거치며, fixture가 띄운 bash·sleep·미끼의 등록 PID만
`/bin/ps -p <PID>`로 조회한다. 전역 프로세스 목록은 조회하지 않는다. 시작 시각을
재확인한 등록 PID만 신호를 받으며, Bash 내장 kill은 fixture의 `BASH_ENV`에서만
비활성화해 PATH 어댑터를 우회하지 못하게 한다. `LG_CHECK_*`는 시험 어댑터 전용
변수이며 guard의 운영 주입 변수는 추가하지 않는다. health/온도는 기존 주입 명령을
사용하고 네트워크 명령은 실패하는 스텁으로 차단한다.

미끼는 fixture 밖 별도 임시 경로의 `qwen38.sh`를 운영과 같은 nohup/Perl 형식으로
기동한다. 생존·T 상태를 반복 관측하고 guard 로그와 신호 기록에 미끼 PID가 없는지
검사한다. 관측 간 순간 상태의 부재는 샘플링만으로 증명하지 않으므로 모든 신호
시도 기록도 함께 검사한다. 정리는 등록한 PID에만 수행한다.

C1.2는 `git show HEAD:./orchestration/lane_guard.sh` 사본을 사용한다. Git 루트가
N의 상위 디렉터리이므로 `HEAD:orchestration/lane_guard.sh` 대신 cwd 상대 Git
표기를 사용한다. 수정 전의 미끼 식별은 예상된 격리 FAIL, 수정 후는 PASS로 기록한다.
이 재현 검사는 수정 전 guard가 HEAD인 1단계 커밋 전에 실행한다. 커밋 후에는
HEAD도 수정 후 코드가 되므로 같은 명령으로 수정 전 FAIL을 재현할 수 없다.
수정 전 실프로세스 보존 검사도 PID 허용목록 안에서만 수행한다.
`ARTIFACTS=/tmp/lane_guard_check.*` 아래 `summary.json`, `head_source.txt`, 케이스별
`cycles.log`, `calls.jsonl`, `signals.jsonl`, `decoy_samples.json`을 남긴다.
실패가 있으면 rc 1, 실제 프로세스 증거가 불가하면 rc 77, 모두 통과하면 rc 0이다.

동결 guard suite는 **운영 레인이 하나도 없을 때만 직접 호출**한다. 1단계의
C1.5는 A가 실행하며, 5b 이후에는 새 계약과 비호환이므로 이 suite를 퇴역시킨다.

```bash
python3 -I shared/harness/tests/runner_checks.py guard "$PWD/orchestration/lane_guard.sh"
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
