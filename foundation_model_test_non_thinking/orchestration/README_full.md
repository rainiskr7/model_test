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
8. taubench_standard: r1에서만 standard 실행, trials 기본 4, 사용자 모델 기본 `openrouter/openai/gpt-4.1-mini`. 세션은 `${BASE_TS}_tbstd4`이며 `BASE_TS=$SESSION`이다. r2 이후는 `skip (once per lane)`.

KMMLU/harness는 포함하지 않는다. 같은 mtime의 workbook은 셸 glob 순서에서 먼저 나온 파일을 선택한다. 모든 실행 단계에 `EVAL_TIMESTAMP`를 지정하고, stdout/stderr를 `logs/<TS>/<stage>.log`에 append한다. `logs/resume_orch/orchestrator.log`에는 단계 시작 명령과 종료 rc를 남긴다. KOFFVQA judge 명령에는 `--judge-api-key-env TAUBENCH_USER_API_KEY`로 변수 이름만 전달하고, 키 값은 이미 export된 환경에서 읽는다. judge의 직접 `--judge-api-key`가 우선하며, 환경변수 옵션을 지정했는데 값이 없거나 비어 있으면 fallback 없이 rc 2로 종료한다. 두 옵션을 생략하면 기존 `OPENAI_API_KEY` fallback을 유지한다.

기존 공통 키와 함께 다음 키를 사용한다. conf는 shell을 실행하지 않는 리터럴 `key=value` 형식이다.

| 키 | full 계약 |
| --- | --- |
| SESSION_FULL | full 결과 세션 접두, 필수 |
| REPS | 양의 정수, 기본 3 |
| LANE_DISPLAY | 공통 필수 표시명; 로그 레이블은 `<LANE_DISPLAY> full` |
| KRETA_WORKERS | 1..4, 기본 4; multimodal에만 주입 |
| KRETA_RESUME | 0 또는 1, 기본 0; 정확한 multimodal 재개 지점에만 1 주입 |
| RESUME_FROM | 선택: `r<N>:<stage>`, N은 1..REPS |
| TAUBENCH_MAX_CONCURRENCY | 기본 4; solo·standard taubench에 주입 |
| TAUBENCH_USER_MODEL / TAUBENCH_TRIALS | standard 사용자 모델 / 시행 수; 기본 `openrouter/openai/gpt-4.1-mini` / 4. 제공자·effort 선택은 [사용자 프로파일](#standard-사용자-프로파일)을 따른다 |
| AGENT_REQUEST_TIMEOUT | 양의 정수 초, 기본 300; functionchat·taubench에만 주입 |
| AGENT_TASK_TIMEOUT | REQUEST보다 큰 정수 초, 기본 900; functionchat·solo taubench에만 주입 |
| JUDGE_MODEL | FC·KOFFVQA 판정 모델, 기본 `openai/gpt-4.1-mini`; 빈값 금지 |
| JUDGE_COHORT | FC 판정 저장 이름, 기본 빈값(`judge.json`); 지정하면 `judge.<값>.json`. 소문자 `[a-z0-9][a-z0-9_-]{0,31}`만 허용. KOFFVQA에는 전달하지 않음 |
| JUDGE_PROVIDER | 선택: OpenRouter 제공자 slug; 지정하면 order 단일 제공자, allow_fallbacks=false, require_parameters=true |
| JUDGE_REASONING_EFFORT | 빈값(미전송) 또는 low·medium·high |
| JUDGE_MAX_TOKENS | 빈값(FC 700·KOFFVQA 1024 유지) 또는 양의 정수 |

판정 키도 공통 값보다 `FULL_JUDGE_*` 값이 우선한다. Stage 1의 설정 전달 범위는 full 레인과 판정기 직접 CLI다. `shared/multimodal/run_koffvqa.sh`의 선택적 API judge 경로는 새 provider·reasoning·토큰 옵션을 전달하지 않는다. FC seed는 전송하지 않고 KOFFVQA full의 `--seed 0`은 유지한다. 제공자 설정은 요청 조건이며 실제 제공자는 기존 served identity 기록으로 확인한다.

알 수 없는 키, 잘못된 REPS/KRETA 값, 유효하지 않은 재개 단계나 반복 번호는 rc 2다. 단계 이름은 위 8개 이름과 정확히 같아야 한다. solo taubench에는 `TAUBENCH_TRIALS=1`을 주입하고 standard에는 conf 값 또는 기본 4를 쓴다. `AGENT_REQUEST_TIMEOUT`(기본 300초)과 `AGENT_TASK_TIMEOUT`(기본 900초)은 conf에서 양의 정수 초로 지정하며, TASK가 REQUEST보다 커야 한다(아니면 rc 2). full 자식 환경에서는 `NUM_CONCURRENT`와 두 timeout의 상속값을 제거한 뒤 FunctionChat·solo tau 단계에만 conf 값 또는 레인 기본값을 `env` 접두로 전달한다. standard에는 REQUEST만 전달하며 TASK는 wrapper 기본 600초다. `AGENT_REQUEST_TIMEOUT>=600`이면 standard의 runner 검증에서 실패한다. nlu·multimodal·judge·derive에는 두 timeout을 전달하지 않는다. 기존 kmmlu·taubench_std4의 timeout 전달은 유지한다. taubench와 KRETA의 단계별 변수도 자식 환경에서 먼저 제거하고 필요한 단계에만 다시 넣는다. loader 출력은 기존 방식으로 적용하며, Python 모듈 호출에만 `PYTHONPATH`를 붙인다.

`models/qwen35fp8.conf`는 `CONFIG=qwen_qwen3.5_27b_fp8`, `QWEN35FP8_HOST`(기본 `192.168.0.7:18023`), `OPENAI_API_KEY_7`, `SESSION_FULL=20261015_full`, FULL_REPS=3, FULL_KRETA_WORKERS=4를 사용한다. MODEL은 loader 출력이며 러너에 하드코딩하지 않는다. 현재 모델 YAML은 `kreta_setting: direct`를 loader로 전달한다.

## 충돌과 재개

full도 다른 트랙과 함께 endpoint 문자열 HOST별 잠금을 사용한다. 같은 서버라도 포트가
다르면 다른 잠금이며, 파일은 `logs/resume_orch/.lane_host_<HOST의 [^A-Za-z0-9._-]를 _로 치환>.lock`이다.
preflight 전에 획득하고 경합 시 rc 2, 잠금 오류 시 rc 4로 종료한다. dry-run은 잠금·helper
source 없이 동작한다. 평가 자식에는 fd 9를 넘기지 않으며, 운영 종료는 프로세스 그룹 TERM이다.
flock/lockf 선택과 잠금 수명은 [레인 README](README.md)를 따른다.

RESUME_FROM이 없으면 각 반복의 첫 단계 전에 결과 세션 경로가 이미 있는지 확인한다. 있으면 `세션 존재 — 재개는 RESUME_FROM`을 기록하고 rc 2로 중단한다. 결과 모델 디렉터리는 MODEL의 `/`, `-`, `:`를 `_`로 바꾼 뒤 `shared/results_dir.sh`의 `results_model_dir`로 기존 대소문자 철자를 재사용한다. 이 helper가 여러 casefold 일치를 발견하면 rc 2로 중단한다.

standard 세션 경로가 이미 있으면 재개 여부와 무관하게 실행하지 않고 `세션 존재 — 덮어쓰지 않음(standard 미충족)`을 기록하며 standard 실패 1건으로 집계한다. 성공한 기존 결과도 자동으로 완료 인정하지 않는다.

runner는 기존 manifest의 `harness_integrity.mode`가 다르거나 판독 불가능하면 쓰기 전에 rc 2로 거절한다. 이는 mode 혼합 방지만이며 같은 mode의 재실행·덮어쓰기는 기존대로 허용한다.

선택 키는 접두 없는 공통값보다 FULL_ 접두 값이 우선한다(파일 배치 순서 무관).
예를 들어 공용 모델 conf에 다음 두 값을 지정한다. 이미 있는 `FULL_KRETA_RESUME=0`은
`=1`로 교체한다. 같은 키를 추가하면 중복 설정 오류(rc 2)다.

```ini
FULL_RESUME_FROM=r2:multimodal
FULL_KRETA_RESUME=1
```

r1의 8단계와 r2의 앞 3단계는 `skip (resume)` 로그만 남기고 건너뛴다. r2 multimodal에만 `KRETA_RESUME=1`이 들어가며 r3에는 들어가지 않는다. KRETA_RESUME=0이면 해당 단계도 새 KRETA 실행이다. 재개 지점이 다른 단계면 KRETA_RESUME=1을 설정해도 multimodal에 전달하지 않는다. RESUME_FROM이 지정된 실행은 반복 세션의 충돌 거부를 적용하지 않는다. standard 세션 보존 검사는 별도로 유지한다. r2 이후 재개에서는 r1 standard도 resume skip하며 완료 여부를 확인하지 않는다.

`FULL_RESUME_FROM=r1:taubench_standard`는 r1의 앞 7단계를 건너뛰며 이후 r2..REPS는 기존대로 진행한다. `rK:taubench_standard`에서 K가 1이 아니면 rc 2다.

모델 conf에 `FULL_RESUME_FROM=rK:derive`를 지정하면 rK의 `vision/multimodal/koffvqa_api_judge/results.json`과 `summary.json`이 둘 다 파일로 있을 때 judge를 다시 호출하지 않고 derive를 1회 실행한다. 하나라도 없거나 파일 대신 디렉터리이면 `[<TS>] derive 재개 불가 — judge 산출 없음`을 기록하고 rc 2로 즉시 종료한다. derive rc 0 뒤에는 저장된 judge 파일의 완전성을 검사한다. 정상 진행과 이후 반복도 judge rc 0 또는 10이면 같은 derive·검사를 실행한다. 셸 환경변수만 지정하면 conf 로딩에서 덮어쓰므로 재개 설정은 conf에 둔다.

판정부터 다시 진행하려면 conf에 `FULL_RESUME_FROM=rK:koffvqa_judge`를 지정한다. 해당 반복에 prediction xlsx가 없으면 rc 2로 종료한다. 재판정은 실패 행만 이어서 처리하지 않고 xlsx 전체를 다시 채점한다. 10-05의 246/275(크레딧 부족), 10-06의 274/275(JSON parse 오류) 같은 불완전 판정은 원인을 해결한 뒤 이 경로로 재채점한다. `rK:derive`는 저장된 불완전 판정을 복구하지 않는다.

기존 판정과 모델·provider·effort·실효 토큰 상한(추가로 KOFFVQA temperature·seed)이 같으면 재채점한다. 다르거나 기존 판정 기록을 읽거나 식별할 수 없으면 요청 없이 judge rc 2로 거절하고 기존 산출물을 보존한다. full은 이를 판정 실패로 누적하고 해당 derive를 건너뛰어 최종 rc 1을 낸다. FC는 `JUDGE_COHORT`로 선택한 파일 안에서 프로파일을 검사하며 다른 코호트 파일은 읽거나 덮어쓰지 않는다. KOFFVQA의 다른 프로파일 판정은 아래 절차로 새 세션에 저장한다.

## 저장된 예측의 재판정

FC는 원본 예측 폴더에 `judge.<c>.json`을 추가한다. `<c>`는 위 slug 규칙을 따르며 빈값은 기존 `judge.json`을 선택한다. 코호트 이름은 저장 파일 선택자다. 같은 이름을 썼더라도 판정 프로파일이 다르면 보고서의 judge 우열 비교는 거부된다. `--retry-unresolved`도 선택된 파일의 미해결 항목만 재판정한다. 예측·summary를 다른 세션으로 복사하면 exact 반복 관측으로 다시 수집될 수 있으므로 복사하지 않는다.

N 루트에서 실행한다. `<RD>`는 `results/<모델 폴더>`의 실제 경로이며 `<원본 세션>`은 예측을 생성한 세션이다. 아래 판정 모델과 선택 provider·effort·토큰 상한은 비교하려는 프로파일에 맞춘다.

```bash
python -m shared.functionchat.judge.run_judge \
  --results-dir <RD>/<원본 세션>/language/functionchat \
  --judge-cohort <c> --judge-model <판정 모델>
python -m reports.report_agent_tracks --base . --judge-cohort <c>
```

보고서는 지정한 파일만 읽고 없으면 judged 축을 생략한다. 빈값에서는 기존 `judge.json`만 읽는다. 지정한 코호트명은 콘솔에 표시하며 `--write-markdown <경로>`로 저장한 Markdown에도 표시한다.

KOFFVQA는 새 판정 세션에 `results.json`·`summary.json`을 저장한다. `run_config`는 summary에 내장되며 별도 `run_config.json`은 구형 기록의 읽기 경로다. 현재 결과 base를 명시해 원본 예측과 판정 세션을 같은 모델 폴더 아래에 둔다. `<생성 파일>`은 실제 `*_gen.xlsx` 이름이다.

```bash
MODEL_TEST_BASE="$PWD" EVAL_TIMESTAMP=<원본 세션>_judge_<c> \
python -m shared.multimodal.benches.koffvqa_api_judge \
  --predfile <RD>/<원본 세션>/vision/multimodal/koffvqa/<생성 파일> \
  --target-model <모델> --judge-model <판정 모델> \
  --judge-base-url https://openrouter.ai/api/v1 \
  --judge-api-key-env TAUBENCH_USER_API_KEY --seed 0
python derive_multimodal_publish.py --base . --write \
  --source <RD>/<원본 세션>_judge_<c>/vision/multimodal/koffvqa_api_judge
python -m shared.multimodal.benches.koffvqa_judge_complete \
  <RD>/<원본 세션>_judge_<c>/vision/multimodal/koffvqa_api_judge
```

`_judge_<c>`는 명명 관례이며 코드가 접미사를 해석하지 않는다. 판정 프로파일이 다른 기존 세션을 덮어쓰지 않도록 새 이름을 쓴다. 판정 rc 0 또는 10일 때 저장 산출물에 derive를 적용하고, 그 외 오류에서는 먼저 원인을 해결한다. `koffvqa_judge_complete`는 행 수·점수의 완전성만 검사하며 발행 가능 확인이 아니다. 일반 derive의 rc 0도 발행 가능을 보장하지 않는다. `_derived/publish.json`의 `status`·`publishable`·`failures`를 확인한다.

어댑터는 판정 세션의 형제 `koffvqa/*_gen.xlsx`를 우선한다. workbook이 하나도 없고 `summary.predfile`에서 읽은 예측 세션과 판정 세션이 모두 식별되며 서로 다를 때만, 현재 모델 폴더의 `<예측 세션>/vision/multimodal/koffvqa`를 읽는다. 기록된 절대 base 경로는 사용하지 않는다. 형제 workbook이 있는데 SHA가 다르면 원본 세션으로 우회하지 않고 거부한다. 원본 세션을 참조한 재판정 sidecar는 원본 xlsx가 남아 있고 SHA가 같아야 보고서가 받는다. 백업·이동 시 두 세션의 의존 관계를 보존해야 한다.

**재판정 세션은 모델 간 비교에 쓰지 않는다.** `api_judge_rejudge`는 고정 예측에 대한 판정기 비결정성 진단이며, 예측 SHA가 지문에 들어가 다른 예측끼리는 코호트가 갈린다. Stage 2는 KOFFVQA 저장 지원과 FC 비교까지다. KOFFVQA 모델 간 비교를 위한 재생성 또는 비교 계약 변경은 별도 Stage 2b 결정이다. `tools/output_baseline`은 이 교차 세션 재판정 배치의 의존 파일 복사를 지원하지 않으며 이번 변경 범위 밖이다.

## 실패 정책

- 어떤 단계든 rc 3 또는 rc >=129이면 그 rc로 즉시 중단한다.
- nlu/functionchat/multimodal의 그 외 nonzero도 즉시 중단하고 STOP_LABEL을 포함한 수동 재개 안내를 남긴다.
- solo taubench의 일반 실패는 기록하고 계속하며 실패 집계에서 제외한다. standard는 solo 일반 실패 여부와 무관하게 r1 끝에서 실행한다. 앞 단계의 즉시 중단 정책은 그대로다.
- standard 일반 실패는 별도 누적하고 다음 반복을 계속한다. `serving_incompatible:template_requires_user_turn` reason은 이 런에서 관측된 서빙 거부이며 영구적인 모델 불가 판정이 아니다. reason은 summary와 채점 실패 메시지에 남고 보고서는 기존대로다.
- judge/derive의 일반 실패는 기록하고 누적하며 다음 단계/반복을 계속한다.
- KOFFVQA judge는 먼저 기존 산출물을 저장하고, `total == scored == raw 행 수 > 0` 및 모든 행의 오류 없음·0~10 정수 점수를 검사한다. 불완전이면 rc 10이며 derive는 계속 실행한다. derive 성공 뒤 같은 검사 CLI가 rc 10을 반환하면 derive 실패도 1건 누적한다(따라서 judge와 derive가 각각 실패할 수 있다). 파일 읽기·JSON 오류는 검사 CLI rc 2다. 발행 게이트·측정값·저장 내용은 바꾸지 않는다.
- 정상적으로 루프가 끝나면 `=== <END_LABEL> 레인 종료 (판정 실패 n건, standard 실패 m건) ===`을 남긴다. n 또는 m이 0보다 크면 rc 1, 둘 다 0이면 rc 0이다. solo taubench만 실패해도 이 정책상 최종 rc는 0일 수 있다. 이를 전 단계 성공으로 표기하지 않으며 단계 종료 rc로 확인한다.

## 코드 확인 사항과 명세의 전제 보정

- FunctionChat `shared.functionchat.judge.run_judge`는 정식 패키지 `python -m`으로 호출한다. 세션 경로는 EVAL_TIMESTAMP에서 추론하지 않고 필수 `--results-dir`에서 받는다. 기본 `--data-dir=data/FunctionChat-Bench/data`는 cwd 의존성이 있다. 기존 러너의 `cd "$BASE"`를 유지해 저장소 루트의 data를 해석한다. judge 하위 디렉터리로 cd하면 오히려 잘못된 경로가 된다.
  직접 CLI는 `--judge-model`, `--judge-provider`, `--judge-reasoning-effort`, `--judge-max-tokens`, `--judge-cohort`를 받는다. 구형 FC 기록은 `(judge.model, None, None, 700)`으로 비교한다. 동일 프로파일의 `--retry-unresolved`는 repeats 변경을 허용하고 확정 레코드와 이전 served identity를 보존한다. 보고서는 같은 정규화 프로파일끼리만 judge 우열을 비교한다.
- KOFFVQA `shared.multimodal.benches.koffvqa_api_judge` 역시 `python -m` 호출이다. `benches.paths.get_base_dir/get_timestamp`가 MODEL_TEST_BASE/EVAL_TIMESTAMP를 우선하고 `get_results_dir`가 기존 모델 철자를 재사용한다. 결과는 같은 세션의 `vision/multimodal/koffvqa_api_judge`에 저장된다.
  두 판정기 모두 요약 최상위 `judge_request`에 model·provider·reasoning_effort·max_tokens_requested·max_tokens_effective·temperature를 기록하며 KOFFVQA는 seed도 기록한다. 토큰 옵션 생략은 requested=null, effective는 실제 700/1024다. KOFFVQA의 구형 summary는 judge_model·run_config.decoding을 사용하고, summary가 없으면 같은 폴더 run_config.json의 judge.model·decoding으로 확인한다. 식별 기록 없이 results.json만 남은 경우에는 덮어쓰지 않는다.
- `derive_multimodal_publish.py --source`는 세션 디렉터리가 아닌 벤치 디렉터리(또는 KRETA JSONL) 하나를 받는다. `publish.adapters.ADAPTERS`에 `koffvqa_api_judge`가 등록돼 있다. 따라서 `--base . --write --source <RD>/<TS>/vision/multimodal/koffvqa_api_judge`만 호출한다. 다른 세션이나 다른 벤치의 sidecar를 일괄 갱신하지 않는다. derive를 생략하거나 레인 밖 수동 작업으로 돌릴 필요는 없다.
- `shared/multimodal/run_all.sh`는 KRETA_RESUME=1이면 `run_kreta_resume.sh`를 호출하고 실패하면 1회 재시도한다. NLU/FunctionChat/taubench와 달리 내부 벤치들의 rc는 `run_checked`가 일반 실패 수로 바꿀 수 있다. 새 레인은 run_all 자체가 반환한 rc만 판정한다. 내부 rc 3/130이 항상 보존된다고 가정하지 않는다. 보호 파일은 변경하지 않는다.
- `run_repeated_eval.sh`의 기존 세션 거부는 rc 1이지만 full은 명세가 지정한 rc 2를 쓴다.
- 명세가 언급한 archive v8 파일은 이 작업 트리에서 찾지 못했다. 순서/명령은 명세와 현재 실제 진입점 코드를 기준으로 확인했다.

## Dry-run과 격리 시험

`LANE_DRY_RUN=1`은 BASE/conf/HOST 다음에 반복별 SESSION과 기존 7단계 COMMAND를 출력하고, r1 끝에는 `SESSION=<BASE_TS>_tbstd4`와 standard COMMAND를 추가한다. r2·r3의 standard는 SKIP으로 표시한다. 조건부 단계는 `COMMAND[if-exists]=`, 재개 skip은 `SKIP=<TS> <stage>`다. derive 뒤에는 `COMMAND[if-derive-rc=0]=`로 완전성 확인 명령도 표시한다. 완전성 확인은 별도 재개 단계가 아니다. `<RD>`와 `<latest *_gen.xlsx>`는 고정 계획 표기다. 결과 폴더/helper, `.env`, preflight에 접근하지 않고 로그도 쓰지 않는다. venv activation과 config loader는 기존 계약대로 사용한다.

```bash
/bin/bash -n orchestration/run_lane.sh
/bin/bash -n orchestration/tests/test_run_lane_full.sh
/bin/bash orchestration/tests/test_run_lane_full.sh
```

F1..F9는 temp에 orchestration을 복사해 실행한다. stub loader/러너/judge/derive/curl과 합성 키/결과만 사용하고 `env -i`, 외부 cwd에서 실행한다. 실제 `results_model_dir` helper는 복사해서 합성 results에 대해서만 호출한다. 네트워크 접근은 없다. 기대 파일은 `fixtures_full/dry_run.txt`이며 임시 BASE만 치환한다. 각 단계 argv/env/cwd/EVAL_TIMESTAMP, 로그 append, 최신 xlsx, 조건부 skip, 실패 누적, 모든 단계의 rc 3/130을 검증한다.

C7 결함 재현은 아래 동일 시험을 작업 트리와 `KOFFVQA_COMPLETE_REVISION=3b5377e`에서 실행한다. revision 지정 시 judge·full 파일만 `git show`로 임시 checkout에 복사하며 운영 파일을 교체하지 않는다. HEAD에서는 세 사례가 rc 0 때문에 FAIL, 수정본에서는 PASS가 기대값이다. 실제 judge·derive CLI를 사용하되 client는 가짜이고 소켓 연결은 차단한다.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider \
  shared/multimodal/tests/test_koffvqa_completion_cli.py \
  orchestration/tests/test_koffvqa_completion_lane.py -k 'test_c71 or test_c72'
```

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

## standard 사용자 프로파일

| 키 | full 계약 |
| --- | --- |
| TAUBENCH_USER_PROVIDER | 기본 빈값(미전송). `[a-z0-9][a-z0-9/_.-]*` 제공자 slug; 지정하면 order 단일 제공자, allow_fallbacks=false, require_parameters=true |
| TAUBENCH_USER_REASONING_EFFORT | 기본 빈값(미전송) 또는 low·medium·high; LiteLLM 모델 맵과 무관하게 extra_body.reasoning.effort로 전달 |

공통 값보다 `FULL_TAUBENCH_USER_PROVIDER`·`FULL_TAUBENCH_USER_REASONING_EFFORT`가 우선한다. 두 옵션은 standard 단계에만 전달한다. 하나라도 지정하면 사용자 모델은 `openrouter/` 접두여야 하고 `TAUBENCH_USER_BASE_URL` 환경값과 동시에 지정할 수 없다(rc 2). `OPENROUTER_API_BASE`는 막지 않으며, 새 옵션을 쓸 때 manifest의 `user_openrouter_api_base_set`에 비어 있지 않은 환경값의 존재만 기록한다. 값 자체는 기록하지 않는다.

provider·effort가 비어 있으면 기존 요청·manifest·summary·코호트를 유지한다. 지정한 값은 manifest와 비교 지문에 들어가며 tau2 results.json의 설정 기록과 대조한다(실제 전송 또는 실제 제공자의 증거가 아님). 제공자 정책 플래그·order·effort가 다르거나 잘못된 타입이면 summary를 남기고 발행·후보 간 비교를 거부한다. low/medium 선택과 도구 호출·추론 누출·지연·지원 파라미터는 전환 전 실 요청 검증 대상이다.
