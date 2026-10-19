# 판 8 회귀 검증

운영 입력과 평가 결과는 사용하지 않는다. CD1은 `test_run_lane_full.sh --cd1`의
완전 격리 fixture로 실행하며, 기준 revision은 `015c3c5`다. 최종 자식 환경에
`DISPLAY=sentinel-x11`, `LANG=C.UTF-8`를 넣는다. dry-run은 `loader-dry.env`,
실실행은 일곱 stage의 `dump/<session>.<stage>/env`를 읽는다. 먼저 rc 0과 기록
존재를 검사한 뒤 sentinel을 비교한다. `sentinel.rc`는 기준본 1, 변경본 0이다.
두 코드 경로 모두 실행 성공이어야 하므로 설정 파싱 실패를 재현으로 세지 않는다.

CD3/CH1은 `test_v8_acceptance.py`, CD2/CR1은 `test_display_contract.py`,
CH2/CH3은 `test_registry_hook_order.py`, CH4는 기존 CB1이 검사한다.
CS1은 `test_smoke_cleanup.py`에서 실제 loopback 가짜 서버 및 단위 시험으로
검사한다. bind가 금지된 환경의 HTTP 시험은 INCONCLUSIVE skip으로 구분한다.
셸 묶음과 pytest 전후의 `/tmp/serving-smoke-*` 경로 집합은 검증 실행자가
별도 기록해 CS2를 확인한다. 기존 경로를 정리해서 집합을 맞추면 안 된다.

과거 기준선 4e4354e/587919d/015c3c5에는 DISPLAY, 변경본에는 LANE_DISPLAY
conf 키를 준다. 변환은 키 토큰만 대상으로 하고 값, CR, 마지막 LF는 보존한다.
정상 레인 다섯 개의 stdout/stderr/rc와 `fixtures_full/dry_run.txt`는 그대로다.

의도된 진단 byte 차이는 다음과 같다. 이름을 정규화해 차이를 숨기지 않고 각각 단언한다.

| 경우 | 기준본 | 변경본 |
| --- | --- | --- |
| laneconf CLI 설정 출력 | `DISPLAY=…` | `LANE_DISPLAY=…` |
| 빈 표시명 | `required key: DISPLAY` | `required key: LANE_DISPLAY` |
| 트랙 접두 표시명 | `key cannot have track prefix: DISPLAY` | `key cannot have track prefix: LANE_DISPLAY` |
| 옛 DISPLAY 키 | 기존 설정으로 허용 | `key renamed: DISPLAY -> LANE_DISPLAY`, rc 2 |
| track_run 누락 dry-run | rc 0, dry-run 출력 | rc 2, `track <track> defines no track_run`, stdout 없음 |

필수 훅 누락은 이제 validate/활성화/키/잠금/HTTP보다 먼저 끝난다. smoke의 PASS
기본 정리와 `base_kept`/`cleanup_error`, `--keep`, 중단 rc 130도 의도된 계약 변경이다.
메모리 시험 보고서는 `--out`으로 부모 소유 경로에 저장한 후 fixture를 정리한다.
