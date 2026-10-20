# SPEC: run_full_eval timeout 기본값 300/900 통일 — 트리 검토 3번 (2026-10-20)

담당: A 계획·검증·커밋, X 반박(read-only) → 구현(workspace-write). 범위 N 만. 동결·운영 쓰기 금지 판 6 §0 그대로.

## 사용자 결정(10-20)
functionchat·taubench 요청 timeout 기준을 **300/900 으로 통일**. 근거: 지금 공식 r1~r3(gemma·diffusiongemma·nemotron·qwen3.8 BF16·FP8)은 run_repeated_eval→run_full_eval 경로라 request 60초(결과 metadata `request_timeout: 60.0`, timeout 오류 0건), full 레인은 판 6 4a 로 300/900. 앞으로의 측정을 full 레인과 같게 한다. 기존 60초 결과와 조건이 다르다는 것은 metadata 로 구분된다(결과 무변경).

## 현재
- `run_full_eval.sh:192-195` functionchat·taubench 를 `run_track … bash …/run_functionchat.sh|run_taubench.sh "$MODEL" "$BASE_URL_CHAT"` 로 호출, timeout 주입 없음.
- `shared/functionchat/run_functionchat.sh:40-45` 은 `AGENT_REQUEST_TIMEOUT`·`AGENT_TASK_TIMEOUT` 이 있으면 전달, 없으면 러너 기본(request 60, task 120 — run_functionchat.py 확인 필요). `shared/taubench/run_taubench.sh:65-66` 은 `${AGENT_REQUEST_TIMEOUT:-60}`·`${AGENT_TASK_TIMEOUT:-600}`.
- full 레인: README_full.md:36-39 — 300/900, functionchat·solo tau 단계에만 `env` 접두, TASK > REQUEST 아니면 rc 2.

## 요구
- run_full_eval: functionchat·taubench 두 트랙 호출에만 `AGENT_REQUEST_TIMEOUT=${AGENT_REQUEST_TIMEOUT:-300}`·`AGENT_TASK_TIMEOUT=${AGENT_TASK_TIMEOUT:-900}` 를 넘긴다(호출자가 준 값이 이긴다). 다른 트랙(harness·nlu·multimodal) 환경에는 넣지 않는다 — 전역 export 금지(X 가 다른 트랙이 AGENT_* 를 소비하는지 확인).
- 값 검증: 양의 정수, TASK > REQUEST 가 아니면 트랙 시작 전에 rc 2 + 메시지(full 레인 문구와 맞출지 X 제안). 하위 러너도 검증하지만 앞에서 막는다.
- `_master.log` 머리에 두 값 기록(`[full_eval] AGENT_REQUEST_TIMEOUT=… AGENT_TASK_TIMEOUT=…`).
- 문서: README 진입점 표 아래 "알려진 제한" 문단을 새 기본값으로 고치고, 3.4 절에 한 줄. 기존 결과가 60초였다는 사실도 한 줄.
- 시험(X 작성): `tests/test_run_full_eval.sh`(또는 새 pytest) 에서 가짜 트랙 스크립트로 functionchat·taubench 에만 300/900, 호출자 값 우선, harness·nlu·multimodal 환경에 없음, 잘못된 값 rc 2.

## 수용 조건
- C3.1(결함 재현 FAIL→PASS): 가짜 트랙 fixture 로 run_full_eval 실행 → HEAD 판 functionchat·taubench 환경에 AGENT_REQUEST_TIMEOUT 없음(FAIL), 수정본 300/900(PASS).
- C3.2: 호출자 값 우선(예 350/1000), 다른 트랙 환경에 두 변수 부재, 잘못된 값 rc 2·트랙 미실행.
- C3.3(보존): `tests/test_run_full_eval.sh` 기존 사례 rc 0, pytest 전체(캐시 허용·차단), 출력 기준선 216 MATCH, 동결 0, results 무변경.

## 반박 반영 결정(판 2, 10-20 X 반박 → A 확인)
- **현재 사실 확정**: 호출 위치 `run_full_eval.sh:198-201`. 기본값 FunctionChat 60/120(run_functionchat.py:353-354, wrapper 는 비어 있지 않을 때만 전달), taubench 60/600(run_taubench.py:385-386, wrapper 는 항상 `${…:-60}`/`${…:-600}`). 두 러너 모두 양수·TASK>REQUEST 검사(float 허용). 활성 트랙 harness·nlu·multimodal 은 두 변수 미소비(검색 범위 기준), **비활성 agent 는 소비**(run_gpustack_custom.sh:32-33).
- **주입**: 유효값을 비-export 변수(`FULL_EVAL_REQUEST_TIMEOUT`·`FULL_EVAL_TASK_TIMEOUT`)에 먼저 계산(비어 있지 않은 호출자 값 우선, 빈 값은 기본 300/900) → `run_track` 의 기존 자식 subshell `( … )` 안에서 상속된 `AGENT_REQUEST_TIMEOUT`·`AGENT_TASK_TIMEOUT` 을 unset → functionchat·taubench 호출만 `run_track <name> env AGENT_REQUEST_TIMEOUT=… AGENT_TASK_TIMEOUT=… bash …` 로 다시 넣음(full.sh:52-57·127-135 와 같은 방식). run_track 전체를 subshell 로 감싸지 않는다.
- **검증**: full 레인과 같은 본문(`AGENT_REQUEST_TIMEOUT must be a positive integer` / `AGENT_TASK_TIMEOUT must be an integer greater than AGENT_REQUEST_TIMEOUT`), 접두 `[full_eval] ERROR: `, stderr, rc 2. **activation·키 읽기·HTTP preflight 전**에. 0·음수·소수·문자열·TASK≤REQUEST 거부. 상위는 정수만(full 레인과 같음; 하위 러너는 float 허용이라는 차이를 주석).
- **로그**: `_master.log` 첫 초기화(run_full_eval.sh:175) 뒤 첫 트랙 전에 `[full_eval] AGENT_REQUEST_TIMEOUT=… AGENT_TASK_TIMEOUT=… (functionchat·taubench only)`. `CMD:` 줄에 값이 보이는 것도 시험.
- **문서**: README 진입점 표 아래 "알려진 제한" 문단 교체(config 일괄과 반복 실행의 functionchat·taubench 에 300/900, 비어 있지 않은 호출자 값 우선, 단독 wrapper 기본값은 그대로, 2026-10-20 이전 공식 r1~r3 은 request 60초로 측정·metadata 에 기록), §3.4 특징 한 줄, 반복기는 하위 rc 2 를 최종 rc 1 로 낸다는 구분. 반복기 실패 정책은 무변경.
- **시험**: 동결 `runner_checks.py` 무수정. 새 드라이버 `tests/full_eval_timeout_checks.py`(저장소 밖 임시 디렉터리에 대상 스크립트·helper 복사, 가짜 activate·loader·curl·트랙, 허용 목록 env, `_FULL_EVAL_REEXEC=1`, fixture 내부 LOG_DIR) — `--case <이름> <대상 run_full_eval.sh>` 로 HEAD 사본에도 적용 가능. `tests/test_run_full_eval.sh` 는 첫 `exec` 를 없애고 기존 동결 시험 + 새 드라이버를 순차 실행, rc 집계. 사례: 기본값, 350/1000, 한쪽만, 빈 값, 대상 앞뒤 비대상 트랙 부재, 잘못된 값 메시지·rc 2·트랙/HTTP 미실행, master/CMD 로그, agent 가 목록에 있어도 미실행. pytest 수집이 필요하면 얇은 `tests/test_full_eval_timeout.py` 래퍼(X 판단).
- **C3.1**: `--case defaults` 를 405bc53 사본에 적용 → 두 가짜 트랙 실행됐고 값 미설정이라 FAIL, 수정본 PASS.
- **실행 제한**: pytest 전체 허용(A 확인). guard 셸만 미실행. 보고만: taubench_std4 는 300/600(상속 TASK 가능), **T 확인 필요**(T run_full_eval.sh:187,189).

## 기록
| 조각 | 커밋 | C 결과 | 기록 |
|---|---|---|---|
| 3 | (git log) | C3.1 PASS(같은 `--case defaults` assertion: 405bc53 사본 rc 1 — "both fake tracks executed; observed {'functionchat': {}, 'taubench': {}}", 수정본 rc 0) · C3.2 PASS(override·request_only·task_only·empty·isolation(호출자 350/1000 export 시 harness·nlu env 비어 있음)·invalid 11종 rc 2·정확한 stderr·activation/키/HTTP/트랙 미실행·logs·agent 미실행 각 rc 0) · C3.3 PASS(tests/test_run_full_eval.sh legacy 0·timeout 0, pytest 1488 passed 2 skipped 캐시 허용·차단, 셸 3개+harness runner rc 0, 기준선 216 MATCH, 동결·shared·run_repeated_eval 0, runner_checks N/T cmp 동일, results 무변경) — 10-20 A 실행, diff 해시 a1f4f6771f00 | 사용자 결정 300/900. 보고만: taubench_std4 300/600, **T 확인 필요**(T run_full_eval.sh:187,189). guard 셸 미실행 |
