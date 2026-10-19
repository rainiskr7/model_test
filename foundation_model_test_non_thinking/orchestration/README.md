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
# 2. 트랙과 모델을 고르고 독립 프로세스 그룹으로 시작한다.
name=qwen35fp8_kmmlu
mkdir -p logs/resume_orch
nohup perl -e 'setpgrp; exec @ARGV' /bin/bash "$N/orchestration/lanes/kmmlu.sh" qwen35fp8 >> "logs/resume_orch/$name.nohup.log" 2>&1 &
# 3. 기존 watchdog/temp_guard가 종료되었음을 확인하고 guard를 시작한다.
nohup perl -e 'setpgrp; exec @ARGV' /bin/bash "$N/orchestration/lane_guard.sh" >> logs/resume_orch/lane_guard.nohup.log 2>&1 &
```

4. 손으로 멈출 때는 **lane_guard PID에 먼저 TERM**을 보낸 뒤, 해당 레인의
   프로세스 그룹에 TERM을 보낸다. PID/PGID는 운영자가 확인한다.
   `kill -TERM <guard-pid>` 다음 `kill -TERM -- -<lane-pgid>` 순서다.
5. 상태는 `logs/resume_orch/.lane_guard/<name>.state`, 로그는
   `logs/resume_orch/orchestrator.log`, 잠금은 `.lane_guard.lock`이다.
   `LANEGUARD_RUNTIME_DIR`로 런타임 디렉터리를 바꿀 수 있다.
6. 진입은 `bash "$N/orchestration/lanes/<track>.sh" <model_conf>`다. track은 실행 중인
   체크아웃의 `tracks/<track>.sh` 파일로 등록한다. 이름은 `^[a-z0-9_]+$`이며 일반 파일과
   일반 파일을 가리키는 링크만 인정한다. 현재 등록은 `kmmlu`, `taubench_std4`, `full`이고
   진입 링크는 `../run_lane.sh`를 가리킨다. guard는 등록 파일의 존재만 확인하고 source하지 않는다.
   model_conf는 `^[a-z0-9_]+$`만 허용한다. `.conf`·`/`·추가 인자는 rc 2다.
   모델 설정은 `models/<model_conf>.conf`에 둔다. 런타임 이름은
   `<model_conf>_<track>`이며 상태 파일과 nohup 로그에 이 이름을 쓴다.
   `lanes.conf` 행은 `name|track|model_conf|hostname|keyvar|model`의 6필드다.
   name은 반드시 `<model_conf>_<track>`이어야 한다.
   guard는 자기 `$HERE/lanes`의 논리 경로와 `pwd -P` 물리 경로만 인정한다.
   root는 `/bin/bash <lanes>/<track>.sh <model_conf>`처럼 모델 인자가 정확히
   하나인 프로세스다. 인자 없음·추가 인자·bash 옵션은 미지원 형태로 경고한다.
   같은 트랙의 다른 모델은 별도 레인이며 잘못된 중복·미지원 경고를 만들지 않는다.
   다른 체크아웃과 임의의 심볼릭 링크 별칭은 탐색하지 않는다.
   `nohup perl ... exec` 뒤 bash가 같은 PID를 이어받으므로 이 형식과 호환된다.
7. 실행 전 해석 결과를 확인한다.

```bash
LANE_DRY_RUN=1 bash "$N/orchestration/lanes/kmmlu.sh" qwen38
LANE_DRY_RUN=1 bash "$N/orchestration/lanes/kmmlu.sh" qwenfp8
```

설정은 활성화 전에 `.venv/bin/python -B -m orchestration.laneconf`로 해석한다.
`--tracks-dir`는 실행 체크아웃의 `orchestration/tracks`이며 PYTHONPATH와 bytecode 금지는
이 명령에만 적용한다. runner·guard·laneconf가 같은 체크아웃의 등록부를 사용한다.
트랙별 export·키 읽기·잠금 뒤 검사 훅의 호출 순서와 입력은 [트랙 계약](tracks/README.md)을 따른다.
Dry-run은 설정 해석, cd, venv 활성화, config loader까지만 진행하며 `.env`를 읽지 않는다.
preflight, 로그 쓰기, harness/taubench 실행은 하지 않는다. `LANE_TOKENIZER`는
harness 인자에만 쓰며 loader가 export한 `TOKENIZER`는 유지한다.

kmmlu·taubench_std4·full 모두 preflight 전에 **endpoint 문자열 HOST**를 기준으로
잠근다. 같은 서버라도 포트가 다르면 다른 잠금이다. 파일은
`logs/resume_orch/.lane_host_<HOST의 [^A-Za-z0-9._-]를 _로 치환>.lock`이며,
레인 이름·트랙이 달라도 같은 HOST이면 중복 실행을 거부한다.
경합은 `같은 호스트 레인 실행 중 — 시작 안 함`과 rc 2, 잠금 오류는 `잠금 오류`와
rc 4로 끝난다. dry-run에서는 잠금 helper를 source하지 않고 잠금 파일도 만들지 않는다.

`harness_lock`은 fd 9를 열고 PATH의 `flock -n -E 75 9`를 우선 사용한다.
없으면 macOS의 `/usr/bin/lockf -s -t 0 9` fd 방식을 쓰며 선택 결과는
`HARNESS_LOCK_TOOL`에 남는다. 이 lockf 방식도 BSD flock이고 파일 존재 자체는
잠금 여부가 아니다. 두 방식 모두 잠긴 열린 파일의 마지막 참조가 닫히면 해제된다.
평가 자식 3곳에서 fd 9를 닫으므로 평가 프로세스가 부모 잠금을 계속 보유하지 않는다.
운영 종료는 위와 같이 **프로세스 그룹 TERM**으로 한다. 종료 후 빈 잠금 파일이 남는 것은
정상이며 삭제할 필요가 없다. 경합 중 잠금 파일을 지우면 다른 inode가 생길 수 있으므로
해제 수단으로 삭제하지 않는다.

conf는 빈 줄/첫 칸의 `#` 주석과 `key=value`를 지원한다. 첫 `=` 뒤는 전부 값이다.
값 양끝이 같은 종류의 따옴표이면 한 쌍만 제거하며 shell 확장이나 명령 실행은 하지 않는다.
공백·CR을 제거하지 않고, 인라인 주석도 해석하지 않는다. 공백만 있는 줄과 들여쓴 주석은
오류다. 마지막 줄은 개행이 없어도 읽는다. 명시적인 빈 값은 기본값을 덮어쓴다.
공통 파서는 `orchestration/laneconf`이며 스모크도 같은 parse/resolve를 쓴다.
모르는 키/인자와 설정 오류는 stderr `run_lane: <메시지>` 및 rc 2다.
필수 공통 키는 LANE_DISPLAY, CONFIG, HOST_ENV, HOST_DEFAULT, KEYVAR다.
옛 `DISPLAY` 키는 rc 2와 `key renamed: DISPLAY -> LANE_DISPLAY`로 거부한다.
중복 키 오류는 파싱 단계에서 먼저 판정한다. 내부 HOST와 dry-run의 `HOST=`는 유지한다.
선택 트랙의 `SESSION_<TRACK 대문자>` 키가 반드시 있어야 한다. 예를 들어
`SESSION_KMMLU`, `SESSION_TAUBENCH_STD4`, `SESSION_FULL`이다. 없거나 비어 있으면 rc 2다. TRACK·SESSION·LABEL·PREFIX·
STOP_LABEL·END_LABEL은 conf 키가 아니다. 네 로그 레이블은 모두
`<LANE_DISPLAY> <track>`으로 조합한다. 따라서 5b부터 운영 로그 문구는 바뀐다.

kmmlu는 LANE_TOKENIZER도 필수이며 REPS=3, REQUIRE_NOTHINK=1,
LM_EVAL_MODE=chat, NUM_CONCURRENT=8이 기본이다. NUM_CONCURRENT는 1..8이다.
std4 기본은 TAUBENCH_USER_MODEL=openrouter/openai/gpt-4.1-mini,
TAUBENCH_TRIALS=4, TAUBENCH_MAX_CONCURRENCY=4, AGENT_REQUEST_TIMEOUT=300이다.
호출 시 TAUBENCH_MODE=standard를 설정한다. full 옵션은 [README_full.md](README_full.md)를 따른다.

선택 키에는 등록된 트랙의 `<TRACK 대문자>_` 접두를 붙일 수 있다. 현재 예는
`KMMLU_`, `TAUBENCH_STD4_`, `FULL_`이다. SESSION_*는 공통 키로 먼저 판정하며,
접두가 겹치면 최장 일치한다. 등록 이름과 기존 키가 겹치는 경우도 [트랙 계약](tracks/README.md)에 설명한다.
기본값 → 접두 없는 공통값 → 선택 트랙 접두 값 순으로 적용하며, 파일 안의
공통값/접두 값 배치 순서와 무관하다. 같은 키·같은 범위의 중복은 같은 값이어도 rc 2다.
메시지는 `duplicate key: <접두를 포함한 원래 키>`이며 비선택 트랙의 중복도 오류다.
옵션 변경 시 기존 줄을 교체하고 같은 키를 뒤에 추가하지 않는다.
접두를 허용하는 키는 REPS, LANE_TOKENIZER, REQUIRE_NOTHINK, LM_EVAL_MODE,
NUM_CONCURRENT, TAUBENCH_USER_MODEL, TAUBENCH_TRIALS, TAUBENCH_MAX_CONCURRENCY,
AGENT_REQUEST_TIMEOUT, AGENT_TASK_TIMEOUT, KRETA_WORKERS, KRETA_RESUME, RESUME_FROM이다.
LANE_DISPLAY·접속 식별 키·SESSION_*에는 접두를 붙이지 않는다. 알 수 없는 키는
다른 트랙 접두가 붙어 있어도 rc 2다.

`models/qwen35fp8.conf`는 KMMLU 세션 `kmmlu_nothink_20261015`와 full 세션
`20261015_full`을 함께 보관한다. 이전 full의 REPS=3·KRETA_WORKERS=4·
KRETA_RESUME=0은 FULL_REPS·FULL_KRETA_WORKERS·FULL_KRETA_RESUME으로 보존했다.
KMMLU의 tokenizer도 그대로다. 기존 네 모델의 CONFIG·서버·키·세션은 변경하지 않았다.

재개할 때는 해당 모델 conf의 선택 트랙 세션과 옵션을 먼저 확인한다. full의
재개 설정은 `FULL_RESUME_FROM=r<N>:<stage>`이며 필요하면
`FULL_KRETA_RESUME=1`을 지정한다. dry-run의 SESSION·SKIP·COMMAND를 확인하고
같은 `<track>.sh <model_conf>` 명령으로 시작한다. KMMLU/std4에는 full 재개
의미를 적용하지 않는다. 이전 상태 파일을 새 이름으로 복사하지 않으며,
운영 guard와 레인이 없는 상태에서 새 계약으로 전환한다.

## 검증

```bash
bash orchestration/tests/test_lane_guard.sh
# 같은 guard 시험의 직접 진입점:
bash orchestration/tests/test_lane_guard_isolated.sh
bash orchestration/tests/test_run_lane_equivalence.sh
bash tests/run_pytests.sh orchestration -k lane_host_lock -v -s
cmp shared/harness/tests/runner_checks.py ../foundation_model_test_thinking/shared/harness/tests/runner_checks.py
```

HOST 잠금 시험은 임시 BASE와 합성 conf·curl·평가 스텁을 사용한다. 실제 flock/lockf로
세 트랙의 경합, 같은 서버의 다른 포트 병행, 그룹 TERM 뒤 잠금 재획득을 검사한다.
활성화 전 파서용 실제 Python과 laneconf 사본도 fixture에 준비하며 loader·평가 스텁은 유지한다.
fixture가 만든 독립 프로세스 그룹과 평가 스텁이 기록한 PID만 신호·생존 확인 대상으로
삼고, 전역 프로세스 탐색은 하지 않는다. 네이티브 도구나 신호 권한이 없으면 해당 검사는
INCONCLUSIVE 사유와 함께 pytest skip으로 표시한다. macOS lockf 결과가 Linux flock의
실행 증거를 대신하지는 않는다.

guard 시험은 표준 라이브러리 패키지 `orchestration.tests.lane_guard_check`를
`PYTHONPATH=N python3 -m`으로 실행한다. 운영 `lanes.conf`를 읽거나 복사하지
않으며, 합성 conf·합성 `tracks/kmmlu.sh`와 임시 guard/helper 사본만 사용한다.
등록 확인을 위해 합성 트랙 파일이 필요하지만 guard fixture에 venv나 laneconf는 필요하지 않다. 동결 시험을 import하지 않는다.
기존 래퍼의 선택 인자 및 `LANEGUARD_TARGET`은 검사할 guard 파일 선택용으로 유지한다.

합성 층은 fixture `bin/`의 `ps`/`pgrep`/`kill`이 `processes.json`만 읽는다.
실프로세스 층도 같은 어댑터를 거치며, fixture가 띄운 bash·sleep·미끼의 등록 PID만
`/bin/ps -p <PID>`로 조회한다. 전역 프로세스 목록은 조회하지 않는다. 시작 시각을
재확인한 등록 PID만 신호를 받으며, Bash 내장 kill은 fixture의 `BASH_ENV`에서만
비활성화해 PATH 어댑터를 우회하지 못하게 한다. `LG_CHECK_*`는 시험 어댑터 전용
변수이며 guard의 운영 주입 변수는 추가하지 않는다. health/온도는 기존 주입 명령을
사용하고 네트워크 명령은 실패하는 스텁으로 차단한다.

미끼는 fixture 밖 별도 임시 경로의 `kmmlu.sh qwen38`을 운영과 같은 nohup/Perl 형식으로
기동한다. 생존·T 상태를 반복 관측하고 guard 로그와 신호 기록에 미끼 PID가 없는지
검사한다. 관측 간 순간 상태의 부재는 샘플링만으로 증명하지 않으므로 모든 신호
시도 기록도 함께 검사한다. 정리는 등록한 PID에만 수행한다.

C1.2는 `git show HEAD:./orchestration/lane_guard.sh` 사본과 현재 guard를
각각 격리 fixture에서 검사한다. HEAD가 이미 경로 격리를 포함하면 양쪽 모두
미끼를 배제해야 한다. HEAD가 옛 5필드 형식이면 HEAD 전용 fixture만 그 형식을
사용하고 현재 guard는 6필드로 검사한다. 두 모델의 같은 트랙 식별은 합성 층과
등록 PID만 조회하는 실프로세스 층에서 별도로 확인한다.
`ARTIFACTS=/tmp/lane_guard_check.*` 아래 `summary.json`, `head_source.txt`, 케이스별
`cycles.log`, `calls.jsonl`, `signals.jsonl`, `decoy_samples.json`을 남긴다.
실패가 있으면 rc 1, 실제 프로세스 증거가 불가하면 rc 77, 모두 통과하면 rc 0이다.

동결 `shared/harness/tests/runner_checks.py guard` suite는 **퇴역(실행 금지)**이다.
5b의 모델 인자·6필드 계약과 비호환이다. 운영 레인이 없어도 실행하지 않으며,
위의 `test_lane_guard_isolated.sh`를 사용한다.

시험은 임시 fixture에서만 가짜 레인/키/HTTP 및 harness 스텁을 사용한다.
legacy 파일은 원본을 `cp -p`로 보관한 비교 기준이며 수정하지 않는다.
실제 `.env`나 운영 로그를 시험 입력/출력으로 사용하지 않는다.
runner_checks.py의 모든 suite는 `.codex_work/harness_stop_guard/` 아래에
fixture를 만든다. 샌드박스가 fixture 생성이나 ps/TCP bind를 거부하면
해당 동결 시험의 검증은 INCONCLUSIVE로 보고한다. runner_checks.py는 실패가 없을 때 PASS 없이 INCONCLUSIVE만 있으면
rc 77, PASS가 있으면 기존 계약대로 rc 0이다. guard의 MODEL PASS는
모의 프로세스 상태 검사이며 실제 프로세스 C7 PASS를 대신하지 않는다.

D8 아카이브 이동과 C4 manifest/상태 해시 확인은 A 담당이다. C2 PASS 뒤
이동하며 이 구현은 `logs/`를 변경하지 않는다. T 파일 패치가 샌드박스로
거부된 환경에서는 N의 runner_checks.py를 T의 같은 위치에 복사하고 cmp 후
T 시험을 실행해야 한다.

5b 등가성 시험은 harness/taubench의 호출 argv·환경·세션 및 결과 경로·rc를 비교한다.
LANE_DISPLAY 기반 orchestrator 로그 문구의 byte 비교는 제외하며 평가 자식의 로그 append 검사는 유지한다.
fixture curl 어댑터로 200·500·다른 모델 응답을 재현하며 소켓을 열지 않는다.

설정 통합 수용 시험은 다음으로 실행한다. CA1과 CA3의 기준은 묶음 A 시작 시 HEAD
`4e4354e122844ba8423c906057064dae6fd3074c`로 고정한다. 이후 커밋에도 중복 결함 재현을
유지하기 위한 기준이며 `git show`로 읽는다. CA3는 임시 경로 하나에 기준본/변경본을
교대로 놓고 stdout·stderr bytes와 rc를 각각 비교한다. `-s` 출력에 증거 경로가 나온다.

```bash
PYTHONDONTWRITEBYTECODE=1 bash tests/run_pytests.sh orchestration -q -s -k laneconf
```

묶음 B 수용 시험(CB1 새 트랙 추가/제거·공통 파일 해시, CB2 하드코딩 검사, CB3
HEAD byte 비교, CB4 입력 계약 음성 검증, CB5 lanes.conf와 loader 일치)은 다음과 같다.

```bash
bash tests/run_pytests.sh orchestration -q -s -k 'registry or track_contract or lanes_consistency'
PYTHONDONTWRITEBYTECODE=1 bash tests/run_pytests.sh orchestration -q -s -k 'registry or track_contract or lanes_consistency'
```

CB3 기준은 묶음 B 시작 시 HEAD `587919d3ff568a08c94a59bd7c341506c0bd9bbe`로 고정한다.
묶음 A의 결함 재현 기준은 유지한다. fixture 복사 시 소스의 `__pycache__`·`*.pyc`를
제외하며, pytest 자체의 bytecode 쓰기 허용·차단 양쪽에서 확인한다.
