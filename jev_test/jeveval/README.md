# jeveval — P1 작업 1 기능 지도

P1_CONTRACT.md 판 2의 §8-4 작업 1만 구현했다. fixture는 합성 데이터이며,
아직 없는 실행·렌더·응답 검증·채점 모듈을 호출하지 않는다.

## 현재 파일

- `__init__.py`: 패키지 네임스페이스.
- `types/__init__.py`: 공통 JSON 왕복과 dataclass 공개 이름.
- `types/specs.py`: Item, QuestionSpec, TaskSpec, SplitPlan.
- `types/records.py`: Request, AttemptRecord, CallRecord, FinalRecord.
- `types/results.py`: ParsedAnswer, LengthInfo, Threshold, RiskCell, ScoreTable.
- `io/__init__.py`: 파일 입출력 네임스페이스.
- `io/config.py`: 안전한 UTF-8 YAML 로더, 중첩 중복 키 거부, 순수 검사기 위임.
- `contract/__init__.py`: 순수 검사 네임스페이스.
- `contract/taskspec.py`: dict → TaskSpec 또는 전체 오류 문자열 목록.
- `README.md`: 이 기능 지도와 미정 계약 범위.

현재 의존 방향: `io/config → contract/taskspec → types` 및 `io/config → types`.
`types`는 io/contract에 의존하지 않는다. 전체 계약의 방향은
`run → client/io → score/data/contract → types`이며, 앞 단계 모듈은 아직 없다.
`types` 내부 공통 JSON 기능을 먼저 정의한 뒤 세 타입 파일을 공개한다.

## 사용과 검사

`jeveval.io.config.load_taskspec(path)`는 TaskSpec을 반환한다.
스키마 오류는 `TaskSpecError.errors`에 모이며, 중복 키는 위치를 포함하는
`DuplicateKeyError`로 실패한다. 순수 함수 `validate_taskspec(dict)`는 입력을
변경하지 않는다. 설정 예제 §1-1에 나열된 최상위 키를 필수로 검사한다.
`criteria`의 `"true"`/`"false"` 키는 계약 예제처럼 인용한다(SafeLoader 규칙).
YAML merge로 같은 키를 덮어쓰는 경우도 중복으로 거부한다.

모든 dataclass는 frozen이다(내부 list/dict까지 불변은 아니다).
`to_dict()`/`from_dict()`는 독립된 JSON 사본과 중첩 dataclass를 왕복한다.
알 수 없는 dataclass 필드와 NaN/Infinity는 거부한다. 도메인 검사는 별도다.

- `tests/types/test_specs.py`: 설정·분할·식별자 왕복과 사본 분리.
- `tests/types/test_records.py`: 요청 봉투·기록·중첩 타입 왕복.
- `tests/types/test_results.py`: 결과 왕복과 미정 점수 필드 거부.
- `tests/io/test_config.py`: 중복·별칭·안전 로더·계약 검사 위임.
- `tests/contract/test_taskspec.py`: §1-1 필수 필드·값·ID·질문 유형 검사.
- `tests/fixtures/test_fixtures_wellformed.py`: JSON·README·CP·temperature·바이트 해시 검사.
- `tests/conftest.py`: `python -I` 실행에 필요한 저장소 경로 추가.
- `tests/fixtures/{render,responses,scoring,splits,resume,length,temperature,b1}/`:
  §9 각 행의 입력과 기대값, 각 폴더 README.

검사: `../foundation_model_test_non_thinking/.venv/bin/python -I -m pytest -q tests`

## SPEC_AMBIGUOUS — 필드가 확정되지 않은 타입

§8-1은 타입 이름만 열거한다. 아래 미정 부분에는 새 필드를 발명하지 않았다.
따라서 이 타입들이 전체 실행에 충분하다는 뜻은 아니다.

- §1·§6·§8-1 Item: `set/group_id/item_id`만 구현. 본문과 정답 필드명·구조 미정.
- §3·§5-3 ParsedAnswer: 명시된 응답 필드만 구현. 파싱 후 답·확신 스키마 미정.
- §4-3·§5-3 LengthInfo: `length_tokens/target_end`만 구현. 상한·고정부 필드명 미정.
- §7-4 Threshold: `t_star`만 구현. 목표 위험별 threshold.json 전체 구조 미정.
- §7·§8-3 ScoreTable: 필드 자체가 없어 빈 dataclass만 정의. 실제 점수 필드는 거부.
- §5-3: `answers_parsed` 내부 구조가 없다. 타입을 추측하지 않고 JSON 값 그대로 보존한다.

`score` 질문은 이번 요청대로 스키마 오류 목록에 넣는다. 이후 응답 검증기·채점의
NotImplementedError 규칙은 이번 작업 범위가 아니다.
