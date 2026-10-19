# 트랙 등록과 입력 계약

`run_lane.sh`와 `lane_guard.sh`는 실행 체크아웃의 `orchestration/tracks/<track>.sh`를
등록 기준으로 삼는다. 이름은 `^[a-z0-9_]+$`이고 일반 파일 또는 일반 파일을 가리키는
링크(`-f`)만 인정한다. 디렉터리와 끊어진 링크는 등록이 아니다. guard는 존재만 확인하며
트랙 파일을 source하지 않는다. laneconf는 명시적인 `--tracks-dir`를 읽고 smoke는 자기
root의 `orchestration/tracks`를 전달한다. 모듈 파일의 원본 경로로 등록부를 찾지 않는다.

트랙 파일은 함수 정의만 포함한다. source 시 평가 실행·키 읽기·로그 쓰기를 하지 않는다.
아래 변수 표가 공통부 입력의 단일 문서 목록이다. 각 파일 머리에는 사용하는 입력을 적는다.
같은 트랙 파일이 만드는 작업 변수와 Bash 내장 `BASH_REMATCH`는 외부 입력이 아니다.

## 호출 단계

| 단계 | 호출 순서와 준비 상태 |
| --- | --- |
| P0 | 인자·트랙·설정 검증 → 기본 훅 정의 → 트랙 source → `track_validate` |
| P1 | BASE로 cd → venv 활성화 → MODEL_TEST_BASE export → `track_export` |
| P2 | ORCH·HOST·TOK·BASE_TS 설정 → read_key 정의 → 비-dry-run일 때 OPENAI_API_KEY 읽기 → `track_secrets` |
| P3 | log 정의 → endpoint override export → loader 실행·eval → dry-run이면 `track_dry_run` 후 종료 |
| P4 | 로그 디렉터리 준비 → 잠금 helper source → HOST 잠금 성공 → `track_pre_http` |
| P5 | HTTP preflight 성공 → `track_run` |

준비된 입력은 이후 단계에도 사용할 수 있다. loader가 LM_EVAL_MODE를 다시 export할 수
있으므로 `track_export`를 loader 뒤로 옮기지 않는다. dry-run은 P3에서 종료하므로 키·잠금·
템플릿·HTTP 검사를 수행하지 않는다. 모델별 템플릿 검사는 P4에 둔다.

## 입력 변수

<!-- input-variables:start -->
| 변수 | 최초 사용 단계 | 의미 |
| --- | --- | --- |
| `CONFIG` `HOST_ENV` `HOST_DEFAULT` `KEYVAR` `DISPLAY` | P0 | 필수 공통 설정 |
| `LANE_TOKENIZER` `REPS` `REQUIRE_NOTHINK` `LM_EVAL_MODE` `NUM_CONCURRENT` | P0 | 해석된 선택 설정 |
| `TAUBENCH_USER_MODEL` `TAUBENCH_TRIALS` `TAUBENCH_MAX_CONCURRENCY` `AGENT_REQUEST_TIMEOUT` | P0 | 사용자 모델·동시성·timeout 설정 |
| `FULL_AGENT_TASK_TIMEOUT` `FULL_KRETA_WORKERS` `FULL_KRETA_RESUME` `FULL_RESUME_FROM` | P0 | 기존 내부 변수명으로 해석한 설정 |
| `SESSION` | P0 | 선택 트랙 SESSION 키의 값; 트랙은 이 공통 이름을 사용 |
| `TRACK` `BASE` `HERE` | P0 | 트랙 이름·코드 루트·orchestration 경로 |
| `LABEL` `PREFIX` `STOP_LABEL` `END_LABEL` | P0 | DISPLAY와 트랙 이름으로 만든 레이블 |
| `MODEL_TEST_BASE` | P1 | 평가 자식에 export한 BASE |
| `ORCH` `HOST` `TOK` `BASE_TS` | P2 | 로그 경로·유효 endpoint host·lane tokenizer·SESSION 별칭 |
| `OPENAI_API_KEY` | P2, 비-dry-run만 | 공통부가 KEYVAR로 읽은 모델 키 |
| `TAUBENCH_USER_API_KEY` | P2의 secrets 훅 이후, 비-dry-run만 | 필요한 트랙이 읽어 export한 사용자/판정 키 |
| `MODEL` `TOKENIZER` `BASE_URL_CHAT` `BASE_URL_V1` | P3 | loader가 해석한 모델·tokenizer·endpoint |
| `BASE_URL_CHAT_OVERRIDE` `BASE_URL_V1_OVERRIDE` | P3 | HOST 기반 loader 입력 |
| `PYTHONPATH` | 호출 환경 | 없을 수 있는 상속값; `${PYTHONPATH:+...}`처럼 안전하게 접근 |
<!-- input-variables:end -->

SESSION 키는 등록된 이름에서 `SESSION_<TRACK 대문자>`로 생성한다. 공통값 다음 선택
트랙의 `<TRACK 대문자>_` 접두 값을 적용한다. SESSION_*는 먼저 공통 키로 판정하며,
접두가 겹치면 최장 일치한다(`a`와 `a_b`의 경우 `A_B_` 우선). 중복 키는 동일 값도 오류다.
접두가 공통 키와 겹치는 새 이름은 기존 설정을 오류로 만들 수 있다. 예를 들어 `taubench`
등록 후 명시적인 `TAUBENCH_USER_MODEL=x`는 `USER_MODEL` 미등록 키 오류(rc 2)가 된다.

## 입력 함수와 훅 실패 처리

| 함수 | 사용 가능 단계 | 계약 |
| --- | --- | --- |
| `bad` | P0부터 | stderr에 run_lane 오류를 출력하고 프로세스를 rc 2로 종료 |
| `read_key` | P2부터, secrets 훅에서만 호출 | BASE/.env의 첫 해당 키를 읽음; dry-run에서 호출 금지 |
| `log` | P3부터, 실제 로그 쓰기는 P4/P5에서 | ORCH/orchestrator.log에 append하고 stdout에도 출력 |

선택 훅 `track_validate`, `track_export`, `track_secrets`, `track_pre_http`는 공통부의
`:` 기본 함수가 있고 트랙 정의가 이를 덮는다. **필수 훅 `track_dry_run`, `track_run`은
기본 함수가 `bad`(rc 2, "track <이름> defines no track_dry_run|track_run")** 라서 새 트랙
파일이 빠뜨리면 조용히 성공하지 않고 바로 실패한다.
기존 검증 훅은 오류 시 `bad`로 종료한다. export·secrets 훅은 기존 셸과 같이 반환값을
별도 검사하지 않으므로 치명적 오류는 `bad` 또는 명시적 `exit`로 끝낸다.
`track_pre_http`는 `track_pre_http || exit "$?"`로 호출한다. 실패 로그를 남긴 뒤
`return 1` 등으로 반환하면 HTTP와 평가를 건너뛰고 같은 rc로 종료한다.
`track_dry_run`은 출력용이며 공통부가 rc 0으로 종료한다. `track_run`은 최종 호출로
그 반환값/명시적 exit가 레인 rc다. full의 `results_model_dir`는 공통 입력이 아니라
자기 `track_run`이 source한 helper다. 평가 자식의 fd 9 닫기 규칙은 유지한다.

입력 계약 검사(`test_track_contract_units.py`)는 대문자 변수 참조가 문서 목록 또는
같은 트랙에서 대입하는 이름에 속하는지 확인한다. 일반 셸 해석기가 아니며 동적 eval·
간접 참조의 대상이나 읽기 전 초기화 누락은 증명하지 않는다. 실행 순서는 별도 훅 시험과
기존 등가성·full·잠금 시험이 검증한다. 미등록 전역을 삽입한 임시 사본은 검사 실패해야 한다.

## 트랙 추가 절차

1. `tracks/<track>.sh`에 필요한 훅을 정의하고 사용 입력을 머리 주석에 적는다.
2. `lanes/<track>.sh -> ../run_lane.sh` 링크를 만든다. 진입 링크 자체는 resolve하지 않는다.
3. 모델 conf에 `SESSION_<TRACK 대문자>`를 지정하고 필요한 선택 설정을 추가한다.
   기존 키를 바꿀 때는 해당 줄을 교체한다.
4. guard 감시 대상에는 `lanes.conf`의 6필드 행을 추가한다.
   `name=<model_conf>_<track>`, KEYVAR는 모델 conf, model은 CONFIG를 loader의 `load()`로
   푼 MODEL과 같아야 한다. hostname은 별도 운영 설정이다.
5. 저장소 밖 cwd에서 dry-run을 확인한 뒤 CB1·계약·설정 일치 시험을 실행한다.
   새 동작에 새 입력 변수가 필요하면 이 문서와 그 입력을 만드는 코드·시험도 갱신한다.

```bash
bash tests/run_pytests.sh orchestration -q -s -k 'registry or track_contract or lanes_consistency'
PYTHONDONTWRITEBYTECODE=1 bash tests/run_pytests.sh orchestration -q -s -k 'registry or track_contract or lanes_consistency'
```

CB3의 묶음 B 기준은 시작 시 HEAD `587919d3ff568a08c94a59bd7c341506c0bd9bbe`다.
기존 묶음 A의 중복 결함 재현 기준은 따로 유지한다. 각 수용 시험은 같은 임시 경로에
기준본과 변경본을 교대 배치하고 stdout·stderr·rc를 별도로 남긴다.
