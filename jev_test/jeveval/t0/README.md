# T0 순수 층 — 작업 ⑦a, P1_CONTRACT.md §8-7

파일·네트워크·모델 접근은 없다. 실제 요청 확정·참조/서버 호출·CLI는 ⑦b다.
본시험 request/response의 score 거부는 그대로 유지한다.

- `request.py`: contract/render 사용, T0 세 종류 요청과 model 별칭, 봉투 바이트·동일성 해시.
- `response.py`: noul/choice 공개 검증기를 질문별 재사용, score 및 요청 전체 오류 우선순위.
- `distribution.py`: 순서 고정 분포 벡터·수치 도메인·상태 우선순위.
- `compare.py`: 분포와 별도 답 정책, 요청 검증 실패 시 모든 질문을 실패로 기록.
- `tolerance.py`: 고정 반복/배치 변형 완전성·대상 동일성·질문별 변동과 허용폭.
- `boundary.py`: 전체 입력 길이와 HTTP/길이 상태 판정; usage를 사용하지 않음.
- `judge.py`: 기대 케이스 분모·중복/누락·inputs/요청 해시 사슬·최종 상태와 변경 개수.
- `record.py`: t0 제외 설정 해시·원문 없는 t0/1·T0/C1 검출 범위 및 실제/가짜 증거.
- `gate.py`: passed 증거의 바이트 해시·PASS·설정 해시를 순수 검사.
- `../types/t0.py`: 요청·변형·허용폭·케이스·관측·판정의 dataclass 인터페이스.
- `../io/t0.py`: YAML 원본과 T0 기록 읽기, run의 쓰기/모델 로딩 전 검증.
- `../io/environment.py`: 설치 버전과 외부 코드 해시/경로 검사, archive 외부 이름 지원.

요청 봉투는 §2-1처럼 키 삽입 순서·UTF-8·compact JSON을 사용한다. 동일성 해시는
`state, questions, images` 순서이며 images 미지정과 빈 목록은 동일하다. 질문·선택지
순서를 정렬하지 않는다. model 별칭은 봉투 해시만 바꾼다. 설정 해시는 t0를 제외하고
재귀 키 정렬한 compact JSON이다. 각 출력은 입력 객체를 변경하지 않는다.

응답 검증은 전역 type → noul → choice 키/값/pick → score 키/값/legend/confidence/score
순서다. 파싱·봉투·질문 ID는 그보다 앞이다. score 오류도 bool·비유한값을 거부한다.
`epsilon_r=None`은 정상 응답에서도 unknown_rounding이며 확정 계약 위반보다 후순위다.
반올림 확률은 재정규화하지 않는다. 비교에는 검증된 Validated만 전달한다.

반복 번호는 0..4다. Clef/Flash/v1 배치는 1·4·8, v1.1 대상 위치는
1질문 위치0, 8질문 위치0/7, 17질문 위치0/7/8/15/16이다. 이 목록의 모든 반복과
질문별 동일 대상 해시가 필요하다. Clef/v1은 batch_one_equal=True 증거가 선행한다.
미측정과 측정값 0을 구분하며, 변동 >0.02면 tol_prob를 내지 않고 INCOMPLETE다.
⑦b는 실제 하위 경로와 공개 경로의 바이트 동일성을 확인한 뒤 이 값을 전달해야 한다.

judge는 각 출력 경로의 epsilon을 받아 별도로 검증한다. score 대조의 `2ε`에는
두 경로 반단위의 최댓값을 사용한다. 허용폭은 참조 경로 epsilon으로 계산한다.
뺄셈의 float 표현 오차는 상대 1e-12로만 보완하며 허용폭 0은 정확한 0만 허용한다.
score argmax는 반올림 확률의 첫 최대 수준이며 진단만이다.

CaseResult의 n_expected는 해당 요청 질문 전체, n_compared는 분포 대조 질문 수,
n_failed는 검증/실행 실패로 대조할 수 없는 질문 수다. 분포/답 위반은 questions의
FAIL로 기록한다. 경계 요청은 n_compared=0이며 성공한 경계는 n_failed=0이다.
Judgement의 n_changed/n_allowed/n_violated는 원시 답 변경 중 정책 판정별 개수다.
검증 실패 시 정상 질문을 부분 비교하지 않는다. 전체 분모는 경계까지 포함한
n_expected_cases/n_expected_questions로 남긴다. 해시/중복/낯선 ID는 ValueError,
누락은 INCOMPLETE다. FAIL > INCOMPLETE > PASS, 참조 없는 경우에만 PARTIAL이다.

T0Case는 서버용 T0Request와 허용된 참조용 봉투 해시를 가진다. T0Observation은
원응답과 세 해시를 포함하며 비공개 자료다. build_record에는 T0Judgement만 넘겨
원문을 남기지 않는다. C1 temperature status는 PASS/FAIL/INCOMPLETE/NOT_RUN,
path는 real/fake다. PASS/FAIL에는 evidence_sha256이 필수다.

사람이 T0 기록을 검토하고 모델 YAML의 t0 포인터를 갱신한 뒤 본시험을 시작한다.
run은 passed일 때만 증거를 강제하며 not_run/partial은 기존 표시 방식을 유지한다.
`--check-config`는 구조 검사만 한다. CLI base_url 재정의는 원본 YAML 지문에 영향을
주지 않는다. 첫 fingerprint 뒤 t0 포인터를 바꾸면 기존 동결 검사에서 거부된다.
외부 코드는 fingerprint.external, 패키지는 env에 기록하며 archive에서 외부 코드를
`_external/reranker_test/evalcommon/schema.py`로 보존한다. 저장소 내부 경로 검사와
외부 파일의 명시적 허용 목록을 별도로 적용한다.
