# SPEC: SKIP_BENCHES 이름 검사·정책 주석 — 트리 검토 6번 (2026-10-20)

> 상태: 채택 범위 완료(`3b5377e`) — run_all 재개용 skip 이름 검사·측정 제외 정책 주석 반영; 로더의 정책 허용값은 무변경.

담당: A 계획·검증·커밋, X 반박(read-only) → 구현(workspace-write). 범위 N 만(T 확인 필요는 보고만). 동결 `shared/harness/*`·`configs/tests/*`, 운영 results/data/logs 쓰기 금지.
근거: 10-20 A 분석 + X 반박(C1 SUPPORTED, C2·C3 PARTIAL). 사용자 결정(10-20): 아래 1~3 만. 완주 검사(기대 벤치 vs 결과 폴더)는 하지 않음.

## 1. yaml 허용 목록 유지 + 로더 주석 정정
- `configs/load_model_config.py:59-62` 주석: "run_all.sh 에 skip 훅이 있는 벤치" → **측정 제외 정책**: yaml·serving_profile 의 `skip_benches` 는 "이 모델에서 숫자가 의미 없는 벤치를 아예 재지 않는다"는 측정 정의이며 지금은 `b4_latency_profile` 만 허용. run_all.sh 의 나머지 훅(재개용)은 여기서 허용하지 않는다는 것과 이유(발행 strict 는 없는 벤치를 실패로 보지 않음 — test_publish_derive.py:209-222). 
- `SKIPPABLE_BENCHES` 값·오류 문구·동작 **무변경**(동결 시험 configs/tests/test_load_model_config.py 가 문구를 볼 수 있음).

## 2. run_all.sh 이름 검사
- 허용: `kreta k_dtcbench koffvqa mtvqa_kr k_mmbench b4_latency_profile`(지금 skip 훅이 달린 6종). 빈 값·공백만은 통과.
- 위치: **세션 파일 생성(`.eval_session` 쓰기, run_all.sh:18-27) 전**, MODEL 인자 확인 뒤. 모르는 이름이면 stderr `[run_all] SKIP_BENCHES 에 알 수 없는 이름: <이름들>` + `사용 가능: <6종>` → rc 2, 아무 파일도 쓰지 않음.
- glob 확장 방지(지금 skip_bench 처럼 set -f) — `*` 같은 토큰도 이름으로 검사.
- 허용 목록을 skip 훅과 한 곳에서 관리할 방법이 있으면 X 제안(예: 배열 하나를 검사와 주석이 공유). 과한 구조 변경은 금지.
- 기존 동작 보존: 유효 이름이면 출력·건너뛰기·sanity·rc 전과 동일.

## 3. 문서
- run_all.sh 주석(44-46, 70-71)과 README 멀티모달 실행 절(§3.3 run_all 근처)에: 재개용 `SKIP_BENCHES` 는 **run_all.sh 를 직접 부를 때** 쓰는 것이고, run_full_eval·레인처럼 로더 출력을 eval 하는 경로에서는 **최상위 명령 앞에 환경변수로 붙여도 로더가 `unset`/yaml 값으로 덮어쓴다**(load_model_config.py:182-186). run_full_eval 은 로더 뒤 `.env` 를 source 하므로 `.env` 에 넣으면 살아남을 수 있으나 권장하지 않는다(run_full_eval.sh:110-112). 건너뛴 벤치는 발행 strict 가 누락으로 잡지 않는다.

## 수용 조건
- C6.1(결함 재현 FAIL→PASS): 임시 MODEL_TEST_BASE 에서 `SKIP_BENCHES=kretaa bash run_all.sh m` → HEAD 판은 rc≠2 이고(벤치 진입 전 멈추도록 가짜 환경 필요 — X 설계) 수정본은 rc 2·정확한 stderr·`.eval_session`·results 미생성.
- C6.2(보존): 6종 각각·여럿·빈 값은 검사 통과(벤치는 가짜로 대체해 실행 안 함), diffusion profile 의 b4 제외 경로 그대로. 기존 `shared/multimodal/tests/` 전체 PASS.
- C6.3: pytest 전체(캐시 허용·차단), 기준선 216 MATCH, 동결 0, `SKIPPABLE_BENCHES` 값 무변경, results 무변경.

## 반박 반영 결정(판 2, 10-20 X 반박 → A 확인)
- **§1**: 동결 configs/tests 는 로더 주석 원문을 검사하지 않음(test_load_model_config.py:19,55,285) — 주석 수정 안전. 허용값·오류 문자열·동작은 사용자 결정에 따라 보존.
- **§2 위치·보장**: run_all.sh 현재 16행(BASE_URL 대입) 뒤, 18행 앞. 보장 범위는 "직접 호출한 run_all.sh 자체가 파일을 만들거나 바꾸지 않음, stdout 없음, stderr 두 줄(`[run_all] SKIP_BENCHES 에 알 수 없는 이름: …` / `사용 가능: …`), rc 2". 호출자의 리다이렉션·로그는 범위 밖.
- **§2 단일 기준**: `SKIP_BENCH_NAMES=(kreta k_dtcbench koffvqa mtvqa_kr k_mmbench b4_latency_profile)` 배열 하나로 판정·진단 출력 공유. 기존 skip_bench·분기 유지, glob 상태 보존·복원, 사용자 토큰은 고정 포맷 printf 인자로. 비동결 시험 하나로 배열 집합 == `if skip_bench <이름>; then` 호출 집합. 로더의 정책 1종과 합치지 않음.
- **§3 README**: §3.3 멀티모달 예시 코드블록 뒤(현재 168행 다음)에 X 문안 3문단(재개용 직접 호출·허용 이름·오류 시점·sanity / yaml 은 측정 제외 정책, run_full_eval·레인은 로더가 덮어씀 / strict 는 결과 원천이 전혀 없는 벤치의 부재를 검사하지 않음). `.env` 는 "로더 뒤 source 되는 .env 에서 export 하면 전달될 수 있으나 권장하지 않음" 으로 한정. run_all.sh 주석도 같은 뜻으로 짧게.
- **C6.1**: 저장소 밖 독립 임시 디렉터리 두 개에 HEAD(`git show HEAD:./shared/multimodal/run_all.sh`)·수정본 run_all.sh 를 두고, 호출되는 벤치 파일은 표식만 출력하고 exit 0 인 가짜, B-3 manifest 없음, `PY` 는 stderr 표식 + exit 97 인 가짜, env 는 최소 구성(임시 MODEL_TEST_BASE, 제한 PATH, 더미 URL, `SKIP_BENCHES=kretaa`, EVAL_TIMESTAMP 미설정), cwd 임시. 기대: HEAD rc 1 + `.eval_session` 생성 + 가짜 벤치·PY 표식 존재 / 수정본 rc 2 + stdout 빈 값 + 정해진 stderr 두 줄 + 실행 표식 0 + 파일 트리·내용 무변경.
- **C6.2**: 같은 방식으로 끝까지 실행해 skip·실행 표식·rc 비교: 6종 각각·조합·미설정·빈 문자열·공백/탭/개행·중복은 통과, 오타·유효+오타 혼합·리터럴 `*` 는 rc 2. diffusion profile b4 제외 경로 보존은 로더 출력 → run_all 로 별도 확인. 기존 run_all 복사 시험은 SKIP_BENCHES 를 제거한 환경에서.
- **C6.3**: pytest 전체 허용(A 확인: orchestration 시험은 가짜 프로세스 표). guard 셸만 미실행.

## 기록
| 조각 | 커밋 | C 결과 | 기록 |
|---|---|---|---|
| 1~3 | (git log) | C6.1 PASS(같은 계약 시험: 6b9d292 사본 rc 1 — `rc=1, session_created=True, fake_bench_called=True, fake_py_stop=True`, 수정본 PASS; 실제 run_all 사본에 `kreta kretaa *` → stderr 두 줄·rc 2·MODEL_TEST_BASE 미생성) · C6.2 PASS(skip 관련 44 passed — 6종·조합·빈 값·공백·중복 통과, 오타·혼합·`*` 거절, diffusion b4 경로, 배열=훅) · C6.3 PASS(pytest 1532 passed 2 skipped 캐시 허용·차단, 셸 4개 rc 0, 기준선 216 MATCH, 동결 0, 로더 코드 diff 0(주석만), results 무변경) — 10-20 A 실행, diff 해시 f1f5a50d9dd2 | T 확인 필요(T run_all.sh 는 skip 훅 자체가 없음 — 이식 관계 아님). guard 셸 미실행 |
