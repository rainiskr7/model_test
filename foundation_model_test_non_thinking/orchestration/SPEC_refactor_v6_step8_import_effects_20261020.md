# SPEC: 판 6 8단계 — import 부작용 2건 (2026-10-20)

> 상태: 완료(`0718b8b`) — FunctionChat identity 실행별 객체화([judge_pilot.py:79](../shared/functionchat/judge/judge_pilot.py#L79)); 외부 배치 adapter는 [CONVENTIONS §12 예외](../CONVENTIONS.md#L163)로 유지.

담당: A 계획·결정·검증·커밋, X 반박·구현. 공통 규칙은 판 6 §0 그대로. 규약: CONVENTIONS §12 마지막 항목 "모듈을 import 하는 것만으로 환경(os.environ)·전역 가변 상태가 바뀌면 안 된다. 키 로딩·dotenv·누적 상태는 main() 이 만든 객체에 둔다."

**이 단계는 "고친다" 가 정해진 단계가 아니다.** 대상마다 (가) 고치기 (나) 규약 예외로 남기고 이유 기록 중 하나를 근거로 고른다. 기존 시험이 import 시점 동작을 계약으로 고정하고 있으면 그 시험을 바꾸는 것 자체가 계약 변경이므로 (가) 를 고르려면 그 이득이 분명해야 한다.

## 대상 A — `shared/agent/gpustack_custom/openai_compat_adapter.py`
- import 시 `apply_serving_constraints = _load_serving_constraints()`(62행): `MODEL_TEST_BASE` 를 읽고, `shared/serving/constraints.py` 가 있으면 **`sys.path.insert(0, <base>/shared)`**, 실패·불일치 때 stderr 경고, 고른 함수를 모듈 전역에 묶는다.
- 이 파일은 Ko-AgentBench 에 **복사·배치되는 외부 코드**(§11 예외; `shared/agent/run_gpustack_custom.sh:50`, `run_gpustack_passk.sh:33`).
- 기존 시험 `shared/agent/tests/test_agent_runner_requests.py:355-369` 이 import 직후 `module.apply_serving_constraints is chosen.apply`, no-op 이면 `__name__ == '_noop'` 를 단언 — **import 시점 선택이 시험된 계약**.
- 질문: 지연 선택(첫 호출 때 선택·캐시)으로 바꾸면 운영 동작이 같은가(러너는 env 를 import 전에 정해 둔다)? sys.path 변경을 없앨 수 있는가(외부 배치에서 `serving.constraints` 를 찾는 유일한 방법인지)? 시험 계약을 바꿀 가치가 있는가?

## 대상 B — `shared/functionchat/judge/judge_pilot.py` 의 `SERVED_IDENTITY`
- 78행 모듈 전역 dict(빈 set 3개). 변경은 `record_served_identity`·`reset_served_identity`(재시도 시 이전 judge.json 기록 병합)·`served_identity_snapshot` 호출 때만. 사용: `run_judge.py:284,369`.
- 시험이 전역을 직접 다룸: `test_functionchat_scoring.py:474-476`(clear), `test_run_judge_requests.py:20`(monkeypatch).
- 질문: import 만으로 상태가 "바뀌는" 것은 아니다(빈 등록부 생성). §12 위반인가, 아니면 "명시적 reset 이 있는 프로세스 단위 등록부" 로 예외 기록이 맞는가? 객체화하면 judge.json 의 `served_identity` 병합 계약이 같게 유지되는가?

## 산출물(결정 뒤)
- (가) 를 고른 대상: 구현 + 기존 계약 시험을 새 계약으로 바꾸는 이유를 시험 주석·커밋에. 운영 동작 동일성 시험(러너 경로에서 고른 함수·요청 payload 가 전과 같음).
- (나) 를 고른 대상: CONVENTIONS §12 에 예외 표 행 추가(파일·이유·조건), 코드 주석.

## A 결정(10-20, X 권고 채택)
- **대상 A → (나) 규약 예외.** import 시 `MODEL_TEST_BASE/shared` 검색 경로 등록은 요청 변환뿐 아니라 러너 `_decoding_provenance()`(run_gpustack_benchmark_with_logging.py:235)의 `serving.constraints` import 도 받친다. 지연 선택은 경고 시점·메타데이터 경로까지 재검증이 필요하고 이득이 작다. 기존 시험 355-369 는 "import 직후" 가 아니라 "첫 호출 뒤" 동일성을 본다(명세 표현 정정).
  - 산출물: CONVENTIONS §12 예외 표(없으면 §12 끝에 표 신설)에 X 문안 그대로 한 행 — "`shared/agent/gpustack_custom/openai_compat_adapter.py`의 제약 로더 | 외부 Ko-AgentBench 배치의 제약 선택·경고 및 러너 decoding 메타데이터 import를 보존하기 위해 import 시 `MODEL_TEST_BASE/shared` 검색 경로 등록과 함수 선택을 허용한다. 부모 실행 환경에서 기준 경로를 확정하고 기존 no-op·경고·배치 import 계약을 유지한다." + 어댑터 62행 근처 주석. 코드 동작 무변경.
- **대상 B → (가) 실행별 객체.** §12 "누적 상태는 main() 이 만든 객체에 둔다" 위반. `judge_pilot.py` 에 등록부 클래스(예: `ServedIdentity` — record/reset(previous)/snapshot 같은 의미), `run_judge.main()` 이 입력을 읽은 뒤 하나 만들어 **이전 전체 identity 와 이번 응답의 합집합**을 유지(알 수 없는 필드 무시·`str()` 변환·중복 제거 그대로), 모든 반복·worker 의 `call_judge()` 에 같은 객체 전달, 응답 identity 는 지금처럼 판정 파싱·검증 **전에** 기록, worker 완료 뒤 snapshot(필드 순서 model→system_fingerprint→provider, 빈 필드 생략, 값 sorted), summary 삽입 위치·writer 옵션 무변경. `judge_pilot.main()` 호출부도 연결. 모듈 전역 `SERVED_IDENTITY` 와 무인자 helper 는 제거.
  - 기존 시험: `test_functionchat_scoring.py:471-476`·632 부근 병합 시험, `test_run_judge_requests.py:15-20` 은 **상태 주입 준비 코드만** 객체 인자로 바꾸고, 요청·병합·산출물 기대값과 캡처 기준선은 무변경. 다중 worker(concurrency>1)와 같은 프로세스에서 두 번 main 을 돌릴 때 기록이 섞이지 않음을 새 시험으로.

## 수용 조건 정정
- C8.1 → **B: `-k runner_requests`·`test_run_judge_requests.py` 의 요청·judge.json 캡처 기대값 무변경 통과**(상태 주입 준비 코드 변경은 허용). 출력 기준선 216 MATCH 는 functionchat `summary.json` 재채점이라 judge.json byte 근거가 아님 — 근거는 위 캡처 시험.
- C8.2 → A: 예외 표 행·주석이 어댑터 실제 행과 맞고, 어댑터 코드 diff 는 주석뿐.
- C8.4(신규) → B: concurrency 2 이상에서 모든 worker 응답 identity 가 하나의 snapshot 에 모임, 같은 프로세스 연속 두 실행 사이 누출 0.

## 수용 조건
- C8.1 (가) 대상: 요청 앵커 시험(`-k runner_requests`) 무수정 통과 + 판정 산출(judge.json `served_identity`) 동일 — functionchat 은 출력 기준선 216 MATCH 에 포함.
- C8.2 (나) 대상: CONVENTIONS 예외 표·주석이 실제 코드 행과 맞음.
- C8.3 전체: 셸 묶음·pytest 두 환경·기준선, 동결 0, gpustack_custom 은 외부 배치 계약(import 경로·파일 이름) 무변경.
