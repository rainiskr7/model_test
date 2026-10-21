# SPEC: KOFFVQA 판정이 불완전하면 rc 0 으로 끝나지 않게 (2026-10-20, 판 3)

> 상태: 판 3 채택 범위 완료(`bc32554`) — judge·full 레인에 채점 완전성 검사 연결; `--require-publishable`은 철회, 발행 판정은 무변경.

담당: A 계획·검증·커밋, X 반박(read-only) → 구현(workspace-write). 범위 N 만(T 확인 필요는 보고만). 동결·운영 쓰기 금지 판 6 §0 그대로. **목표는 rc(성공/실패 표시)만** — 측정값·저장 내용·발행 게이트 판정은 바꾸지 않는다.

## 근거(관측)
- 운영 로그 `logs/resume_orch/orchestrator.log`: 10-05 qwen3.8 BF16 r3 "246/275 만 채점(크레딧 부족, rc=0 으로 통과됨)", 10-06 FP8 r3 "274/275 (json parse 오류 1건) → publish REJECTED".
- `koffvqa_api_judge.main()`(311-330)은 행 오류가 있어도 저장 뒤 None(rc 0). summary 의 `total`·`scored`(278-279).
- `full.sh`: judge rc 0 일 때만 derive(148 근처 `FULL_KOFFVQA_RAN`), derive 는 REJECTED 여도 `--native` 없으면 rc 0(`derive_multimodal_publish.py:_report_derivation`). `rN:derive` 재개는 judge 파일 존재만 확인(full.sh:114-122) → 불완전 판정도 최종 rc 0.
- 발행 게이트(adapters_koffvqa.py:64-71)는 이미 judge 오류·건수 불일치를 REJECTED 로 막는다 → 점수 오염은 없음.

## 판 1 → 판 2 (X 반박 10-20 반영)
- 반영: 별도 rc 10, derive 는 판정 rc 10 뒤에도 실행(REJECTED 사유 보존), derive `--require-publishable`(정상·재개 같은 명령), total 0 도 불완전, 명시 judge 재개 시 xlsx 없으면 rc 2.
- 범위 밖(기록만): `--limit <= 0` 해석, multimodal 단계의 `API_JUDGE`/`LOCAL_JUDGE` 상속 해제(현재 conf·yaml·.env 0건), `run_koffvqa.sh:110` 키 argv, T 의 judge 진입점(**T 확인 필요**).

## 판 2 → 판 3 (X 반박 2차 10-20 반영)
- `--require-publishable` 철회: 발행 가능 여부는 채점 완전성보다 넓고(기대 건수·SHA·ID·평균), 저장된 `summary.total` 과 raw 불일치는 검사하지 않는다(adapters_koffvqa.py:73-78). → **KOFFVQA 채점 완전성 전용 검사** 하나를 judge·full 레인 정상·재개가 공유. 발행 판정·sidecar 내용 무변경.
- judge 오류 코드는 일반화하지 않는다: 키 오류 rc 2(koffvqa_api_judge.py:318), 컬럼 오류 문자열 SystemExit rc 1(209) 그대로.
- derive 실행 조건 확대는 **koffvqa_judge rc 0·10 만**(다른 비0 는 옛 산출물 derive 위험).
- 명시 judge 재개 검출은 `FULL_RESUME_REP == N && FULL_RESUME_INDEX == 6`(full.sh:29-35) — 그 반복에만 적용.
- NATIVE skip 으로 derived 가 빈 경우도 완전성 검사는 저장된 judge 파일로 판단하므로 영향 없음(derive CLI 무변경).

## 요구
1. **완전성 검사(새 순수 함수 + CLI)**: 예) `shared/multimodal/benches/koffvqa_judge_complete.py` — `check(results, summary) -> (ok, reason)`; 완전 = `summary.total == summary.scored == len(results) > 0` 이고 error 있는 행 0, 모든 행에 0~10 정수 score(adapters_koffvqa 규칙과 같은 정의, 코드 중복이면 X 제안). CLI `python -m … <judge_dir>`: 완전 rc 0, 불완전 stderr `[koffvqa_judge] incomplete: …` rc 10, 파일 없음·JSON 깨짐 rc 2. 키·네트워크 접근 없음.
2. **judge** (`koffvqa_api_judge.py`): 산출물 저장은 지금과 같이 먼저. 그 뒤 같은 `check` 로 불완전이면 stderr + **rc 10**, 완전이면 rc 0. 기존 rc 1·2 경로 무변경.
3. **full 레인** (`orchestration/tracks/full.sh`):
   - koffvqa_judge rc 0 **또는 10** 이면 `FULL_KOFFVQA_RAN=1`(derive 실행해 REJECTED 사유 보존). rc 10 은 판정 실패 1건 → 최종 rc 1.
   - derive 단계: derive rc 0 뒤 같은 세션 judge 폴더에 완전성 CLI 실행, rc 10 이면 derive 단계 실패(판정 실패 1건)로 기록. 정상 진행·`rN:derive` 재개 공통. stage 목록·인덱스 무변경. dry-run 은 확인 명령도 표시(형식 X 제안, fixture 갱신).
   - `rN:koffvqa_judge` 명시 재개인 반복에서 xlsx 없음 → log + exit 2.
   - README_full: 실패 정책 rc 10, 재판정은 전체 재채점(10-05/10-06), 재개는 conf `FULL_RESUME_FROM`(run_lane.sh:16, resolver.py:23).
4. **시험(X 작성)**: X 반박 표의 갱신 대상(test_koffvqa_judge_requests.py:22,27 · r3_koffvqa_judge.json:2,41 · test_koffvqa_judge_key_env_units.py:34,56,61 · test_run_lane_full.sh:174,274 · fixtures_full/dry_run.txt:11,19,27). 새 사례: 완전성 함수(정상·부분·전부 실패·0건·total 불일치·score 범위 밖), CLI rc, judge 실제 CLI 종료 코드, full 레인 판정 rc 10 → derive 실행·최종 rc 1·다음 반복 계속, `rN:derive` 재개 불완전 → rc 1, `rN:koffvqa_judge` 재개 xlsx 없음 → rc 2, 실제 derive 를 연결한 격리 사례에서 REJECTED sidecar 존재. 기존 derive 무옵션·NATIVE 보호 시험은 그대로.

## 수용 조건
- C7.1(결함 재현 FAIL→PASS): 가짜 client 로 2건 중 1건 오류 → 수정 전 HEAD(3b5377e) 판정기 rc 0(FAIL), 수정본 rc 10 + results/summary 저장. 같은 assertion.
- C7.2(결함 재현 FAIL→PASS): full 레인 fixture 에서 판정 불완전 — (a) 정상 진행 judge rc 10 (b) `rN:derive` 재개 + 불완전 judge 파일 → HEAD full.sh 최종 rc 0(FAIL; (a) 는 HEAD judge 가 rc 0 을 내는 상황으로 재현), 수정본 rc 1 + derive 실행 기록, 실제 derive 격리 사례에서 REJECTED sidecar 존재.
- C7.3(보존): 전부 채점이면 judge rc 0 · results.json·summary.json 내용 동일(run_config 의 스크립트 해시류 제외), derive CLI 무변경(diff 0), pytest 전체(캐시 허용·차단), 셸 시험 4개+harness runner rc 0, 기준선 216 MATCH, 동결 0, results 무변경.

## 기록
| 조각 | 커밋 | C 결과 | 기록 |
|---|---|---|---|
| 7 | (git log) | C7.1 PASS(같은 assertion: 3b5377e judge 에서 `assert 0 == 10` FAIL, 수정본 rc 10·산출물 저장) · C7.2 PASS(3b5377e full.sh 정상·`r1:derive` 재개 둘 다 REJECTED sidecar 인데 "판정 실패 0건" rc 0 FAIL, 수정본 rc 1) · C7.3 PASS(pytest 1581 passed 2 skipped 캐시 허용·차단, 셸 4개+harness runner rc 0, 기준선 216 MATCH, 동결·derive CLI·publish 코드 diff 0, results 무변경, runner_checks cmp 동일) — 10-20 A 실행, diff 해시 e3aa127fa9e0 | X 반박 2회(판 1→2→3). guard 셸 시험 미실행(정지 레인). T 확인 필요: T judge·run_koffvqa 같은 구조 |
