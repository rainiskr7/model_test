# SPEC: run_lane TRACK=full (전 트랙 3회 레인) — A 계획 (Codex 반박 반영, 2026-10-15)

## 0. 절대 제약 (실행 중 BF16 레인 보호)
- 다음 파일은 **읽기만** 한다. 한 바이트도 바꾸지 않는다: orchestration/run_lane.sh, orchestration/lane_guard.sh,
  orchestration/lanes.conf, orchestration/lanes/*.conf(기존 3개), orchestration/tests/test_run_lane_equivalence.sh,
  orchestration/tests/test_lane_guard.sh, shared/harness/**, configs/load_model_config.py, shared/results_dir.sh,
  shared/**/run_*.sh, run_full_eval.sh, run_repeated_eval.sh. (실행 중인 bash 가 run_lane.sh 를 증분으로 읽는다.)
- 새 러너는 **orchestration/run_lane_next.sh** 로 쓴다 (run_lane.sh 전체 사본 + TRACK=full 추가). 배포(rename 교체)는 A 가 한다.
- 실행 금지: orchestration/tests/test_lane_guard.sh, runner_checks.py guard, 네트워크·서버 접근, results/ 아래 쓰기, .env 읽기.
- 실행 허용: 네가 만든 fixture 시험, 그리고 기존 등가성 시험을 **임시 복사본**(orchestration/ 을 temp 로 복사하고 그 안에서 run_lane.sh := run_lane_next.sh 로 바꿈)에 대해 실행.

## 1. 범위
TRACK=full 은 반복 N=1..REPS 마다 세션 `${SESSION}_r${N}` 으로 다음 단계를 **이 순서로** 돈다(archive v8 1단계의 else 분기와 같음):
  1 nlu           : bash vsm/nlu/run_nlu.sh --model "$MODEL" --endpoint "$BASE_URL_CHAT"
  2 functionchat  : bash vsm/functionchat/run_functionchat.sh "$MODEL" "$BASE_URL_CHAT"
  3 taubench(solo): env TAUBENCH_MODE=solo TAUBENCH_TRIALS=1 TAUBENCH_MAX_CONCURRENCY=$TAUBENCH_MAX_CONCURRENCY bash vsm/taubench/run_taubench.sh "$MODEL" "$BASE_URL_CHAT"
  4 multimodal    : env KRETA_WORKERS=$KRETA_WORKERS [KRETA_RESUME=1 — 재개 지점일 때만] bash vsm/multimodal/run_all.sh "$MODEL" "$BASE_URL_V1"
  5 functionchat_judge : <RD>/<TS>/language/functionchat 이 있을 때만 — python -m shared.functionchat.judge.run_judge --results-dir "<RD>/<TS>/language/functionchat"
  6 koffvqa_judge : <RD>/<TS>/vision/multimodal/koffvqa/*_gen.xlsx 최신 파일이 있을 때만 — python -m shared.multimodal.benches.koffvqa_api_judge --predfile <xlsx> --target-model "$MODEL" --judge-model openai/gpt-4.1-mini --judge-base-url https://openrouter.ai/api/v1 --judge-api-key "$TAUBENCH_USER_API_KEY" --seed 0
  7 derive        : 6 이 실행됐을 때만 — python derive_multimodal_publish.py --base . --write --source <이 세션의 source 경로>. derive.py 의 --source 의미(벤치 단위인지 세션 단위인지)를 코드로 확인해 **이 세션 것만** 건드리게 호출한다. 세션 한정이 불가능하면 7 을 빼고 "derive 는 레인 밖에서 수동" 이라고 dry-run 계획과 README 에 적는다.
  harness(KMMLU)·taubench standard 는 full 에 포함하지 않는다(각각 kmmlu / taubench_std4 TRACK).
- 모든 단계는 `EVAL_TIMESTAMP="$TS"` 로 실행하고 로그는 `$BASE/logs/$TS/<stage>.log` 에 append (기존 run_track 과 같은 형식의 "[TS] <stage> 시작: …" / "[TS] <stage> 종료 rc=N" 줄을 orchestrator.log 에 남긴다).
- <RD> = 결과 모델 폴더 = `shared/results_dir.sh` 의 `results_model_dir` 로 구한다(철자 재사용). `-m` 호출로 judge 가 세션·경로를 올바로 잡는지(EVAL_TIMESTAMP 로 세션 결정, cwd 의존 없음) 코드로 확인하고, cwd 의존이 있으면 v8 처럼 해당 디렉터리로 cd 해서 부른다.

## 2. 환경 (단계별 주입만, 전역 export 금지)
- 기존 kmmlu / taubench_std4 경로의 환경·출력·rc 는 **바이트 단위로 그대로**(등가성 시험 103 PASS 유지). 51-52행의 export 분기에 full 을 끼울 때 kmmlu/std4 쪽 결과가 바뀌면 안 된다.
- full 에서 전역 export 는 MODEL_TEST_BASE, OPENAI_API_KEY, TAUBENCH_USER_API_KEY(judge·taubench 용), BASE_URL_*_OVERRIDE, loader 출력만. AGENT_REQUEST_TIMEOUT 과 NUM_CONCURRENT 는 full 단계 환경에 **넣지 않는다**(functionchat·solo tau 는 자기 기본 60초; v8 과 같음).
- 새 conf 키: KRETA_WORKERS(정수 1..4, 기본 4), KRETA_RESUME(0|1, 기본 0), RESUME_FROM(선택, 형식 `r<N>:<stage>`, stage ∈ nlu|functionchat|taubench|multimodal|functionchat_judge|koffvqa_judge|derive). full 에서는 REPS 양의 정수·STOP_LABEL 필수를 kmmlu 와 같이 검증. 모르는 키·잘못된 값은 rc 2.

## 3. 충돌 거부와 재개
- RESUME_FROM 이 없으면: 반복 N 의 첫 단계 전에 `<RD>/${SESSION}_r${N}` 이 존재하면 "세션 존재 — 재개는 RESUME_FROM" 로그 후 rc 2 (run_repeated_eval 과 같은 정책).
- RESUME_FROM=rK:stage 이면: r1..r(K-1) 전체와 rK 의 stage 이전 단계를 "skip (resume)" 로 로그만 남기고 건너뛴다. rK 의 stage 부터 정상 실행. KRETA_RESUME=1 은 재개 지점이 정확히 rK:multimodal 일 때 그 단계에만 주입한다. 그 외 반복/단계에는 절대 주입하지 않는다.

## 4. 실패 정책
- 어느 단계든 rc==3 또는 rc>=129 → 즉시 `exit rc` (잠금 충돌·신호 종료; run_full_eval 과 같음).
- 필수 단계 nlu·functionchat·multimodal rc≠0 → "[TS] <stage> 실패 — $STOP_LABEL 레인 중단 (원인 확인 후 수동 재개)" 로그, `exit rc`.
- taubench(solo) rc≠0 → 로그만, 계속 (Qwen 템플릿 거부가 측정된 실패).
- judge·derive rc≠0 → 로그, 계속, 실패 수 누적. 레인 끝에 "=== $END_LABEL 레인 종료 (판정 실패 n건) ===" 를 남기고 n>0 이면 exit 1, 아니면 exit 0. 성공 표시는 모든 단계 rc 0 일 때만.

## 5. dry-run 계약 (LANE_DRY_RUN=1)
- .env 읽기·로그 쓰기·preflight·결과 폴더 조회 모두 하지 않는다(judge 조건부 실행은 실제 파일 존재와 무관하게 고정 문구로 출력).
- 출력: `BASE=`, `conf=`, `HOST=` 다음에 반복마다 `SESSION=<TS>` 한 줄과 단계 7개의 `COMMAND=` 줄(조건부 단계는 `COMMAND[if-exists]=` 접두). RESUME_FROM 이 있으면 건너뛰는 단계는 `SKIP=<TS> <stage>` 로 출력. 기존 kmmlu/std4 dry-run 출력은 그대로.

## 6. 시험 (새 파일 orchestration/tests/test_run_lane_full.sh, bash 3.2 호환; 등가성 시험처럼 python3 -I 보조 허용)
fixture: temp 디렉터리에 orchestration/ 복사(run_lane.sh := run_lane_next.sh), stub 러너·judge·derive·loader 로 argv/env/cwd/EVAL_TIMESTAMP 를 기록, 합성 .env, 합성 results 폴더. 서버·네트워크·실제 results/ 없음.
케이스(각각 PASS/FAIL 줄 + 끝에 SUMMARY {"pass":N,"fail":M,"inconclusive":K}):
  F1 dry-run 리터럴: REPS=3 계획 전체를 기대 파일과 byte 비교; .env 미접근(없어도 rc 0).
  F2 충돌 거부: 세션 폴더 존재 + RESUME_FROM 없음 → rc 2, 러너 미호출.
  F3 실패 정책: nlu rc 1 → 이후 단계·다음 rep 미호출, exit 1; taubench rc 1 → 계속; judge rc 1 → 계속하고 최종 exit 1 + 종료 문구; multimodal rc 3 / rc 130 → 즉시 exit 3/130.
  F4 재개: RESUME_FROM=r2:multimodal + KRETA_RESUME=1 → r1 전부·r2 nlu/functionchat/taubench SKIP, r2 multimodal 환경에만 KRETA_RESUME=1, r3 에는 없음.
  F5 환경 격리: 단계 환경에 AGENT_REQUEST_TIMEOUT·NUM_CONCURRENT 없음; taubench 단계에만 TAUBENCH_MODE=solo TAUBENCH_TRIALS=1; multimodal 에만 KRETA_WORKERS.
  F6 conf 검증: 모르는 키, KRETA_WORKERS=9, RESUME_FROM=r0:x, REPS=0 → rc 2.
  F7 기존 kmmlu/std4 dry-run 출력이 run_lane.sh 와 byte 동일(두 러너를 같은 fixture 로 돌려 diff).

## 7. 산출물
- orchestration/run_lane_next.sh, orchestration/tests/test_run_lane_full.sh (+ 기대 파일), orchestration/lanes/qwen35fp8_full.conf
  (CONFIG=qwen_qwen3.5_27b_fp8, HOST_ENV=QWEN35FP8_HOST, HOST_DEFAULT=192.168.0.7:18023, KEYVAR=OPENAI_API_KEY_7, TRACK=full,
   SESSION=20261015_full, LABEL="qwen3.5 27B FP8 전 트랙 3회", PREFIX="qwen3.5 FP8 full", STOP_LABEL=qwen3.5-FP8, END_LABEL="qwen3.5 27B FP8 전 트랙 3회", KRETA_WORKERS=4),
  orchestration/README_full.md (README 에 합칠 full 절 초안: 키·재개·실패 정책·배포 순서).
  lanes.conf 에 넣을 한 줄은 README_full.md 에만 적는다(파일은 수정 금지): `qwen35fp8_full|qwen35fp8_full|aitopatom-337f|OPENAI_API_KEY_7|qwen_qwen3.5_27b_fp8`.
- 보고: 바꾼 파일 목록, 네가 돌린 정확한 명령과 결과(F1..F7, 등가성 103), 스펙과 다르게 한 결정과 이유, 확인하지 못한 것. 한국어.
