# 서버 없는 수용 도구 — 계획 2판

계약 §9c. 기존 dataset/.work/results와 감사 out을 구현 시험에서 읽거나 변경하지 않는다.
실 run·감사 재실행·새 보고서 생성은 운영자가 별도로 한다. 기존 결과 replay는 이번 수용의 조건이 아니다.
[변경 파일 책임·재사용 근거·새 함수 검색 기록](IMPLEMENTATION.md)을 함께 확인한다.
`PY`는 프로젝트 의존성과 pytest가 있는 Python 실행 파일이다. 저장소 안 운영 venv를 변경하지 않는다.

| 파일 | 책임 | 짝 시험 |
|---|---|---|
| contract_map_check.py | d41e8b9 원문·여섯 블록 SHA·현행 제목·지도 21/5/7행 | tests/audits/test_contract_map_check.py |
| function_shapes.py | 함수 본문 AST에서 인자·지역 이름 정규화 | tests/audits/test_function_shapes.py |
| dup_check.py | Python 본문/shell 이름 중복, base 대비 새 그룹·새 구성원 | tests/audits/test_dup_check.py |
| t0_worker.py | 한 트리에서 기존 fake runtime/post로 독립 실행 | tests/audits/test_t0_worker.py |
| t0_compare.py | 두 worker 실행·SHA 선검사·두 필드만 정규화·help 비교 | tests/audits/test_t0_compare.py |

```sh
"$PY" -B audits/serverless_20261021/contract_map_check.py
"$PY" -B audits/serverless_20261021/dup_check.py --base 57ddf76
```

중복 Python 범위는 jeveval/**, ops/*.py, audits/**/*.py, tests/**/*support*.py와 conftest.py다.
자료/산출물 디렉터리는 제외한다. 함수의 docstring 제외 최상위 문이 3개 이상인 본문을 검사하며
전역 이름·속성·상수·연산은 보존한다. 같은 동작의 모든 변형을 찾는 의미 동치 증명은 아니다.
base는 Git object에서 읽고 checkout하지 않는다. 기존 중복은 JSON groups에 남기고 new_groups만 실패시킨다.
줄 이동은 새 그룹이 아니며 기존 그룹에 함수가 추가되는 경우도 실패다.

지도 검사는 원문 범위 첫 40 Unicode 문자의 SHA와 현 문서에 남은 원문을 함께 검사한다.
21번 extra 절은 보존 fence가 아닌 현행 본문에 원문 그대로 남은 경우다. 옛 식별자를 현행 절에서 찾는
검사는 하지 않는다. 블록 SHA·행 정체성·절 존재는 구조 증거이며 의미 반영 전수 검토의 대체가 아니다.

## 보고서 비교

기존 도구를 확장했다. 운영자가 이미 만든 두 보고서만 읽으며 run 디렉터리는 열지 않는다.

```sh
"$PY" -B audits/stage2_20261021/compare_runs.py --audit-only-report \
  --old-report "$OLD_REPORT" --new-report "$NEW_REPORT" --expected-derived-lines 3
```

감사 줄을 지우지 않으며 정확히 3개의 actions_only 사후 감사 연결 미확인 줄이 파생 출처/원천 PASS/
가상 직접 요청 범위 문구로 바뀌어야 한다. 나머지 공백·줄 끝·출처 파일명·SHA도 같아야 한다.
새 감사 증거 파일을 선택해 모든 감사 줄의 출처가 바뀐 경우에는 실패한다. 문구 회귀 비교에는 같은
명시 감사 파일을 사용하고, 새 감사의 출처 변경 검증은 별도로 수행한다.
기존 normalize.report의 기본 동작과 run/compare 비교 모드는 유지한다.

## 독립 T0 비교

```sh
"$PY" -B audits/serverless_20261021/t0_compare.py \
  --base-tree "$BASE_JEV_TREE" --current-tree "$CURRENT_JEV_TREE" --scratch "$NEW_EXTERNAL_SCRATCH"
```

두 트리는 jeveval·configs·기존 tests/t0_io 및 tests/run 도우미를 포함해야 한다. scratch는 두 트리와
현재 도구 저장소 밖의 새 경로여야 한다. 같은 Python으로 각각 새 프로세스를 띄운다. 세 참조 가족
clef/pplx_v1/pplx_v1_1에서 기존 setup fixture factory, fake runtime, 고정 AttemptResult를 재사용한다.
네트워크 및 각 실제 소스 트리의 dataset/.work/results 접근은 기존 test_runner.protect로 차단한다.
임시 root에도 실행하는 jeveval 코드를 복사해 code_sha256가 빈 폴더 해시가 되지 않도록 확인한다.

각 가족의 산출물 7개와 단계 help 5개를 비교한다. fingerprint 실제 파일 SHA를 t0.json과 대조하고
source code SHA를 선택한 트리와 대조한 뒤 fingerprint.json.code_sha256와 t0.json.fingerprint_sha256만
정규화한다. latency·요청·응답·규칙·참조 모듈 SHA는 정규화하지 않는다. 임시 증거는 조사할 수 있게 남긴다.
이는 실모델·실데이터 T0 PASS가 아니라 두 코드의 합성 동작 동일성 증거다.

## 시험 실행

```sh
JEV_NODEIDS_OUT="$AFTER_MANIFEST" PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B audits/stage2_20261021/test_runner.py tests --collect-only -q -p no:cacheprovider
"$PY" -B audits/stage2_20261021/shape_check.py --before "$BEFORE_MANIFEST" --after "$AFTER_MANIFEST"
PYTHONDONTWRITEBYTECODE=1 "$PY" -B audits/stage2_20261021/test_runner.py tests -q -p no:cacheprovider \
  --basetemp="$NEW_TEST_SCRATCH" --ignore=tests/client/test_http_live.py \
  --ignore=tests/run/test_executor_live.py --ignore=tests/t0_io/test_live.py
```

기존 네트워크 시험은 별도 범위다. test_t0_io/test_live의 무소켓 시험 3개는 `tests/t0_io/test_live.py
-k 'not test_cli_all_stages_with_loopback'`으로 따로 실행한다. 새 skip/xfail을 추가하지 않는다.
shape_check는 새 도구와 ops/registration_status.py를 포함한다. 등록 사슬 합성 시험은 기존
Harness·analysis_support로 systemone/separate, systemone/joint, B1/separate 두 판의 registered를 확인한다.
