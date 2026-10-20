# 2단계 수용 도구 — 2026-10-21

기준 커밋은 eb8e2fa다. 이 폴더는 구현·합성 시험 도구이며 실제 run의 수용 완료를 뜻하지 않는다.
기존 결과·감사 증거·보고서를 덮어쓰지 않는다. 아래 실 run 명령은 운영자가 별도로 실행한다.
Python에는 프로젝트 의존성과 pytest, scipy가 필요하다. 저장소 루트에서 실행한다.

## C1: 형태·의존·기존 시험 보존

```sh
# 변경 전 baseline checkout에서 같은 형식으로 수집한 before.json을 보존한다.
JEV_NODEIDS_OUT=/tmp/after.json PYTHONDONTWRITEBYTECODE=1 \
  python -B audits/stage2_20261021/test_runner.py tests --collect-only -q -p no:cacheprovider
python -B audits/stage2_20261021/shape_check.py --before /tmp/before.json --after /tmp/after.json
```

manifest는 `{nodeid: [skip/skipif/xfail marker 이름]}` JSON이다. 기존 nodeid 삭제와 새 marker는 실패한다.
shape_check는 전체 jeveval 및 이 폴더 Python, 변경된 시험·ops/status를 검사한다.
200줄/50줄·첫머리 무엇/입력/출력/계약 §·AST import 방향·순수 층의 I/O/시계 호출·짝 시험을 검사한다.
score와 cmd_report/cmd_compare의 셋 이름 문자열 조건도 거부한다. 등록표는 MappingProxyType이며
계산 안의 metric_spec 조회는 금지한다. 기존 data/split→contract.stages,
data/items/kosgd_requests→contract.render, data/t0_fixture→t0.request만 파일 단위 예외다.

```sh
PYTHONDONTWRITEBYTECODE=1 python -B audits/stage2_20261021/test_runner.py tests \
  -q -p no:cacheprovider --basetemp=/tmp/jev-stage2-tests \
  --ignore=tests/client/test_http_live.py --ignore=tests/run/test_executor_live.py \
  --ignore=tests/t0_io/test_live.py
```

test_runner는 실제 저장소 dataset/.work/results의 open/listdir/scandir 및 소켓 bind/connect/DNS를
차단한다. 수집 대상은 반드시 `tests`로 지정한다. tmp_path 합성 자료에는 접근할 수 있다.
위 세 기존 live 시험 파일은 localhost 소켓을 필요로 하므로 네트워크 금지 실행에서 제외한다.
T0 파일의 무소켓 시험 3개는 별도로 실행할 수 있다:
`test_runner.py tests/t0_io/test_live.py -k 'not test_cli_all_stages_with_loopback'`.
네트워크가 필요한 기존 시험은 총 25개다. 시험에 skip/xfail을 추가하지 않는다.
subprocess에서 쓰는 자료도 합성 tmp_path여야 한다.

## C2: 명시 필드 경로 정규화와 비교

각 `--old-run`과 `--new-run`은 모델별 run 루트(그 아래 A/<set>/<variant>)다.
여러 쌍은 같은 순서로 지정한다. compare 루트는 그 아래 A/<set>/<variant>/compare.json 7개를
가진 폴더다. 예시의 MODEL1~3과 NEW_RUN, compare ID, 보고서 경로를 실제 값으로 바꾼다.

```sh
python -B audits/stage2_20261021/compare_runs.py \
  --old-run results/MODEL1/main_20261019T141841 --new-run results/MODEL1/NEW_RUN \
  --old-run results/MODEL2/main_20261019T141841 --new-run results/MODEL2/NEW_RUN \
  --old-run results/MODEL3/main_20261019T141841 --new-run results/MODEL3/NEW_RUN \
  --old-compare results/_compare/OLD_COMPARE --new-compare results/_compare/NEW_COMPARE \
  --old-report OLD_REPORT_final.md --new-report NEW_REPORT.md
```

완전한 C2는 `ok`, `compare_checked`, `report_checked`가 모두 true여야 한다.
선택 인자를 생략하면 해당 검사를 수행하지 않았다고 출력한다. 모델별 변형 누락도 실패한다.
실제 dev/final SHA·nbytes, threshold SHA와 test/seal/risk의 연결을 먼저 검증한다.
JSON artifact는 기존 writer의 정렬 키·한 칸 들여쓰기·끝 LF, final은 compact JSONL 형식을
검사하므로 공백/형식 변경을 수치 정규화로 숨기지 않는다. 허용 경로는 아래뿐이다.

| 파일 | 정규화 경로 | 선검사 |
|---|---|---|
| threshold/risk/scores/summary | 최상위 run_id(있는 경우) | fingerprint identity와 동일 |
| risk | threshold_sha256 | 실제 threshold 바이트 SHA·seal 연결 |
| 파생 threshold | dev_input.sha256, dev_input.nbytes | 실제 dev final SHA·크기 |
| final | 최상위 derived_from의 run 경로 성분 | model/run/A/set/full 형식·단계 derived.json 일치 |
| scores | cost.by_stage.*.derived_from의 run 경로 성분 | 동일 출처 형식 |

직접 실행 final은 원본 바이트까지 동일해야 한다. 파생 final도 허용된 출처 성분 외의 필드·
순서·행 순서를 보존한다. compare 7개는 정규화 없이 바이트 비교한다. seed·수치·분모·상태·
임의 문자열 속 run ID는 정규화하지 않는다. summary 유무도 비교한다.

보고서는 추가 선택적 예측/확신 변형 절·감사 줄을 제외하고 기존 내용을 비교한다.
명시 출처 줄 `code_sha256: …; started_at: …`, `replay dev/test/extra: …`, 제목의 run ID,
비교 제목의 compare ID만 별도로 정규화한다. 코드 변경·새 replay에서 이 값들은 필연적으로
달라진다. 빈 줄은 표시용으로 제외한다. 기존 지표·주 상태·질문 표·공통 오류·비교 수치는 보존한다.
이 보고 비교가 새 출처 값의 진실성까지 인증하는 것은 아니다.

## C3: 독립 보조 지표 oracle

`--run-dir`은 모델/run/A/set/variant 폴더이며 세 모델의 **비파생 변형 전부**를 반복 지정한다.
기존 score를 실행해 selective.json을 먼저 생성한다. 이 CLI는 읽기만 한다.

```sh
python -B audits/stage2_20261021/check_oracle.py --root . \
  --run-dir results/MODEL1/NEW_RUN/A/kosgd/full \
  --run-dir results/MODEL2/NEW_RUN/A/kosgd/full \
  --run-dir results/MODEL3/NEW_RUN/A/kosgd/full
```

위 예시는 full 3개만이다. 실제 수용에서는 각 비파생 셋/변형을 모두 추가한다.
파생 actions_only separate는 기존 history_stage 제한을 유지하므로 지정하지 않는다.
`oracle.py`는 jeveval 모듈을 import하지 않는다. 모든 cutoff와 정답×오류 쌍을 직접 열거하고
Fraction으로 면적을 계산한다. CP 함수 대신 Binom(n,τ)의 누적확률로 허용 k를 전수 탐색하고
scipy.stats.binom.pmf를 합산해 조건부 통과 확률을 구한다. production selective/power는 사용하지 않는다.
CLI는 동결 입력 복원·주 역사 검증만 기존 history/history_stage에 의존한다. 이 읽기 경로의
보조 파일 검증은 생산 코드를 사용할 수 있으나 기대 수치는 오직 독립 oracle이 계산한다.
정수·null·키·배열 길이는 정확 비교하고 실수는 절대 오차 1e-12다. brute-force이므로 큰 n에서는 느리다.

자체 시험은 빈 분모·전부 무효·동점·첫 묶음 이전·최대 coverage<1·한 클래스,
n=None/0/n_min−1/n_min과 허용 필드 변경·수치/분모/상태/seed 변경 실패를 포함한다.

## 구현 시 확정한 해석 (SPEC_AMBIGUOUS)

- 등록 test replay: 별도 봉인 전용 CLI가 없으므로 source/target 선검사 뒤 같은 test gate를
  호출해 question→variant→주 seal을 쓰고 replay 표식·attempts를 복사한다. 봉인 명령은
  dev threshold 생성 명령들을 뜻하며 test 복사보다 먼저 실행한다. 미등록 replay 경로는 유지한다.
- v4 historical_calls 항목에는 set이 없다. 감사 계산을 바꾸지 않고 검증된 최상위 set을
  상속해 정확 tuple을 검사한다. 항목에 명시된 다른 set은 거부한다.
- selective/1에는 power 표도 저장한다. 보고는 옛 run을 위해 risk에서 같은 표를 계산한다.
- C2 보고의 새 code/시각/replay 출처는 위에 열거한 줄만 정규화한다. 데이터 수치를
  포함한 임의 문자열 치환은 사용하지 않는다.
- 아무 분석도 선언하지 않은 실행의 기존 주 seal 복구 규칙은 변경하지 않는다. 등록 선언이
  있는 실행에서만 추가 봉인 삭제·복사·중간 중단을 손상 정지로 검사한다.
