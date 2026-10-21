# 운영 절차 — 판 5 보정 4

무엇: 기존 B1·pplx 레인의 새 실행, 재개, 재판정 절차. 입력: 동결 설정·같은 실행 환경·모델 서버. 출력: 비공개 실행 기록과 공개 집계. 모든 명령은 jev_test에서 실행한다.

## 준비와 경계

`JEV_PY` 기본은 `../foundation_model_test_non_thinking/.venv/bin/python`이다. 실행 당시와 같은 venv를 사용한다. Python·numpy·scipy·zstandard·PyYAML 버전과 외부 schema도 fingerprint에 들어가므로 검사 도구를 위해 실행 venv를 업그레이드하지 않는다. ops와 tests 변경은 jeveval 코드 해시를 바꾸지 않지만 overlay가 지정한 audits 파일은 fingerprint files일 수 있다.

서버 관리 화면에서 현재 호스트와 포트를 확인한다. URL은 호스트의 `.local` 조회 후 실패하면 인자로 받은 대체 주소를 사용한다. 재배포·네트워크 변경 후에는 주소·포트를 다시 확인하고 모델 YAML은 수정하지 않는다.

키 값은 명령 인자에 넣지 않는다. 모델의 `auth_env`와 같은 환경 변수 이름을 넘긴다. 해당 환경 변수에 값이 이미 있으면 사용하고, 없으면 `JEV_ENV_FILE`(기본 `../foundation_model_test_non_thinking/.env`)에서 그 변수의 한 줄 값만 읽는다. 셸 코드를 source하지 않는다.

```bash
ops/lane.sh "$MODEL" "$HOST" "$FALLBACK" "$PORT" "$KEY_VAR" "$RUN_ID"
SETS=kosgd ops/lane.sh "$MODEL" "$HOST" "$FALLBACK" "$PORT" "$KEY_VAR" "$RUN_ID"
OPS_DRY_RUN=1 SETS=kosgd ops/lane.sh "$MODEL" "$HOST" "$FALLBACK" "$PORT" "$KEY_VAR" "$RUN_ID"
```

기본 순서는 KLUE-MRC → KorFin → FunctionChat → K-MHaS → KOTE → KoSGD다. 일반 셋은 dev → threshold → test → score → certify, FunctionChat은 test 뒤 extra를 실행한다. KoSGD는 full dev → actions_only dev → 두 threshold → full test → actions_only test → 두 score/certify 순서다. `question_scoring: separate` 모델은 actions_only를 파생하고, `joint` 모델은 actions_only도 일반 run으로 전송한다.

## 중단과 같은 run 재개

```bash
ops/stop.sh "$MODEL"       # 지금 셋이 끝난 뒤 중단
ops/stop.sh now "$MODEL"   # 소유 PID·시작 시각 확인 뒤 TERM
ops/status.sh "$MODEL" "$RUN_ID"
```

모델 인자를 생략한 stop은 모든 레인에 적용한다. stop now는 이 ops의 잠금으로 소유권을 확인한 프로세스만 종료한다. 옛 `.work` 실행기는 별도로 관리한다. TERM 시 lane은 자식 Python과 watch를 정리한다.

재개 전 자신이 만든 `.work/ops/STOP` 또는 `.work/ops/STOP.<model>`을 확인하고 의도한 표시만 지운다. 같은 명령·같은 run ID로 다시 실행한다. 잠금 `.work/ops/lock.<model>.<run>`은 중복 실행을 거부하고 죽은 PID의 잠금만 회수한다. 소유 파일이 없거나 살아 있는 PID가 있으면 멈추며 자동 삭제하지 않는다.

run은 기존 final을 상태에 관계없이 건너뛴다. 실패 final도 다시 전송하지 않는다. 완료 여부를 파일 존재로 판단해 run을 생략하지 않는다. seal은 test 시작 전에 생기므로 threshold를 생략하는 근거일 뿐 test 완료 표시가 아니다.

일반 run 전에는 건강 확인이 있어 이미 끝난 단계도 서버·키·인코더 환경이 필요하다. systemone은 모델 목록 GET, B1은 합성 ping 1토큰 POST다. `JEV_WAIT_SECONDS`는 건강 확인 대기의 상한 초(기본 43200)이며 60초마다 확인한다. run 실패는 총 세 번 시도한다. watch는 5초 관찰 보조 장치이며 실패 final 생성 전 중단을 보장하지 않는다. `question_scoring: separate`의 파생 actions_only만 `--offline`을 사용해 건강 확인·URL 없이 처리한다. `joint`의 actions_only는 건강 확인 후 `--base-url`로 실행한다.

status는 split 기대 logical 수, final 고유 수·상태별 수, 파싱된 정상 attempts 줄 수·고유 call 수, 산출물 존재와 reader 경고를 보여 준다. 끊긴 마지막 줄은 정상 시도 수에 포함되지 않고 경고에 남는다. ID 일치·파일 존재는 관측이며 완료·무결성 인증이 아니다. certify 파일은 존재하지 않는다.

dry-run은 읽기 전용 Python 메타데이터 도우미로 모델 YAML을 읽어 `kind`와 `question_scoring`에 맞는 명령 계획을 출력한다. 평가 CLI·curl·watch·sleep·잠금 생성은 실행하지 않고 키 값이나 `.env`도 읽지 않는다. seal·STOP 존재는 관측하며 compare 기존 모델 검증은 실행하지 않는다. 실제 성공이나 상태 검증의 대체가 아니다.

## replay와 중간 중단

```bash
ops/replay.sh "$MODEL" "$OLD_RUN" "$NEW_RUN" "$REASON"
```

새 run ID와 비어 있지 않은 한 줄 사유를 사용한다. 일반 셋은 dev copy → offline dev → threshold → test copy → offline test → FC extra copy/offline → score/certify다. KoSGD의 `question_scoring: separate` 모델은 full만 copy하고 actions_only를 파생한다. `joint` 모델은 full과 actions_only 모두 각 단계에서 copy 후 offline으로 재판정한다. replay는 두 모델 모두 전송하지 않는다. `n_deferred > 0`이면 해당 셋을 중단하고 다른 셋으로 진행한다. 종료 코드 3은 미수신이 남았음을 뜻한다.

중단된 replay 전체를 무조건 다시 실행하지 않는다. 대상 final은 빈 파일이어도 copy를 거부한다. status의 replay/final 존재와 기존 실행 로그로 **어느 단계까지 복사했는지** 먼저 확인한다. replay marker는 attempts보다 먼저 쓰이므로 marker만으로 복사 성공을 단정하지 않는다.

- 한 셋 전체가 아직 미복사라면 `SETS=<set> ops/replay.sh …`로 그 셋만 처리한다.
- 한 셋의 dev는 이미 처리됐고 test/extra가 미복사라면 replay.sh로 그 셋 전체를 다시 부를 수 없다. 아래의 개별 CLI copy/offline 명령을 **미복사 단계에만** 사용한다. test의 threshold와 extra의 test 선행 조건을 먼저 충족한다.
- 이미 복사한 단계에 final이 생겼다면 copy 대신 `run --offline`으로 재판정한다. 미수신이 남아 실제 전송이 필요하면 해당 `run --base-url`을 실행한다.
- 뒤 단계도 복사·offline 처리를 마쳤거나 해당 단계의 추가 전송을 의도한 경우에만 `SETS=<set> ops/lane.sh …`를 사용한다. 미복사 단계를 모르는 상태에서 lane을 부르면 원본에 있는 요청을 새로 보낼 수 있다.

```bash
BOOT='import runpy, sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); runpy.run_module("jeveval.run.cli", run_name="__main__")'
PY=${JEV_PY:-../foundation_model_test_non_thinking/.venv/bin/python}
"$PY" -I -B -c "$BOOT" replay --model "configs/models/$MODEL.yaml" --task "configs/tasks/$TASK.yaml" --stage "$STAGE" --run-id "$NEW_RUN" --source-run-dir "$SOURCE_DIR" --reason "$REASON"
"$PY" -I -B -c "$BOOT" run --model "configs/models/$MODEL.yaml" --task "configs/tasks/$TASK.yaml" --stage "$STAGE" --run-id "$NEW_RUN" --offline
```

offline의 `ok:true`만으로 완료라 판단하지 않고 `n_deferred`도 확인한다. `--offline`과 `--base-url`을 함께 주지 않는다. 파생판은 직접 replay하지 않는다.

## pplx 이어서와 마무리

```bash
SETS=kosgd ops/lane.sh pplx_v1_1 "$HOST" "$FALLBACK" "$PORT" "$KEY_VAR" main_20261019T141841
ops/compare.sh main_20261019T141841 pplx_v1_1 b1_qwen3_8_27b b1_qwen3_8_27b_fp8
```

score는 risk/scores와 주판 summary를 덮어쓴다. threshold는 seal 전에는 덮어쓰고 seal 후에는 거부한다. certify는 파일을 쓰지 않고 a/b/c와 ok를 JSON으로 반환한다. test 전체 완료 또는 점수 전체의 독립 인증을 뜻하지 않는다. 각 명령의 종료 코드를 확인한다.

compare는 일곱 판을 만들며 같은 compare ID에서 참여 모델 집합이 다르면 어떤 비교도 쓰기 전에 거부한다. 같은 집합은 다시 계산해 덮어쓴다. report는 기존 파일을 거부하므로 새 파일명을 사용하고 일곱 compare ID를 `--compare-id`에 명시한다.

```bash
"$PY" -I -B -c "$BOOT" score --run-dir "$RUN_DIR"
"$PY" -I -B -c "$BOOT" certify --run-dir "$RUN_DIR"
"$PY" -I -B -c "$BOOT" report --run-id "$RUN_ID" --models "$MODEL" --out "$NEW_REPORT"
```

결과 커밋은 공개 집계·검증된 보고서만 명시적으로 선택한다. `.gitignore`의 attempts/final, T0 원기록, dataset, archive, `.work`는 포함하지 않는다. 로그·last.out·잠금·STOP은 `.work/ops/`에 둔다. `.gitignore`는 이미 추적된 파일이나 과거 커밋을 제거하지 않으므로 공개 전에 [publish_check](../audits/publish_check/README.md)로 최종 커밋 범위를 검사한다.

## kosgd2 등록 경로 (계약 §9c)

`kosgd2`는 `OPTIONAL_SETS`에만 있으며 기본 실행에 들지 않는다. kosgd2 는 SETS=kosgd2 로만 명시 실행한다.

명시적으로 `SETS=kosgd2 ops/lane.sh "$MODEL" "$HOST" "$FALLBACK" "$PORT" "$KEY_VAR" "$RUN_ID"`를 사용한다.
기본 셋 목록에는 자동으로 추가하지 않는다. 실행 진입점과 lock/STOP/stop now는 기존 lane 그대로다.
`kosgd2_steps.sh`는 source되는 순서 모듈이며 직접 실행용 파일이 아니다.

두 판의 상태 선검사 → full dev → actions_only dev → 일반 threshold 두 판 → question-threshold 두 판
→ score-variants threshold 두 판 → full test → actions_only test → 두 판 score/certify
→ 두 판 question-risk·score-variants risk 순서다. separate의 actions_only는 offline 파생이고 joint는 직접 실행이다.
kind(systemone/B1)와 question_scoring(separate/joint)은 별개 축이며 실제 run의 모델 유효성 검사는 기존 CLI가 담당한다.

registration_status.py의 read_registration_state는 기존 context·등록 검사기와 dev 재계산을 재사용한다.
변형 dev 검증은 analysis_gate와 같은 variant_registration.check_development를 호출한다.
kosgd2_needed가 stage/threshold의 action·skip 공통 처리를 맡으며 실행 명령의 종료 코드를 그대로 반환한다.
완료 dev/test 생략은 cmd_run.read_resume_inputs의 직접·파생 resume 검사도 통과해야 한다.
생략 판정에서는 손상 tail을 거부하며 일반 run의 기존 tail 복구 정책은 바꾸지 않는다.
next_registration_action은 missing→create, ready/sealed→skip, damaged/미지→stop만 결정한다.
정상 완료 dev/test와 유효 threshold는 건너뛴다. 부분 seal·변조된 threshold는 평가 파일 쓰기·전송 전에 중단한다.
운영 lock/로그의 생성·정리는 그대로이며 score/보조 결과는 정상 재실행 시 동일 값으로 다시 쓸 수 있다.
셋 안 실패 단계 뒤에는 진행하지 않는다. 기존 run 3회 재시도와 셋 실패 뒤 다음 셋 처리는 유지한다.

OPS_DRY_RUN=1은 상태 판독 없이 처음 실행할 명령 순서만 표시한다. 실행 완료를 주장하지 않는다.
status의 question_seal_present/variant_seal_present는 존재 관측뿐이다. registered 확인은 실제 question-risk와
score-variants risk의 결과에서 한다. 봉인 사이 중단을 파일 삭제나 사후 봉인으로 복구하지 않는다.
합성 검증 범위는 tests/ops/test_kosgd2_steps.py, test_registration_status.py와
 tests/run/test_serverless_pipeline.py이며 실데이터 경로 검증은 포함하지 않는다.
