# §14 출력 불변 기준선

N 루트에서 실행한다. 네트워크·서버 호출 없이 저장된 결과를 읽는 개발 도구이며,
실제 results/data가 필요하다. 단위 시험은 합성 입력만 쓴다.

```bash
.venv/bin/python -B -m tools.output_baseline.baseline --inputs tools/output_baseline/inputs.txt --out /tmp/output-baseline.json
bash tests/run_pytests.sh baseline
.venv/bin/python -B -m tools.output_baseline.compare /tmp/output-baseline.json
```

종료 코드는 0=동일, 1=차이, 2=입력 누락·실행 실패·전제 조건 실패다.
실행 도중 실패해도 임시 증거 폴더와 단계별 stdout/stderr/rc를 남긴다.
`--out`은 results/data/configs 밖이어야 한다. 증거 폴더는 자동 삭제하지 않는다.

코드·입력·출력은 분리한다. HEAD는 `git archive HEAD -- <추적 최상위 경로들>`을
풀며, 실제 입력인 results/data는 아카이브에서 제외한다. 작업트리 코드와 차례대로
실행하며 각각 코드 루트를 cwd/PYTHONPATH로 설정한다. `.venv/bin/python`은 실제 N의
동일 인터프리터를 쓴다. HEAD SHA, archive 해시, tracked diff 해시와 전문, 미추적 코드
해시를 기록한다. 신규 baseline 도구 자체는 두 쪽의 시험 대상 코드가 아니다.

`inputs.txt`의 목록과 judge의 형제 koffvqa 디렉터리, configs/model_identity.json을
시작할 때 한 번 복사한다. 모든 복사 파일의 SHA-256을 기록하므로 workbook·summary·
run_config도 포함된다. KRETA jsonl은 부모 디렉터리도 복사하여 results.json·run_config.json
의존을 보존한다(derive 호출 대상은 고정된 jsonl 목록뿐이다). 목록은 런타임에 늘리지 않는다. 세 트랙은 주석의 이유로 각 1개,
multimodal은 2026-10-19 생성 시 `discover_sources` 전 대상 208개를 고정했다.
목록에 있는 입력이나 의존 디렉터리가 없으면 rc 2다. snapshot 파일 누락·변경도 rc 2다.
공통 입력은 양쪽이 읽기만 하고, tau/functionchat은 쪽별 출력 디렉터리로 다시 복사해
기존 summary를 제거한 뒤 재채점한다. 폴더 단위 복사는 시점 원자성을 보장하지 않지만
복사 완료 이후 양쪽은 동일한 바이트를 사용한다.

비교 대상:

- agent: `shared.agent.scoring.score_run --check`의 stdout 전문과 rc. 0/1/3은 실행 완료,
  그 외는 실패다. MODEL_TEST_BASE는 실제 N이며 외부 metrics.py 해시를 기록한다.
- taubench/functionchat: 새 summary.json 전체 해시와 rc. 두 채점기는 검증 거부도 summary를
  쓰므로 rc 0/1을 실행 완료로 인정한다. rc 2는 실패다. 경로가 들어간 로그는 보관만 한다.
- 보고서: `reports.report_{agent,harness,multimodal,nlu,taubench}_tracks --base N`의 stdout
  전체 바이트와 rc(0만 성공). 모두 실제 스크립트의 기본 출력이며 `--strict`는 쓰지 않는다.
  **실제 results 전체를 읽는다.** 매니페스트의 `reports_read_live_results=true`,
  `reports_are_snapshotted=false`, `harness_report_may_change_with_running_lanes=true`가 이를
  표시한다. 운영 레인이 쓰는 중이면 특히 harness 보고서가 달라질 수 있다. 차이를 숨기거나
  정규화하지 않는다. 다른 트랙도 실행 중 결과가 바뀌면 보고서가 달라질 수 있다.
- multimodal: 각 코드 루트의 `derive_source`와 `sidecar_json`으로 만든 전체 JSON 해시.
  배치 worker는 `-c`로 실행해 새 tools 패키지가 없는 HEAD에서도 해당 HEAD의 shared만
  import한다. snapshot 안의 `_derived`에는 쓰지 않고 쪽별 출력에 쓴다.

매니페스트에 예상 산출 이름을 별도로 기록한다. compare는 파일을 다시 읽어 해시하므로
한쪽 파일 변조를 검출한다. 양쪽 모두 같은 산출이 없거나 같은 실행 실패를 겪어도 rc 2다.
단독 compare는 기록된 전제 조건·경계 결과와 현재 snapshot/출력을 검사한다.

실행 전에 `bash tests/run_pytests.sh -k runner_requests --junitxml <임시경로>`를 실행하고
JUnit에서 passed/failed/error/skipped를 기록한다. 이 전제가 실패하면 중단한다.
기준선은 저장 결과의 재채점이므로 **요청 변경은 못 잡는다**. 요청 시험을 대체하지 않는다.

실행 직전 마커를 만들고 종료 시 `find results data configs -newer <마커>` 0건과
`git status --short results/` 전후 동일을 검사한다. 자식 프로세스에는 `-B` 및
PYTHONDONTWRITEBYTECODE=1을 주어 외부 bench와 configs에도 pycache를 쓰지 않는다.
마커 검사는 "썼다가 복원"을 검출하지 않는다. 외부 레인의 쓰기와 도구의 쓰기도 구별하지
않으므로 변경이 보이면 rc 2로 남긴다. 실행 시간은 전체와 각 subprocess별로 기록한다.

음성 검증은 manifest의 `sides.working.artifacts` 중 파일 하나를 바꾸고 compare를 돌리면
이름과 rc 1이 나온다. 입력 누락은 임시 snapshot의 목록 대상 하나를 다른 임시 경로로
옮긴 뒤 compare로 rc 2를 확인한다. 실제 results/data/configs를 바꾸지 않는다.
