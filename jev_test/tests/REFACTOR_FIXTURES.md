# d41e8b9 리팩터 회귀 기준값

두 JSON은 실제 데이터·실제 run을 읽지 않고 합성 입력으로 만든 변경 전 출력이다. 시험은 기대값을 읽기만 하며 재생성하지 않는다. 기존 `tests/fixtures`의 동결 표본은 수정하지 않았다.

| 기준값 | 생성 근거 | 비교 범위 |
|---|---|---|
| `data/items/item_wire_d41e8b9.json` | ItemFields 도입 전에 `byte_support.wire_snapshot`을 기존 코드로 실행 | 여섯 셋의 Item.to_dict JSON 바이트, systemone/B1 전송 바이트, 질문 순서·B1 라벨 대응 |
| `run/stage_d41e8b9.json` | `git show d41e8b9:jev_test/jeveval/...` 소스를 import loader로 메모리에서 실행하고 `stage_regression_support.observed` 호출 | FunctionChat·KLUE 합성 완료 run의 history·report·score·archive·compare 단계·판정·분모 |

Item 표본은 고정 task·선택지·라벨 규칙을 사용한다. 중복 묶음, KOTE 진단 강등, KorFin 가변 질문, KoSGD 직전 USER 기준선, FunctionChat 문구 정규화·extra를 포함한다. ItemFields를 Item에 중첩하지 않았는지는 기존 Item.from_dict 왕복도 함께 검사한다.

C6 기준값 생성에는 다른 worktree나 소스 파일 복사본을 만들지 않았다. baseline 로더는 `jeveval`의 모든 모듈을 기준 커밋 소스로 실행했다. 입력 생성과 관측 코드는 전후 동일하다. 현재 rules.yaml을 손상·삭제한 뒤에도 이미 완료된 역사 run 판정이 같은지 별도로 확인한다.

인접 저장소 접근 금지 때문에 C6에서 변경 범위 밖 `evalcommon` 경계만 합성했다. `cli_support.add_external`은 시험 임시 디렉터리 안에 식별용 파일을 만들고, `summary._evalcommon_schema`는 기존 summary 시험이 요구하는 필드 조립 함수를 반환한다. 그 외 실행·채점·역사 검증·보고·보존 목록·비교 계산은 실제 코드를 통과한다. 외부 라이브러리 구현, 실제 아카이브 압축 바이트, 실데이터 재채점·감사 결과를 검증했다는 뜻은 아니다.

## 이번 구현의 제한된 환경 검증 (2026-10-19)

Python 3.12.11·pytest 9.0.3과 오프라인 패키지 캐시를 사용했다. 임시 환경·임시 run은 cwd 안에 만들었고 검증 뒤 삭제했다. 감사 hook으로 다른 저장소 폴더 읽기·소켓 사용·cwd 밖 쓰기를 차단했다. 기존 시험의 기대값·skip/xfail을 바꿔 이 제한을 우회하지 않았다.

| 실행 | pytest 마지막 줄 |
|---|---|
| 전체 현재 코드·시험 | `160 failed, 2227 passed, 100 errors in 35.24s` |
| 같은 차단 조건의 d41e8b9 코드·시험 (메모리 로더) | `160 failed, 2200 passed, 100 errors in 29.15s` |
| 영향 경계·타입 묶음 최종 확인 | `270 passed in 2.83s` |

기존 nodeid 2,460개가 모두 남았고 기존 판정 변화는 0개, 새 nodeid 27개는 전부 통과했다. 수집 오류·새 skip/xfail은 0개다. 전체 실행의 260개 실패/오류는 다른 저장소 폴더 읽기 235개와 소켓 사용 25개가 차단된 결과다. 따라서 C1 전체 통과 판정은 남아 있다. 마지막 270개 묶음은 접근 차단 발생 없이 통과했다.

마지막 묶음: `tests/run/test_unit_isolation.py`, `test_execute_call.py`, `test_executor.py`, `test_executor_interrupt.py`, `test_executor_offline.py`, `tests/data/items`, `tests/types`, `tests/contract/test_stages.py`, `tests/audits/test_v4_executor_boundary.py`, `tests/run/test_stage_regression.py`, `tests/data/test_split.py`, `tests/io/test_history.py`, `tests/run/test_context.py::test_extra_unsupported_context_rejected_before_io`.

문서 검사는 덧붙은 원문 6블록의 정확한 바이트·순서·이력 절 소속, 대체된 본문 원문, NOTES 전체 원문, 기존 문서의 원문 줄 누락 0개를 확인했다. 대응표는 21행, 영향 지도는 13행이며 시험 경로가 존재한다. 실데이터 재채점·감사(C3/C4)는 실행하지 않았다.
