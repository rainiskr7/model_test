# jeveval — P1 작업 ②-0 기능 지도

P1_CONTRACT.md 판 3 보정의 자료형·task 검사·합성 fixture를 구현했다.
실제 데이터 원문은 쓰지 않으며, render·response·score·data·run 실행 모듈은 아직 없다.

## 코드

- `__init__.py`: 패키지 네임스페이스.
- `types/__init__.py`: 기존 `from jeveval.types import X` 경로와 새 자료형 재수출.
- `types/base.py`: JsonRecord, JSON 사본·중첩 dataclass 복원·타입 검사.
- `types/specs.py`: SourceRow, BoundQuestion, Item, QuestionSpec, TaskSpec, SplitPlan.
- `types/results.py`: Rendered, ParsedAnswer, 호출별 LengthInfo.
- `types/scores.py`: Threshold, ThresholdFile, RiskCell, QStats, Population, Cost, ScoreTable.
- `types/records.py`: Request, session_id를 포함한 AttemptRecord, CallRecord, FinalRecord.
- `types/outcomes.py`: 메모리 전용 RequestOutcome, 테스트용 JSON 왕복 지원.
- `contract/__init__.py`: 계약 검사 네임스페이스.
- `contract/taskspec.py`: target_key·정적/동적 질문·성공 질문·ID 충돌 순수 검사.
- `io/__init__.py`: 파일 입출력 네임스페이스.
- `io/config.py`: UTF-8 안전 YAML 읽기, 중첩 중복 키 거부, task 검사 위임.
- `README.md`: 기능 지도와 후속 작업 경계.

의존 방향은 `io → contract → types`이며 io는 반환 타입을 직접 참조한다.
전체 예정 방향은 `run → client/io → score/data/contract → types`다.
types는 jeveval의 다른 패키지를 import하지 않는다.

모든 dataclass는 frozen이다. 내부 list/dict까지 불변인 것은 아니다.
from_dict는 중첩 타입을 복원하고 별칭 없는 사본을 만든다.
알 수 없는 필드·필수 필드 누락·비선택 필드의 null·잘못된 타입·NaN/Infinity를 거부한다.
ThresholdFile은 by_tau 키와 값의 tau가 같은지도 검사한다.
그 밖의 상태·확률 등 도메인 검사는 후속 contract/score/run 작업의 책임이다.

load_taskspec은 TaskSpec을 반환하며 오류 목록은 TaskSpecError.errors에 담는다.
task yaml의 score 질문은 기존대로 오류 목록이며 NotImplementedError로 바꾸지 않는다.
per_item_questions의 충돌 검사는 k 상한 없이 앞자리 0 없는 양의 정수를 대조한다.
실제 질문 펼치기와 중복 재검사는 작업 ③의 data/expand에서 구현한다.

## 테스트

- `tests/conftest.py`: 격리 Python의 저장소 import 경로.
- `tests/types/samples.py`: 자료형 테스트용 합성 표본.
- `tests/types/test_base.py`: 전체 자료형 왕복·frozen·null·알 수 없는 필드.
- `tests/types/test_specs.py`: 설정·항목·분할·중첩 질문·사본 분리.
- `tests/types/test_results.py`: 응답·길이·렌더 자료형과 숫자 경계.
- `tests/types/test_scores.py`: 임계값·모집단·질문 통계 중첩 복원.
- `tests/types/test_records.py`: session_id·호출별 길이·ParsedAnswer 복원.
- `tests/types/test_outcomes.py`: MISSING·실행 오류 요청 결과 왕복.
- `tests/contract/test_taskspec.py`: 정적/동적 질문·target_key·ID 패턴 경계.
- `tests/io/test_config.py`: 안전 YAML·중복 키·검사기 위임.
- `tests/fixtures/test_fixtures_wellformed.py`: JSON·README·CP·temperature·바이트·정확한 대상 prefix·canary 입력.
- `tests/fixtures/reference_scoring.py`: 테스트 전용 독립 F1·보정·임계값 참조 계산.
- `tests/fixtures/test_scoring_fixtures.py`: 빈 bin·빈 채점·빈 마스크·21묶음 분모·코호트·pooled 검산.
- `tests/fixtures/test_answer_fixtures.py`: API 확신·B1 교환 동률·누락 라벨·고정 칸 Brier.
- `tests/fixtures/test_record_fixtures.py`: 다섯 기록 사례·길이 상태·KorFin 연결·terminal 복구 기대값.
- `tests/fixtures/test_cost_fixtures.py`: 논리 완료 지연·백분위·세션 제외·토큰·파생 비용.
- `tests/fixtures/test_seal_fixtures.py`: 바이트 해시·개발 임계값 재계산·mtime·resume 교체 거부.
- `tests/fixtures/test_split_fixtures.py`: ID 묶음·라벨 충돌·연결요소·분할·비례 할당.
- `tests/fixtures/test_resume_fixtures.py`: JSONL 손상·중복·완료 ID·누적 재시도 자료.

fixture 폴더: render, responses, answers, scoring, splits, expand, records,
resume, length, seal, temperature, b1, canary. 각 README는 한 줄이다.
fixture 검산은 실제 실행 모듈 통합 테스트를 대신하지 않는다.
canary는 표식 있는 입력만 만들며, 일곱 커밋 출력의 누출 검사는 작업 ⑥에서 한다.

검사: `../foundation_model_test_non_thinking/.venv/bin/python -I -m pytest -q tests`

## SPEC_AMBIGUOUS

②-0 범위에 남은 항목 없음. 판 2의 자료형 미정 6건은 판 3으로 해결했다.
§10의 서버 인코더·문자→토큰 변환·길이 거부 응답 확인은 P0 후속 작업이다.
현재 길이 fixture는 이미 측정된 합성 LengthInfo를 입력으로 삼는다.
