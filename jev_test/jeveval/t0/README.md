# T0 순수 층 — 작업 ⑦a, P1_CONTRACT.md §8-7

이 디렉터리는 순수 계산만 담당한다. 실제 요청 확정·참조/서버 호출·CLI는 아래 ⑦b 층이다.
본시험 request/response의 score 거부는 그대로 유지한다.

- `request.py`: contract/render 사용, T0 세 종류 요청과 model 별칭, 봉투 바이트·동일성 해시.
- `response.py`: noul/choice 공개 검증기를 질문별 재사용, score 및 요청 전체 오류 우선순위.
- `distribution.py`: 순서 고정 분포 벡터·수치 도메인.
- `status.py`: 질문/사례 상태 합성 — FAIL > INCOMPLETE > PASS, 참조 없으면 PARTIAL (distribution 에서 분리, 10-17).
- `compare.py`: 분포와 별도 답 정책, 요청 검증 실패 시 모든 질문을 실패로 기록.
- `tolerance.py`: T0Policy(configs/t0/tolerance_v1.yaml) 의 반복/배치 변형 완전성·대상 동일성·질문별 변동과 허용폭 (코드 상수 없음).
- `../types/t0_io.py` T0Policy · `../contract/t0_policy.py` 검사 · `../io/t0_policy.py` 읽기(파일 해시 포함): 규칙 파일은 inputs 헤더·fingerprint·variants·tolerance 의 `tolerance_policy_sha256` 으로 단계가 묶이고, reference 뒤 바꾸면 tolerance/judge 가 거부한다.
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

반복 번호는 0..repeats-1 (configs/t0/tolerance_v1.yaml, 기본 5). Clef/Flash/v1 배치는 1·4·8, v1.1 대상 위치는
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

## 단계 실행 (⑦b)

의존 방향은 run → client/io/reference → t0/data → types다. 파일 입출력은 io,
HTTP는 client, 모델 로딩·호출은 reference 경계에만 둔다.

- `../types/t0_io.py`: 확정 입력 묶음·공개 원본 묶음·참조 런타임 dataclass.
- `../data/t0_fixture.py`: 풀 밖 행의 seed 순위·원문 선택·합성 케이스/대상 배치 구성.
- `../io/t0_sources.py`: 공개 5개 셋만 읽고 grouping/분할 groups를 복원.
- `../io/t0_files.py`: 질문/선택지 삽입 순서를 보존하는 원자 JSONL·fixture 쓰기.
- `../io/t0_inputs.py`: 풀 밖 재검사·원문 해시 대조·입력 확정/해시 검증·경계 주입.
- `../io/t0_fingerprint.py`: 코드·실제 로드 모듈·패키지·dtype·장치·checkpoint 파일 해시.
- `../io/t0_chain.py`: 관측·변형·fingerprint의 inputs/요청/참조 파일 연결 검사.
- `../reference/t0_runner.py`: 세 로컬 로더와 공개 응답 어댑터 조립.
- `../reference/variants.py`: Clef/v1 하위 배치 조합과 v1.1 대상 질문 배치.
- `samples.py`: 대상 질문 동일성 해시와 관측 봉투.
- `rounding.py`: 실행 인자의 경로별 반올림 자리수/반단위.
- `../run/make_t0_fixture.py`: 공개 fixture 생성 CLI, 원문은 결과 파일에 쓰지 않음.
- `../run/t0_measure.py`: 본시험 인코더(Measurer)를 T0 의 measurer(request)·boundary_builder(base, target) 로 감싸는 어댑터 — 채움 문자를 두 배씩·이분 탐색으로 붙여 정확히 target 길이의 경계 요청을 만든다; cmd_t0 inputs 가 모델 yaml 의 encoder.rule 로 자동 연결.
- `../run/t0_reference.py`: 공개 참조·모델 전체 batch_1 동일성·5회 변형 실행.
- `../run/t0_server.py`: concurrency 1·재시도 없는 서버 관측·전체 길이 상태.
- `../run/t0_evaluate.py`: 허용폭과 최종 판정 순수 함수 조립·공개 결과 기록.
- `../run/cmd_t0.py`: t0 하위 명령 인자와 단계 연결, 시험/P0 주입 seam.
- `../client/systemone.py`: send_t0로 확정된 봉투 바이트 그대로 전송.

```sh
python -m jeveval.run.make_t0_fixture
python -m jeveval.run.cli t0 inputs --model configs/models/clef.yaml --run-id t0_1
python -m jeveval.run.cli t0 reference --run-dir results/_t0/clef/t0_1 --checkpoint checkpoints/clef --device cuda
python -m jeveval.run.cli t0 tolerance --run-dir results/_t0/clef/t0_1 --rounding reference=4
python -m jeveval.run.cli t0 server --run-dir results/_t0/clef/t0_1 --base-url http://127.0.0.1:8000
python -m jeveval.run.cli t0 judge --run-dir results/_t0/clef/t0_1 --rounding reference=4,server=4
```

명령의 모델 YAML은 served_name·인증 환경변수·길이 제한을 P0에서 채운 사본을 쓴다.
기존 미확정 YAML을 자동으로 바꾸지 않는다. 반올림 4는 예시이며 확인한 자리수를 넣는다.
참조 별칭이 필요하면 inputs에 `--reference-name jev-latest`를 지정한다.
inputs는 기존 파일을 덮어쓰지 않는다. 새 입력은 새 run-id로 만든다.
서버 단계는 YAML의 auth_env를 Bearer 머리글로 쓰고 그 값은 기록하지 않는다.

inputs·reference·tolerance는 GPU 장비에서 준비한다. reference가 종료된 뒤 서버를 띄운다.
같은 장비에서 참조와 서빙을 동시에 실행하지 않는다(계획 §6). inputs.jsonl·reference.jsonl·
variants.jsonl·tolerance.json·fingerprint.json을 같은 run 경로로 옮기면 server와 judge는
Mac 등에서 실행할 수 있다. fixture나 원본을 다시 읽어 요청을 만들지 않는다.

원문 4파일(inputs/reference/server/variants JSONL)은 비공개이며 gitignore 대상이다.
t0.json·tolerance.json·fingerprint.json에는 원문/원응답/인증 값을 넣지 않는다.
fixture는 13개 정의(일반 12개+경계 규칙 1개), 확정 시 14개 요청이다.
7개 공개 참조는 5개 고유 행을 재사용하며 FunctionChat과 AI-Hub는 포함하지 않는다.
직렬화 합성 state는 json_string의 text 값으로 감싸 §2-2의 plain_text strip 규칙을
바꾸지 않고 내부 앞뒤 공백까지 보존한다. 공개 원문과 합성 state를 섞지 않는다.

P0는 `cmd_t0.run(stage="inputs", boundary_builder=..., measurer=...)`에 실제 인코더를 주입한다.
builder(base_request, target_total_tokens)는 T0Request와 잘리기 전 전체 길이를 반환한다.
measurer(request)는 전체 길이 목록을 반환한다(분리 모델은 질문별). 경계는 최대 길이가
L 또는 L+1이어야 한다. 빌더 없으면 lengths=null인 경계 요청으로 남아 INCOMPLETE다.
CLI에 시험용 길이 추정기를 노출하지 않는다. HTTP 200 길이 상태는 확정 시 길이와
run/length.classify로 구하며 usage.input_tokens를 쓰지 않는다.

반올림 미지정은 INCOMPLETE다. tolerance와 judge의 참조 반올림이 다르면 거부한다.
`--no-reference`만 참조 없는 PARTIAL을 허용하며 설치 실패의 우회 수단으로 쓰지 않는다.
C1은 real/NOT_RUN으로 기록한다. 실제 autojev temperature, 반올림, 경계 빌더,
served_name/별칭의 실모델 확인은 P0에 남는다. 가짜 모듈 시험을 실모델 증거로 쓰지 않는다.
