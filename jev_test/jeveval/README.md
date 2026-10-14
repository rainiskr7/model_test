# jeveval — P1 작업 ⑥b-2·보정 12 기능 지도

P1_CONTRACT.md 보정 12와 ⑥b-2 R1–R8 기준으로 compare·archive·참조 구현 호출 층까지 구현했다.
시험은 합성 fixture·tmp_path·가짜 참조 모듈·127.0.0.1 서버를 사용한다.

## 코드

- `__init__.py`: 패키지 네임스페이스.
- `types/__init__.py`: 기존 `from jeveval.types import X` 경로와 새 자료형 재수출.
- `types/base.py`: JsonRecord, JSON 사본·중첩 dataclass 복원·타입 검사.
- `types/specs.py`: SourceRow, BoundQuestion, Item, QuestionSpec, TaskSpec, SplitPlan, Groups, PoolResult.
- `types/results.py`: Rendered, ParsedAnswer, 호출별 LengthInfo.
- `types/scores.py`: Threshold, ThresholdFile, RiskCell, QStats, Population, Cost, ScoreTable.
- `types/records.py`: Request, 메모리 전용 AttemptResult, session_id를 포함한 AttemptRecord, CallRecord, FinalRecord.
- `types/outcomes.py`: 필수 roles를 포함한 메모리 전용 RequestOutcome, JSON 왕복 지원.
- `types/run.py`: ModelConfig·Decision·RunSummary JSON 왕복, bytes를 담는 메모리 전용 CallPlan.
- `contract/model_config.py`: 닫힌 모델 스키마·파일 해시·토큰 ID 검사, 실행 필수 값·B1 라벨 집합 대조.
- `io/models.py`: 중복 키 거부 YAML 로더와 ModelConfigError.errors.
- `io/hashes.py`: 스트리밍 SHA-256·SHA256SUMS 대조·정렬된 Python 소스 해시·토크나이저 재검증.
- `io/run_files.py`: 정규 JSON·fsync/원자 교체·파생 단계 final/빈 attempts/derived.json 기록과 재개.
- `types/contract.py`: Validated·B1Config·B1Call·B1Response의 frozen JsonRecord 자료형.
- `types/scoring.py`: AnswerParse·F1Result·CalibResult·SlotJudgement·메모리 전용 Observation 자료형.
- `contract/__init__.py`: 계약 검사 네임스페이스.
- `contract/taskspec.py`: target_key·state 키 중복·정적/동적 질문·성공 질문·ID 충돌 검사.
- `contract/render.py`: 설정 키 순서의 state 문자열과 대상 끝 문자 위치 계산.
- `contract/request.py`: 질문·선택지 순서 보존 요청, UTF-8 바이트·SHA-256·로컬 검증.
- `contract/response.py`: JSON 중복 키 거부, 전역 사유 우선순위·누적 경고·원 답 반환·독립 usage 추출.
- `contract/b1_response.py`: B1 로그확률 검증·독립 usage 추출·기록용 -inf 문자열 사본.
- `contract/b1_prompt.py`: 설정 기반 문구·매개변수, 정렬된 선택지의 라벨 배정.
- `score/labels.py`: 전체 라벨 이름 등록표, 33개 정답 규칙과 누락·타입 오류 거부.
- `score/answers.py`: systemone 원 확률 보존, B1 토큰 대조·softmax·동률·경고 처리.
- `score/f1.py`: 출현 클래스 macro-F1과 support·예측 수·tp·재현율·정밀도.
- `score/calibration.py`: 15 bin top-label ECE·one-hot Brier·clip log loss.
- `score/population.py`: 질문·pooled·셋별 ok 코호트 점수, 질문별 경고 재계산과 scores/1 조립.
- `score/compare.py`: C4 일치 검사, test/all_rows 공통 코호트와 compare/1 조립.
- `score/bootstrap.py`: 시험 대표 처리율·공통 ok F1의 묶음 paired bootstrap, 고정 임계값과 95% CI.
- `score/kosgd_slots.py`: 카탈로그 순서의 고정 정답 칸·중복·묶음 정답·순서 진단.
- `score/tasks.py`: 호출별 답 병합·역할 보존, 성공 질문 전체 확신·정답 마스크·KoSGD 묶음 오류·최대 길이.
- `score/threshold.py`: 정확한 위험 경계·동점 묶음 임계값, dev 대표 완료 대조·ThresholdFile 조립.
- `score/risk.py`: 단측 CP 상한·정확한 n_min·b_flip·봉인 임계값 적용·RiskCell과 risk/1 JSON 조립.
- `score/risk_mix.py`: 성공 질문 정답 클래스·서비스·층·질문 수 분포, 다섯 길이 칸과 수락 내 진단 오류.
- `score/cost.py`: 단계별 논리 완료 지연·실패·호출·재시도·입력 토큰 하한·파생 비용 0.
- `io/__init__.py`: 파일 입출력 네임스페이스.
- `io/records.py`: JSONL 추가·flush/fsync·타입/호출 연속성 검사·끝 줄 복구·없는 기록 파일 생성.
- `client/__init__.py`: 단일 시도 전송 네임스페이스.
- `client/http.py`: proxy·리디렉트 없는 urllib POST, 소켓 timeout·부분 본문·HTTP 오류 응답 보존.
- `client/systemone.py`: request_bytes 그대로 전송하고 SHA-256 반환.
- `client/vllm_chat.py`: 라벨 순서 토큰 제한·params 보존·chat 바이트와 SHA-256·단일 전송.
- `client/attempt.py`: executor가 준 식별자·terminal과 AttemptResult를 독립 AttemptRecord로 변환.
- `io/config.py`: UTF-8 안전 YAML 읽기, 중첩 중복 키 거부, task 검사 위임.
- `io/tasks.py`: JSON 중복 키 거부 목록 읽기와 B1 네 필드·사용자 문구 틀 검사.
- `io/sources/__init__.py`: 셋별 reader 공통 선택과 KOTE 투표 설정 전달.
- `io/sources/kosgd.py`: USER 위치·frames·대상까지 dialogue·services와 감사 선정 읽기.
- `io/sources/functionchat.py`: serial_num·메시지·중첩 도구를 보존하는 JSONL 읽기.
- `io/sources/kmhas.py`: 물리 행 ID·Python label 보존, 메타데이터 label_names 변환·범위 검사.
- `io/sources/kote.py`: 보정 7의 raw 투표 검증·평가자별 중복 제거·votes/labels_majority 생성, 원본 labels 보존 및 메타데이터 이름 읽기.
- `io/sources/korfin.py`: 원본 순서의 SID별 aspect 행 읽기.
- `io/sources/klue_mrc.py`: is_impossible 양·음성 전체 행과 guid·source 읽기.
- `data/expand.py`: 정적·항목별 질문 확장, 값의 중괄호 보존·ID 재검사·정답 소속 검사.
- `data/items/common.py`: 분할 의미·묶음 대조, 단계별 조립·사본·라벨 충돌·원문 없는 요약.
- `data/items/kosgd.py`: 두 판의 대화·카탈로그·정답·직전 USER 기준선.
- `data/items/functionchat.py`: 시스템 문장 정규화·단일 도구 선택지 출처·대표/extra.
- `data/items/kmhas.py`: 대표 문장·이름 라벨·묶음 라벨 충돌.
- `data/items/kote.py`: 과반수 라벨·동결 감정 강등·묶음 라벨 충돌.
- `data/items/korfin.py`: SRC별 원본 SID 순서의 aspect 질문·정답·미포함 flag.
- `data/items/klue_mrc.py`: context/question·답변 가능성·source 층.
- `data/grouping.py`: 정확 일치·union-find 묶음, ID·source 검사, 원본 행 연결과 항목 구성원.
- `data/pool.py`: 고정 선정 검증, 전체·단순 cap·최대 나머지 비례 할당과 층별 추출.
- `data/split.py`: 대표·dev/test·extra, 풀 대표 기준 KOTE 강등, 전체/풀 라벨 충돌·행 통계 및 분할 의미 검사.
- `io/splits.py`: 보정 6의 정렬된 UTF-8 JSON 바이트와 SplitPlan 왕복, 감정 이름 외 한글 거부.
- `run/make_splits.py`: 원본·순수 계산·쓰기 조립과 셋별 한 줄 요약, expect_groups 불일치 종료.
- `run/item_summary.py`: task 선택·입출력 연결, 단계별 원문 없는 JSONL 요약.
- `run/plan_calls.py`: 공통 항목 검증·고유 B1 호출 ID·렌더 실패를 포함한 로컬 오류 계획·전송 바이트.
- `run/length.py`: 호출별 잘림·문자 끝→토큰 끝·길이 구간, P0 측정 구현용 Measurer Protocol.
- `run/encoders/__init__.py`: ENCODERS 등록표·measurer_for, 미확정·미등록 규칙 거부.
- `run/encoders/hf_chat_template.py`: 파일 해시 대조·오프라인 no-think 템플릿·ID 재인코딩 일치·state offsets 기반 LengthInfo.
- `run/policy.py`: MAX_ATTEMPTS=5·전송 오류 우선·정수 Retry-After·누적 번호에 따른 Decision.
- `run/outcome.py`: 기록 연결·예산·길이 필수 검사, 독립 usage·답 변환·거부 우선·논리 상태 합성.
- `run/resume_check.py`: 전체 계획·attempts·final ID·누적 예산을 첫 전송/쓰기 전에 대조하는 순수 검사.
- `run/executor.py`: 주입 post/measurer/sleep으로 순차 실행·재시도·복구·attempts 뒤 final 기록·RunSummary.
- `run/derive.py`: 전체판 Item의 질문 ID 대조·행동 질문/호출 거르기·오류 상태와 관측값을 보존하는 독립 사본.
- `run/fingerprint.py`: 원본/토크나이저 검증·설정/규칙/코드 해시 수집·started_at 제외 비교.
- `run/stage_inputs.py`: 동결 설정과 검증된 원본에서 단계별 Item 복원·해당 단계 final과 경고 읽기.
- `run/gate.py`: 모든 검사 뒤 fingerprint 쓰기·현재 단계 tail 복구·첫 시험 봉인; 호출은 보내지 않는다.
- `run/seal.py`: threshold/dev final 바이트 해시 봉인·덮어쓰기 거부·resume 해시 대조 (certify는 ⑥b).
- `io/run_inputs.py`: fingerprint 재생성·단계 완료·identity와 compare/archive 공통 봉인 검사.
- `io/archive.py`: 전체 run 폴더/보존 입력 열거·결정적 tar.zst·sha/이름/길이 검증.
- `io/reference.py`: 로컬 체크포인트·오프라인 환경·참조 소스의 읽기 전용 import.
- `score/observations.py`: 성공 질문의 F1 관측·KoSGD 고정 칸·KorFin pooled 관측.
- `run/cli.py`: run·threshold·score·certify·compare·archive 인자와 원문 없는 오류 출력.
- `run/cmd_run.py`, `cmd_threshold.py`, `cmd_score.py`, `cmd_certify.py`: 실행/채점/인증 조립.
- `run/cmd_compare.py`: C4 검사·전체 시험 처리율·공통 성공 F1·T0 상태 출력 조립.
- `run/cmd_archive.py`: run_id 전체 완료 확인·한 번의 보존·모델별 archive.json 쓰기.
- `run/layout.py`, `summary.py`: 결과 경로 제한·주 지표 RiskCell의 evalcommon summary.
- `reference/__init__.py`: 무거운 의존성을 로드하지 않는 네임스페이스.
- `reference/clef_runner.py`: Clef/Flash 로컬 로딩·전체 systemone 요청 위임.
- `reference/pplx_runner.py`: v1 질문별 Decider.predict·v1.1 서버 predict 위임.
- `reference/README.md`: API의 file:line 근거·temperature seam·P0 경계.
- `README.md`, `NOTES.md`: 기능 지도·명령·세부 규칙과 이전 결정.

의존 방향은 `run → io/data → score/types`, `io → contract → types`, `score → types`다. 전체 예정 방향은 `run → client/io → score/data/contract → types`다.
data/items는 io·contract·run을 import하지 않는다. expand·items·labels는 파일·난수를 사용하지 않는다. types는 jeveval의 다른 패키지를 import하지 않는다.
contract·score는 서로 import하지 않으며 파일·네트워크·시계에 접근하지 않는다. score/bootstrap의 난수는 지역 random.Random(f"{seed}:boot:{set_name}")만 쓴다. data도 파일·네트워크·시계에 접근하지 않고, 난수는 계약의 문자열 seed로 만든 random.Random만 쓴다.
run/encoders의 의존은 types·io.hashes·run.length·표준 라이브러리·transformers/tokenizers로 제한한다. 로드는 HF_HUB_OFFLINE=1·TRANSFORMERS_OFFLINE=1, local_files_only=True·trust_remote_code=False다.

세부 규칙·기존 시험 지도·이전 구현 결정은 [NOTES.md](NOTES.md)에 보존한다.

## 실행 명령

저장소 루트 `jev_test/`에서 동결한 task·분할·입력·모델 설정을 사용한다. 다음은
설정과 서버 준비가 끝난 뒤의 순서다. `--base-url`은 메모리에서만 덮어쓰며 YAML을 바꾸지 않는다.
직접 실행은 모델 설정의 `auth_env`가 지정한 환경 변수에 인증 토큰이 있어야 한다.
토큰은 `Authorization: Bearer` 헤더에만 사용하고 출력·fingerprint에 기록하지 않는다.

```sh
python -m jeveval.run.cli run --model configs/models/b1_qwen3_8_27b.yaml --task configs/tasks/kmhas.yaml --stage dev --run-id r1 --base-url http://127.0.0.1:8000 --check-config
python -m jeveval.run.cli run --model configs/models/b1_qwen3_8_27b.yaml --task configs/tasks/kmhas.yaml --stage dev --run-id r1 --base-url http://127.0.0.1:8000
python -m jeveval.run.cli threshold --run-dir results/b1_qwen3_8_27b/r1/A/kmhas/default
python -m jeveval.run.cli run --model configs/models/b1_qwen3_8_27b.yaml --task configs/tasks/kmhas.yaml --stage test --run-id r1 --base-url http://127.0.0.1:8000
python -m jeveval.run.cli score --run-dir results/b1_qwen3_8_27b/r1/A/kmhas/default
python -m jeveval.run.cli certify --run-dir results/b1_qwen3_8_27b/r1/A/kmhas/default
```

FunctionChat은 test 뒤 `run --stage extra`까지 완료한 뒤 score한다. test는 인증 모집단,
dev+test+extra는 `all_rows` 기술 통계다. score는 봉인 존재·해시 및 각 단계의 정확한 완료
ID 집합을 먼저 검사한다. threshold는 dev 기록만 열고, 시험 봉인 후에는 재작성하지 않는다.

`--check-config`는 설정·task·분할 구조와 실행 누락 목록만 검사한다. 원본 데이터 로드,
길이 측정, 인증 확인, 전송, 결과 쓰기는 하지 않는다. 일반 명령은 JSON 한 줄과 종료값
0(성공)/1(실패)을 반환하며 예외 원문을 출력하지 않는다.

fingerprint는 명시적 `inputs` 경로와 `configs/datasets.yaml` 해시를 포함한다.
threshold·score·certify는 저장된 입력으로 fingerprint를 다시 만들고, `started_at`을
제외한 값이 모두 같아야 진행한다. 이전 형식의 inputs 없는 fingerprint는 거부한다.
인증은 dev 완료 확인·Item 복원 후 기존 threshold 함수로 세 tau를 재계산한다.
dev 바이트/threshold 재계산/threshold–seal–risk 해시를 각각 a/b/c로 출력하며,
threshold mtime이 봉인 시각보다 늦은 것은 경고다. 개발 실행을 반복해 고르는 일은
이 검사로 막지 못한다. attempts와 fingerprint 보존은 archive 명령의 책임이다.

KoSGD separate 모델은 `kosgd_full.yaml`의 같은 단계 완료 후
`kosgd_actions_only.yaml`로 run한다. 두 판의 공통 fingerprint 입력을 비교하고,
파생 판도 dev → 자기 threshold → test 봉인 → score → certify 순서를 거친다.
파생에는 인증·측정·전송이 없으며 출처는 저장소 상대 full 경로로 단계별 derived.json에
남긴다. 파생 재개는 동일 final 접두부만 허용하고, 비용은 전부 0(p50/p95 null)이다.

summary는 동결 datasets 설정의 주 지표 판, risk.cells["0.02"]에서만 만든다.
NO_THRESHOLD/UNDERPOWERED 또는 분모 0의 score는 0이고, t0_status도 함께 기록한다.
비주 지표 판에 기존 summary가 있으면 자동 삭제하지 않고 거부한다.
score는 risk·scores·summary를 모두 계산·직렬화한 뒤 파일별로 원자 교체한다.
같은 입력의 재실행은 같은 바이트다. 여러 파일 전체의 트랜잭션이나 디스크 장애 시
롤백은 제공하지 않으므로 저장 도중 장애가 나면 같은 명령을 다시 실행한다.

canary는 합성 원본·가짜 Measurer·주입 post로 실제 CLI 전체 순서를 실행한다.
systemone의 실제 인코더는 P0 후속이며 시험용 주입은 CLI 옵션으로 노출하지 않는다.
seal fixture 여섯 경우는 실제 certify 경로를 통과하고, fixture의 synthetic 셋은
시험에서 Item 로더만 주입한다.

## 비교·보존 (⑥b-2)

```sh
python -m jeveval.run.cli compare --run-dirs results/model1/r1/A/kmhas/default results/model2/r1/A/kmhas/default --compare-id c1
python -m jeveval.run.cli archive --run-id r1 --results results --archive-root archive
```

compare는 모든 run의 fingerprint·dev/test(FC는 extra) 완료·threshold identity·봉인을
검사하고 같은 set/variant·분할/task 해시·시험 ID 집합을 요구한다. 모델 ID 중복은 거부한다.
`common_cohort`는 시험 성공 교집합의 비인증 Population이다. `bootstrap.coverage["0.02"]`는
실패도 분모에 남긴 시험 전체와 각 모델의 고정 t*를 사용한다. `bootstrap.f1.test`는
성공 질문별 공통 ok F1이며 FC 도구 질문은 제외한다. FC의 `f1.all_rows`는 dev/test/extra
공통 ok 행을 분할 group_id로 함께 재표집한다. KorFin은 pooled `aspect`도 제공한다.
`compare.json`은 `t0_status`와 `t0_not_passed`를 포함한다. 부트스트랩은 분할 seed로 2,000회다.

archive는 run_id 아래 모든 모델/셋/판의 완료와 threshold·seal·scores·risk를 요구한다.
어느 폴더에든 archive.json 또는 목적 tar가 있으면 다른 archive-root로도 재실행을 거부한다.
보존 목록은 각 fingerprint의 files, fingerprint.json, 각 단계의 attempts/final이다.
여기에는 모델/task/b1/list/split YAML·JSON, datasets.yaml, rules.yaml, SHA256SUMS가 포함된다.
PAX tar의 이름 정렬·mtime/uid/gid 0·uname/gname 빈 문자열·mode 0644를 고정한다.
archive.json의 archive는 저장소 상대 경로다. verify_archive는 추출 없이 sha·이름·길이를 대조한다.
I/O는 io에, 확률/점수 계산은 순수 score 함수에 둔다. 참조 로딩은 I/O 경계다.

⑥b-2 짝 테스트: tests/run/test_cmd_compare.py·test_cmd_archive.py,
tests/io/test_archive.py·test_reference.py, tests/score/test_observations.py·test_compare.py,
tests/reference/test_clef_runner.py·test_pplx_runner.py. 합성 실행은 기존 cli_support 흐름을 재사용한다.
누출 양성 대조는 가짜 서버가 state를 되돌려 주어 state/묶음 원문 표식이 attempts와 실제
archive tar 안에 있음을 확인한다. fingerprint·threshold·seal·scores·risk·summary·compare·
archive.json에는 이 표식과 인증 키가 없어야 한다. 정답 원문 표식은 Item 변환에서 사라지므로
누출 검사 대상으로 삼지 않는다. 실제 autojev 고정 logit 경로와 T0는 P0에 남는다.

REBUTTAL: R1–R8 반영. 이번 작업의 SPEC_AMBIGUOUS / FIXTURE_CONFLICT 없음.
검사: `../foundation_model_test_non_thinking/.venv/bin/python -I -m pytest -q -p no:cacheprovider -rs tests`

## T0 단계 실행 (⑦a·⑦b, 보정 13)

`t0/`는 세 종류 요청·응답 검증·질문별 허용폭·분포/답/경계 판정·원문 없는 기록을 담당한다.
파일별 지도와 dataclass 인터페이스·고정 배치 목록은 [t0/README.md](t0/README.md)에 있다.
`io/t0.py`·`t0/gate.py`는 passed 기록을 run의 첫 쓰기 전에 확인한다. YAML은 사람이 동결한다.
`io/environment.py`는 fingerprint의 external/env를 수집하며 archive는 `_external/`로 보존한다.
⑦b의 파일별 지도·CLI 실행 순서·서버 점유·P0 잔여 항목은 [t0/README.md](t0/README.md#단계-실행-⑦b)에 있다.
GPU 장비에서 inputs → reference → tolerance, 참조 종료 후 어디서나 server → judge를 실행한다.
계획 §6에 따라 같은 장비에서 참조와 서빙을 동시에 실행하지 않는다.
