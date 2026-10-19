# TRACK=full — README 통합용 초안

`run_lane.sh`는 2026-10-17 에 full 분기와 전용 함수를 추가한 판으로 교체됐다(교체 전 후보 이름은 `run_lane_next.sh`, 등가성 시험 103 PASS·F1..F7 PASS 뒤 rename). guard, 등록 목록, 기존 conf 의 계약은 그대로다. 실행 진입점은 기존과 같이 `orchestration/lanes/<name>.sh` symlink다. 러너 파일을 직접 실행하면 lane 이름/BASE 해석이 맞지 않는다.

## 실행 범위와 설정

매 반복의 세션은 `${SESSION}_r${N}`이며 N은 1부터 REPS까지다. 단계는 아래 순서다.

1. nlu
2. functionchat
3. taubench solo, trials=1
4. multimodal (`run_all.sh`)
5. functionchat_judge: 이 세션의 `language/functionchat` 디렉터리가 있을 때
6. koffvqa_judge: 이 세션의 `vision/multimodal/koffvqa/*_gen.xlsx` 중 수정 시각이 가장 최신인 파일이 있을 때
7. derive: 이번 실행에서 이 세션의 koffvqa_judge를 실제 호출했을 때만

KMMLU/harness와 taubench standard는 포함하지 않는다. 같은 mtime의 workbook은 셸 glob 순서에서 먼저 나온 파일을 선택한다. 모든 실행 단계에 `EVAL_TIMESTAMP`를 지정하고, stdout/stderr를 `logs/<TS>/<stage>.log`에 append한다. `logs/resume_orch/orchestrator.log`에는 단계 시작 명령과 종료 rc를 남긴다. 명령 로그의 judge 키는 `${TAUBENCH_USER_API_KEY}`로 가린다.

기존 공통 키와 함께 다음 키를 사용한다. conf는 shell을 실행하지 않는 리터럴 `key=value` 형식이다.

| 키 | full 계약 |
| --- | --- |
| TRACK | `full` |
| REPS | 양의 정수, 기본 3 |
| STOP_LABEL | 필수 |
| KRETA_WORKERS | 1..4, 기본 4; multimodal에만 주입 |
| KRETA_RESUME | 0 또는 1, 기본 0; 정확한 multimodal 재개 지점에만 1 주입 |
| RESUME_FROM | 선택: `r<N>:<stage>`, N은 1..REPS |
| TAUBENCH_MAX_CONCURRENCY | 기존 키, 기본 4; solo taubench에만 주입 |
| AGENT_REQUEST_TIMEOUT | 양의 정수 초, 기본 300; functionchat·taubench에만 주입 |
| AGENT_TASK_TIMEOUT | REQUEST보다 큰 정수 초, 기본 900; functionchat·taubench에만 주입 |

알 수 없는 키, 잘못된 REPS/KRETA 값, 유효하지 않은 재개 단계나 반복 번호는 rc 2다. 단계 이름은 위 7개 이름과 정확히 같아야 한다. full에서는 `TAUBENCH_TRIALS`의 기존 기본 4 대신 해당 단계에 1을 주입한다. `AGENT_REQUEST_TIMEOUT`(기본 300초)과 `AGENT_TASK_TIMEOUT`(기본 900초)은 conf에서 양의 정수 초로 지정하며, TASK가 REQUEST보다 커야 한다(아니면 rc 2). full 자식 환경에서는 `NUM_CONCURRENT`와 두 timeout의 상속값을 제거한 뒤 FunctionChat·solo tau 단계에만 conf 값 또는 레인 기본값을 `env` 접두로 전달한다. nlu·multimodal·judge·derive에는 두 timeout을 전달하지 않는다. 기존 kmmlu·taubench_std4의 timeout 전달은 유지한다. taubench와 KRETA의 단계별 변수도 자식 환경에서 먼저 제거하고 필요한 단계에만 다시 넣는다. loader 출력은 기존 방식으로 적용하며, Python 모듈 호출에만 `PYTHONPATH`를 붙인다.

`qwen35fp8_full.conf`는 `CONFIG=qwen_qwen3.5_27b_fp8`, `QWEN35FP8_HOST`(기본 `192.168.0.7:18023`), `OPENAI_API_KEY_7`, `SESSION=20261015_full`, REPS=3, KRETA_WORKERS=4를 사용한다. MODEL은 loader 출력이며 러너에 하드코딩하지 않는다. 현재 모델 YAML은 `kreta_setting: direct`를 loader로 전달한다.

## 충돌과 재개

RESUME_FROM이 없으면 각 반복의 첫 단계 전에 결과 세션 경로가 이미 있는지 확인한다. 있으면 `세션 존재 — 재개는 RESUME_FROM`을 기록하고 rc 2로 중단한다. 결과 모델 디렉터리는 MODEL의 `/`, `-`, `:`를 `_`로 바꾼 뒤 `shared/results_dir.sh`의 `results_model_dir`로 기존 대소문자 철자를 재사용한다. 이 helper가 여러 casefold 일치를 발견하면 rc 2로 중단한다.

예를 들어 conf에 다음 두 줄을 지정한다.

```ini
RESUME_FROM=r2:multimodal
KRETA_RESUME=1
```

r1의 7단계와 r2의 앞 3단계는 `skip (resume)` 로그만 남기고 건너뛴다. r2 multimodal에만 `KRETA_RESUME=1`이 들어가며 r3에는 들어가지 않는다. KRETA_RESUME=0이면 해당 단계도 새 KRETA 실행이다. 재개 지점이 다른 단계면 KRETA_RESUME=1을 설정해도 multimodal에 전달하지 않는다. RESUME_FROM이 지정된 실행은 명세대로 세션 존재 충돌 거부를 적용하지 않는다.

`RESUME_FROM=rK:derive`는 유효하지만, 이번 실행에서 rK의 KOFFVQA judge를 호출하지 않았으므로 그 반복의 derive는 조건 불충족으로 skip한다. 판정부터 다시 진행하려면 `rK:koffvqa_judge`를 사용한다. 이는 명세의 “6이 실행됐을 때만 7 실행”을 그대로 적용한 동작이다.

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

F1..F6은 temp에 orchestration을 복사해 실행한다(옛 러너와의 dry-run 비교 F7은 10-17 교체 뒤 제거). stub loader/러너/judge/derive/curl과 합성 키/결과만 사용하고 `env -i`, 외부 cwd에서 실행한다. 실제 `results_model_dir` helper는 복사해서 합성 results에 대해서만 호출한다. 네트워크 접근은 없다. 기대 파일은 `fixtures_full/dry_run.txt`이며 임시 BASE만 치환한다. 각 단계 argv/env/cwd/EVAL_TIMESTAMP, 로그 append, 최신 xlsx, 조건부 skip, 실패 누적, 모든 단계의 rc 3/130을 검증한다.

기존 등가성 시험 `test_run_lane_equivalence.sh`는 교체된 러너에 그대로 적용된다. 이 시험은 임시 127.0.0.1 HTTP 서버를 사용하므로, 네트워크 전면 금지 세션에서는 loopback 예외 승인이 있어야 실행한다. `.venv`와 `configs` symlink는 기존 시험이 필요로 하는 읽기용 참조다. 실제 러너/결과/키를 사용하지 않는다.

```bash
lane_eq_tmp=$(mktemp -d /tmp/lane_full_equivalence.XXXXXX)
cp -R orchestration "$lane_eq_tmp/orchestration"
ln -s "$PWD/.venv" "$lane_eq_tmp/.venv"
ln -s "$PWD/configs" "$lane_eq_tmp/configs"
env -i HOME="$HOME" USER="${USER:-fixture}" LANG=C PATH="$PATH" \
  PYTHONDONTWRITEBYTECODE=1 /bin/bash "$lane_eq_tmp/orchestration/tests/test_run_lane_equivalence.sh"
```

## 운영 파일 교체 순서 (2026-10-17 완료 기록)

1. 기존 BF16 lane과 해당 runner를 읽는 프로세스가 종료된 뒤 후보 diff와 F1..F7/등가성 결과를 확인한다. 이 구현 작업에서는 교체하지 않는다.
2. 후보 `run_lane_next.sh`를 기존 경로로 rename 교체한다.
3. `orchestration/lanes/qwen35fp8_full.sh -> ../run_lane.sh` 진입 symlink를 만들고 아래 한 줄을 `lanes.conf`에 등록한다. 현재 작업에서는 symlink/등록 목록을 변경하지 않는다.
4. 배포 후 `LANE_DRY_RUN=1 bash orchestration/lanes/qwen35fp8_full.sh`로 계획을 확인하고 세션/재개 설정에 맞춰 실행한다.

등록 후보 한 줄:

```text
qwen35fp8_full|qwen35fp8_full|aitopatom-337f|OPENAI_API_KEY_7|qwen_qwen3.5_27b_fp8
```

실제 모델 서버, 외부 judge, 실제 데이터/결과를 통한 평가와 checkpoint 복구는 이 격리 시험의 검증 범위 밖이다.
