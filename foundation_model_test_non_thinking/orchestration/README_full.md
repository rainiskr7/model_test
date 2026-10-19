# full 트랙

아래 예시의 `N`은 코드 루트의 정규 절대경로다(`N="$(pwd -P)"`는 코드 루트에서 설정).

실행은 `bash "$N/orchestration/lanes/full.sh" <model_conf>`다. 모델 설정은
`orchestration/models/<model_conf>.conf`이며 SESSION_FULL이 필수다. 예:
`LANE_DRY_RUN=1 bash "$N/orchestration/lanes/full.sh" qwen35fp8`.
진입 링크는 `../run_lane.sh`를 가리키며 런타임 이름은 `qwen35fp8_full`이다.
모델 인자 규칙·기동·로그 이름은 [레인 README](README.md)를 따른다.

## 실행 범위와 설정

매 반복의 세션은 `${SESSION}_r${N}`이며 N은 1부터 REPS까지다. 단계는 아래 순서다.

1. nlu
2. functionchat
3. taubench solo, trials=1
4. multimodal (`run_all.sh`)
5. functionchat_judge: 이 세션의 `language/functionchat` 디렉터리가 있을 때
6. koffvqa_judge: 이 세션의 `vision/multimodal/koffvqa/*_gen.xlsx` 중 수정 시각이 가장 최신인 파일이 있을 때
7. derive: 이번 실행에서 이 세션의 koffvqa_judge가 rc 0으로 끝났을 때. `r<N>:derive` 재개 반복은 아래의 저장 산출 확인 규칙 적용

KMMLU/harness와 taubench standard는 포함하지 않는다. 같은 mtime의 workbook은 셸 glob 순서에서 먼저 나온 파일을 선택한다. 모든 실행 단계에 `EVAL_TIMESTAMP`를 지정하고, stdout/stderr를 `logs/<TS>/<stage>.log`에 append한다. `logs/resume_orch/orchestrator.log`에는 단계 시작 명령과 종료 rc를 남긴다. KOFFVQA judge 명령에는 `--judge-api-key-env TAUBENCH_USER_API_KEY`로 변수 이름만 전달하고, 키 값은 이미 export된 환경에서 읽는다. judge의 직접 `--judge-api-key`가 우선하며, 환경변수 옵션을 지정했는데 값이 없거나 비어 있으면 fallback 없이 rc 2로 종료한다. 두 옵션을 생략하면 기존 `OPENAI_API_KEY` fallback을 유지한다.

기존 공통 키와 함께 다음 키를 사용한다. conf는 shell을 실행하지 않는 리터럴 `key=value` 형식이다.

| 키 | full 계약 |
| --- | --- |
| SESSION_FULL | full 결과 세션 접두, 필수 |
| REPS | 양의 정수, 기본 3 |
| LANE_DISPLAY | 공통 필수 표시명; 로그 레이블은 `<LANE_DISPLAY> full` |
| KRETA_WORKERS | 1..4, 기본 4; multimodal에만 주입 |
| KRETA_RESUME | 0 또는 1, 기본 0; 정확한 multimodal 재개 지점에만 1 주입 |
| RESUME_FROM | 선택: `r<N>:<stage>`, N은 1..REPS |
| TAUBENCH_MAX_CONCURRENCY | 기존 키, 기본 4; solo taubench에만 주입 |
| AGENT_REQUEST_TIMEOUT | 양의 정수 초, 기본 300; functionchat·taubench에만 주입 |
| AGENT_TASK_TIMEOUT | REQUEST보다 큰 정수 초, 기본 900; functionchat·taubench에만 주입 |

알 수 없는 키, 잘못된 REPS/KRETA 값, 유효하지 않은 재개 단계나 반복 번호는 rc 2다. 단계 이름은 위 7개 이름과 정확히 같아야 한다. full에서는 `TAUBENCH_TRIALS`의 기존 기본 4 대신 해당 단계에 1을 주입한다. `AGENT_REQUEST_TIMEOUT`(기본 300초)과 `AGENT_TASK_TIMEOUT`(기본 900초)은 conf에서 양의 정수 초로 지정하며, TASK가 REQUEST보다 커야 한다(아니면 rc 2). full 자식 환경에서는 `NUM_CONCURRENT`와 두 timeout의 상속값을 제거한 뒤 FunctionChat·solo tau 단계에만 conf 값 또는 레인 기본값을 `env` 접두로 전달한다. nlu·multimodal·judge·derive에는 두 timeout을 전달하지 않는다. 기존 kmmlu·taubench_std4의 timeout 전달은 유지한다. taubench와 KRETA의 단계별 변수도 자식 환경에서 먼저 제거하고 필요한 단계에만 다시 넣는다. loader 출력은 기존 방식으로 적용하며, Python 모듈 호출에만 `PYTHONPATH`를 붙인다.

`models/qwen35fp8.conf`는 `CONFIG=qwen_qwen3.5_27b_fp8`, `QWEN35FP8_HOST`(기본 `192.168.0.7:18023`), `OPENAI_API_KEY_7`, `SESSION_FULL=20261015_full`, FULL_REPS=3, FULL_KRETA_WORKERS=4를 사용한다. MODEL은 loader 출력이며 러너에 하드코딩하지 않는다. 현재 모델 YAML은 `kreta_setting: direct`를 loader로 전달한다.

## 충돌과 재개

full도 다른 트랙과 함께 endpoint 문자열 HOST별 잠금을 사용한다. 같은 서버라도 포트가
다르면 다른 잠금이며, 파일은 `logs/resume_orch/.lane_host_<HOST의 [^A-Za-z0-9._-]를 _로 치환>.lock`이다.
preflight 전에 획득하고 경합 시 rc 2, 잠금 오류 시 rc 4로 종료한다. dry-run은 잠금·helper
source 없이 동작한다. 평가 자식에는 fd 9를 넘기지 않으며, 운영 종료는 프로세스 그룹 TERM이다.
flock/lockf 선택과 잠금 수명은 [레인 README](README.md)를 따른다.

RESUME_FROM이 없으면 각 반복의 첫 단계 전에 결과 세션 경로가 이미 있는지 확인한다. 있으면 `세션 존재 — 재개는 RESUME_FROM`을 기록하고 rc 2로 중단한다. 결과 모델 디렉터리는 MODEL의 `/`, `-`, `:`를 `_`로 바꾼 뒤 `shared/results_dir.sh`의 `results_model_dir`로 기존 대소문자 철자를 재사용한다. 이 helper가 여러 casefold 일치를 발견하면 rc 2로 중단한다.

선택 키는 접두 없는 공통값보다 FULL_ 접두 값이 우선한다(파일 배치 순서 무관).
예를 들어 공용 모델 conf에 다음 두 값을 지정한다. 이미 있는 `FULL_KRETA_RESUME=0`은
`=1`로 교체한다. 같은 키를 추가하면 중복 설정 오류(rc 2)다.

```ini
FULL_RESUME_FROM=r2:multimodal
FULL_KRETA_RESUME=1
```

r1의 7단계와 r2의 앞 3단계는 `skip (resume)` 로그만 남기고 건너뛴다. r2 multimodal에만 `KRETA_RESUME=1`이 들어가며 r3에는 들어가지 않는다. KRETA_RESUME=0이면 해당 단계도 새 KRETA 실행이다. 재개 지점이 다른 단계면 KRETA_RESUME=1을 설정해도 multimodal에 전달하지 않는다. RESUME_FROM이 지정된 실행은 명세대로 세션 존재 충돌 거부를 적용하지 않는다.

`RESUME_FROM=rK:derive`이면 rK의 `vision/multimodal/koffvqa_api_judge/results.json`과 `summary.json`이 둘 다 파일로 있을 때 judge를 다시 호출하지 않고 derive를 1회 실행한다. 하나라도 없거나 파일 대신 디렉터리이면 `[<TS>] derive 재개 불가 — judge 산출 없음`을 기록하고 rc 2로 즉시 종료한다. 파일 내용의 검증은 derive가 맡는다. 이후 반복은 기존대로 해당 반복의 judge가 rc 0으로 끝났을 때 derive를 호출한다. 판정부터 다시 진행하려면 `rK:koffvqa_judge`를 사용한다. dry-run은 파일 존재를 검사하지 않으며 기존 명령과 `SKIP=` 표시를 유지한다.

## 실패 정책

- 어떤 단계든 rc 3 또는 rc >=129이면 그 rc로 즉시 중단한다.
- nlu/functionchat/multimodal의 그 외 nonzero도 즉시 중단하고 STOP_LABEL을 포함한 수동 재개 안내를 남긴다.
- solo taubench의 일반 실패는 기록하고 계속한다.
- judge/derive의 일반 실패는 기록하고 누적하며 다음 단계/반복을 계속한다.
- 정상적으로 루프가 끝나면 `=== <END_LABEL> 레인 종료 (판정 실패 n건) ===`을 남긴다. n>0이면 rc 1, 아니면 rc 0이다. solo taubench만 실패해도 이 정책상 최종 rc는 0일 수 있다. 이를 전 단계 성공으로 표기하지 않으며 단계 종료 rc로 확인한다.

## 코드 확인 사항과 명세의 전제 보정

- FunctionChat `shared.functionchat.judge.run_judge`는 정식 패키지 `python -m`으로 호출한다. 세션 경로는 EVAL_TIMESTAMP에서 추론하지 않고 필수 `--results-dir`에서 받는다. 기본 `--data-dir=data/FunctionChat-Bench/data`는 cwd 의존성이 있다. 기존 러너의 `cd "$BASE"`를 유지해 저장소 루트의 data를 해석한다. judge 하위 디렉터리로 cd하면 오히려 잘못된 경로가 된다.
- KOFFVQA `shared.multimodal.benches.koffvqa_api_judge` 역시 `python -m` 호출이다. `benches.paths.get_base_dir/get_timestamp`가 MODEL_TEST_BASE/EVAL_TIMESTAMP를 우선하고 `get_results_dir`가 기존 모델 철자를 재사용한다. 결과는 같은 세션의 `vision/multimodal/koffvqa_api_judge`에 저장된다.
- `derive_multimodal_publish.py --source`는 세션 디렉터리가 아닌 벤치 디렉터리(또는 KRETA JSONL) 하나를 받는다. `publish.adapters.ADAPTERS`에 `koffvqa_api_judge`가 등록돼 있다. 따라서 `--base . --write --source <RD>/<TS>/vision/multimodal/koffvqa_api_judge`만 호출한다. 다른 세션이나 다른 벤치의 sidecar를 일괄 갱신하지 않는다. derive를 생략하거나 레인 밖 수동 작업으로 돌릴 필요는 없다.
- `shared/multimodal/run_all.sh`는 KRETA_RESUME=1이면 `run_kreta_resume.sh`를 호출하고 실패하면 1회 재시도한다. NLU/FunctionChat/taubench와 달리 내부 벤치들의 rc는 `run_checked`가 일반 실패 수로 바꿀 수 있다. 새 레인은 run_all 자체가 반환한 rc만 판정한다. 내부 rc 3/130이 항상 보존된다고 가정하지 않는다. 보호 파일은 변경하지 않는다.
- `run_repeated_eval.sh`의 기존 세션 거부는 rc 1이지만 full은 명세가 지정한 rc 2를 쓴다.
- 명세가 언급한 archive v8 파일은 이 작업 트리에서 찾지 못했다. 순서/명령은 명세와 현재 실제 진입점 코드를 기준으로 확인했다.

## Dry-run과 격리 시험

`LANE_DRY_RUN=1`은 BASE/conf/HOST 다음에 반복별 SESSION과 7개 COMMAND를 출력한다. 조건부 단계는 `COMMAND[if-exists]=`, 재개 skip은 `SKIP=<TS> <stage>`다. `<RD>`와 `<latest *_gen.xlsx>`는 고정 계획 표기다. 결과 폴더/helper, `.env`, preflight에 접근하지 않고 로그도 쓰지 않는다. venv activation과 config loader는 기존 계약대로 사용한다.

```bash
/bin/bash -n orchestration/run_lane.sh
/bin/bash -n orchestration/tests/test_run_lane_full.sh
/bin/bash orchestration/tests/test_run_lane_full.sh
```

F1..F9는 temp에 orchestration을 복사해 실행한다. stub loader/러너/judge/derive/curl과 합성 키/결과만 사용하고 `env -i`, 외부 cwd에서 실행한다. 실제 `results_model_dir` helper는 복사해서 합성 results에 대해서만 호출한다. 네트워크 접근은 없다. 기대 파일은 `fixtures_full/dry_run.txt`이며 임시 BASE만 치환한다. 각 단계 argv/env/cwd/EVAL_TIMESTAMP, 로그 append, 최신 xlsx, 조건부 skip, 실패 누적, 모든 단계의 rc 3/130을 검증한다.

등가성 시험 `test_run_lane_equivalence.sh`는 harness/taubench의 argv·환경·결과 경로를 비교하며, LANE_DISPLAY로 바뀐 orchestrator 로그 문구는 비교하지 않는다. 5b부터 fixture curl 어댑터가 200·500·다른 모델 응답을 재현하므로 소켓을 열지 않는다. `.venv`와 `configs` symlink는 기존 시험이 필요로 하는 읽기용 참조다.
활성화 전 파서 실행을 위해 fixture에 `orchestration/laneconf`도 복사한다. 실제 러너/결과/키를 사용하지 않는다.

```bash
bash orchestration/tests/test_run_lane_equivalence.sh
```

## 등록과 기동

`models/qwen35fp8.conf`는 KMMLU와 full 설정을 함께 가진다. `lanes/full.sh` 링크는
모델마다 추가하지 않는다. `lanes.conf`의 등록 행은 다음과 같다.

```text
qwen35fp8_full|full|qwen35fp8|aitopatom-337f|OPENAI_API_KEY_7|qwen_qwen3.5_27b_fp8
```

기동 전 dry-run으로 세션·재개 위치를 확인한다. 정규 절대경로 N에서 실행한다.

```bash
LANE_DRY_RUN=1 bash "$N/orchestration/lanes/full.sh" qwen35fp8
nohup perl -e 'setpgrp; exec @ARGV' /bin/bash "$N/orchestration/lanes/full.sh" qwen35fp8 >> "$N/logs/resume_orch/qwen35fp8_full.nohup.log" 2>&1 &
```

실제 모델 서버, 외부 judge, 실제 데이터/결과를 통한 평가와 checkpoint 복구는 이 격리 시험의 검증 범위 밖이다.
