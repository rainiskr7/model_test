# jeveval — P1 작업 ③a 기능 지도

P1_CONTRACT.md 판 3 보정 6까지의 요청·응답·기초 채점과 원본 읽기·묶음·평가 풀·분할을 구현했다.
테스트는 합성 fixture와 tmp_path만 사용한다. 항목·질문 펼치기·정답·client·실행기는 후속 작업이다.

## 코드

- `__init__.py`: 패키지 네임스페이스.
- `types/__init__.py`: 기존 `from jeveval.types import X` 경로와 새 자료형 재수출.
- `types/base.py`: JsonRecord, JSON 사본·중첩 dataclass 복원·타입 검사.
- `types/specs.py`: SourceRow, BoundQuestion, Item, QuestionSpec, TaskSpec, SplitPlan, Groups, PoolResult.
- `types/results.py`: Rendered, ParsedAnswer, 호출별 LengthInfo.
- `types/scores.py`: Threshold, ThresholdFile, RiskCell, QStats, Population, Cost, ScoreTable.
- `types/records.py`: Request, session_id를 포함한 AttemptRecord, CallRecord, FinalRecord.
- `types/outcomes.py`: 메모리 전용 RequestOutcome, 테스트용 JSON 왕복 지원.
- `types/contract.py`: Validated·B1Config·B1Call의 frozen JsonRecord 자료형.
- `types/scoring.py`: AnswerParse·F1Result·CalibResult·SlotJudgement 자료형.
- `contract/__init__.py`: 계약 검사 네임스페이스.
- `contract/taskspec.py`: target_key·state 키 중복·정적/동적 질문·성공 질문·ID 충돌 검사.
- `contract/render.py`: 설정 키 순서의 state 문자열과 대상 끝 문자 위치 계산.
- `contract/request.py`: 질문·선택지 순서 보존 요청, UTF-8 바이트·SHA-256·로컬 검증.
- `contract/response.py`: JSON 중복 키 거부, 전역 사유 우선순위·누적 경고·원 답 반환.
- `contract/b1_prompt.py`: 설정 기반 문구·매개변수, 정렬된 선택지의 라벨 배정.
- `score/answers.py`: systemone 원 확률 보존, B1 토큰 대조·softmax·동률·경고 처리.
- `score/f1.py`: 출현 클래스 macro-F1과 support·예측 수·tp·재현율·정밀도.
- `score/calibration.py`: 15 bin top-label ECE·one-hot Brier·clip log loss.
- `score/kosgd_slots.py`: 카탈로그 순서의 고정 정답 칸·중복·묶음 정답·순서 진단.
- `io/__init__.py`: 파일 입출력 네임스페이스.
- `io/config.py`: UTF-8 안전 YAML 읽기, 중첩 중복 키 거부, task 검사 위임.
- `io/sources/kosgd.py`: USER 턴의 전체 위치·frames 읽기와 감사 selected_turns 읽기.
- `io/sources/functionchat.py`: serial_num·메시지·중첩 도구를 보존하는 JSONL 읽기.
- `io/sources/kmhas.py`: 물리 행 ID와 Python label 목록을 갖는 parquet 읽기.
- `io/sources/kote.py`: 보정 7의 raw 투표 검증·평가자별 중복 제거·votes/labels_majority 생성, 원본 labels 보존 및 메타데이터 이름 읽기.
- `io/sources/korfin.py`: 원본 순서의 SID별 aspect 행 읽기.
- `io/sources/klue_mrc.py`: is_impossible 양·음성 전체 행과 guid·source 읽기.
- `data/grouping.py`: 정확 일치·union-find 묶음, ID·source 검사, 원본 행 연결과 항목 구성원.
- `data/pool.py`: 고정 선정 검증, 전체·단순 cap·최대 나머지 비례 할당과 층별 추출.
- `data/split.py`: 대표·dev/test·extra, 풀 대표 기준 KOTE 강등, 전체/풀 라벨 충돌·행 통계.
- `io/splits.py`: 보정 6의 정렬된 UTF-8 JSON 바이트와 SplitPlan 왕복, 감정 이름 외 한글 거부.
- `run/make_splits.py`: 원본·순수 계산·쓰기 조립과 셋별 한 줄 요약, expect_groups 불일치 종료.
- `README.md`: 기능 지도와 후속 작업 경계.

의존 방향은 `run → io/data → types`, `io → contract → types`, `score → types`다.
전체 예정 방향은 `run → client/io → score/data/contract → types`다.
types는 jeveval의 다른 패키지를 import하지 않는다.
contract·score는 서로 import하지 않으며 파일·네트워크·시계·난수 접근이 없는 순수 함수다.
data도 파일·네트워크·시계에 접근하지 않고, 난수는 계약의 문자열 seed로 만든 random.Random만 쓴다.

모든 dataclass는 frozen이다. 내부 list/dict까지 불변인 것은 아니다.
from_dict는 중첩 타입을 복원하고 별칭 없는 사본을 만든다.
알 수 없는 필드·필수 필드 누락·비선택 필드의 null·잘못된 타입·NaN/Infinity를 거부한다.
ThresholdFile은 by_tau 키와 값의 tau가 같은지도 검사한다.
요청·응답·채점 도메인 검사는 각 contract/score 함수, 실행 상태 결합은 후속 run의 책임이다.

load_taskspec은 TaskSpec을 반환하며 오류 목록은 TaskSpecError.errors에 담는다.
task yaml의 score 질문은 기존대로 오류 목록이며 NotImplementedError로 바꾸지 않는다.
per_item_questions의 충돌 검사는 k 상한 없이 앞자리 0 없는 양의 정수를 대조한다.
실제 질문 펼치기와 중복 재검사는 작업 ③의 data/expand에서 구현한다.
Request가 봉투 구조를 보장하고 build_request가 질문 ID 중복을 거부한다.
systemone criteria는 options 순서를 보존하며 B1만 코드포인트 순서로 라벨을 배정한다.
usage 없음/null은 usage_input_tokens_invalid 경고를 내지 않는다. 추가 봉투 키 경고는 별도다.
응답 검증 실패 시 answers는 None이며, 그때까지 수집한 경고는 중복 없이 보존한다.
B1 allowed_token_ids는 후속 client가 채운다. calibrate의 모집단 구성은 호출자 책임이다.

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
- `tests/contract/test_render.py`: 기존 render fixture의 state·위치·요청 바이트·해시 통합 검증.
- `tests/contract/test_request.py`: ID·타입·선택지 개수·casefold·중복·순서·사본 분리.
- `tests/contract/test_response.py`: 모든 기존 응답의 str/bytes 검증·사유 우선순위·usage 경고.
- `tests/contract/test_b1_prompt.py`: 기존 라벨 대응·새 prompt fixture·설정 사본·라벨 수 제한.
- `tests/score/test_answers.py`: 기존 답/B1 fixture·strip·중복·동률·프롬프트/검증기 연결.
- `tests/score/test_f1.py`: 기존 F1 fixture·출현 클래스 순서·길이 불일치.
- `tests/score/test_calibration.py`: 기존 보정 fixture·bin 경계·서로 다른 선택지·답 파서 연결.
- `tests/score/test_kosgd_slots.py`: 기존 칸 fixture·copy_prev 별도 판정·칸별/평균 Brier 반례.
- `tests/io/test_config.py`: 안전 YAML·중복 키·검사기 위임.
- `tests/io/test_sources_kosgd.py`: USER 위치·원문 제외·파일 순서·선정 읽기·중복 대화 거부.
- `tests/io/test_sources_functionchat.py`: system 선행·중첩 도구·첫 USER 기준의 전이 연결.
- `tests/io/test_sources_kmhas.py`: 물리 행 번호와 Python 라벨 목록.
- `tests/io/test_sources_kote.py`: info 메타데이터 경로와 메타데이터 누락 거부.
- `tests/io/test_sources_korfin.py`: SID 행 순서 보존과 SRC별 단일 항목.
- `tests/io/test_sources_klue_mrc.py`: 답변 불가능 행을 포함한 guid·중첩 answers 보존.
- `tests/data/test_grouping.py`: 기존 union-find·충돌 fixture, 숫자 최소·문자열 정렬·ID/source 거부.
- `tests/data/test_pool.py`: 기존 추출·비례 fixture, 동률·cap·빈 모집단·잘못된 고정 선정.
- `tests/data/test_split.py`: 기존 중간 shuffle·최종 정렬, 풀 대표 강등·충돌·extra·KorFin 행 수.
- `tests/io/test_splits.py`: 고정 바이트·왕복·입력 순서 불변·한글 감정 강등과 원문 제외.
- `tests/run/test_make_splits.py`: 여섯 합성 셋 CLI 두 번의 바이트 일치·단일 셋·expect_groups 실패.
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
작업 ② 짝 테스트는 기존 fixture를 실제 함수에 통과시키며 기존 기대값은 변경하지 않는다.
추가 fixture `tests/fixtures/b1/prompt.json`은 합성 설정으로 choice/noul 문구·매개변수를 고정한다.
canary는 표식 있는 입력만 만들며, 일곱 커밋 출력의 누출 검사는 작업 ⑥에서 한다.

검사: `../foundation_model_test_non_thinking/.venv/bin/python -I -m pytest -q -p no:cacheprovider tests`

실제 데이터 미리보기 (저장소 루트에서, `-I` 경로 처리는 실행 명령에만 둔다):

```sh
../foundation_model_test_non_thinking/.venv/bin/python -I -c 'import runpy, sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); runpy.run_module("jeveval.run.make_splits", run_name="__main__")' --rules configs/splits/rules.yaml --root . --set all --out .work/splits_preview
```

분할 파일에는 평가 풀 묶음만 담는다. KOTE 강등 이름만 한글을 허용하며 원문 묶음 키는 저장하지 않는다.
`pool_rule`은 YAML pool 객체 그대로, 바이트는 `ensure_ascii=False, indent=1, sort_keys=True`와 끝 LF다.
`Groups`·`PoolResult`는 frozen JsonRecord이며, strata 입력은 group_id→층 이름이다.
KoSGD 고정 선정은 원본 USER 구성원 존재 여부로 검증한다 (없는 대화·중복·SYSTEM·범위 밖 거부).
CLI의 상대 `--rules`와 source/선정 경로는 `--root` 기준, 상대 `--out`은 실행 cwd 기준이다.

## SPEC_AMBIGUOUS

작업 ② 범위의 SPEC_AMBIGUOUS / FIXTURE_CONFLICT 없음. 반박 10건은 계약 판 3 보정 4 와 Claude(조율자) 판정으로 해결했다 (사용자 결정 아님).
작업 ③a의 반박 11건은 보정 6과 사용자 승인으로 해결했다. 남은 SPEC_AMBIGUOUS / FIXTURE_CONFLICT 없음.
승인된 fixture 변경: union_find.expected.groups의 구성원 11–15를 문자열로 변경;
label_conflicts.expected.notes의 옛 키를 label_conflict_groups_total/pool (각 1)로 대체.
deterministic.json은 변경하지 않았으며 중간 순서와 최종 정렬을 따로 검증한다.
§10의 서버 인코더·문자→토큰 변환·길이 거부 응답 확인은 P0 후속 작업이다.
현재 길이 fixture는 이미 측정된 합성 LengthInfo를 입력으로 삼는다.
