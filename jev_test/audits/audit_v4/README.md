# 감사 v4 — 오프라인 구현

보존본 v3를 실행하거나 수정하지 않는다. kosgd2 프로필이 계획의 종전 v5를 포함한다.
부재/미실행은 INCOMPLETE, 규칙 위반은 FAIL이며 full 후보가 아니면 종료 코드 2다.
입력/출력 오류는 원문 없는 고정 메시지와 종료 코드 1이다. 기존 출력은 덮어쓰지 않는다.

| 파일 | 기능 / 짝 시험 |
|---|---|
| `run.py` | 규칙·모델 결과 조립 / test_v4_run |
| `worker.py` | 모델당 독립 프로세스, 인코더와 post 포착 / test_v4_worker |
| `checks.py` | R4/R7/해시/길이 순수 검사 / test_v4_checks |
| `selftest.py` | 합성 13 주입(옛 kosgd ongoing_two만 N/A) / test_v4_selftest |
| `evidence.py` | 입력·코드·명시 역사 run SHA / test_v4_evidence |
| `offline.py` | 네트워크 거부, executor post 메모리 포착 / test_v4_offline |
| `preservation.py`, `offline_check.py` | 보호 파일 SHA·출력 경계 wrapper / 각각 test_v4_preservation, test_v4_offline_check |
| `independent/source.py` | 원 schema/catalog/lists/선정/split / test_v4_independent |
| `independent/frozen.py`, `independent/requests.py` | 249f096 고정 연결표/문구 SHA, 독립 봉투 / test_v4_independent, test_v4_worker |
| `independent/labels.py`, `independent/timing.py` | 독립 고정 칸/행동/R5/R6 / test_v4_independent |

independent는 jeveval을 import하지 않는다. 공통 task.label/role과 lists가 함께 바뀌어도
동결 표/문구 SHA 및 원 schema 대조로 거부한다. R6는 모든 원본 test USER 중 INFORM_INTENT frame이
분모다. actions_only에는 R6가 적용되지 않고 R5는 act 범위만 적용한다.

6모델 실제 인코더 길이는 각각 하위 프로세스에서 잰다. null served_name은 측정용 이름만 쓰며
measurement_config=true/byte_evidence=INCOMPLETE다. 실제 전송 완료라고 표시하지 않는다.
동결된 세 모델은 계획/독립/가짜 post SHA를 비교한다. separate actions_only는 직접 호출 가정이다.
실데이터 실행과 외부 oracle 1,200/1,200 검증은 Claude가 수행하며 합성 시험 결과와 구분한다.
외부 oracle의 호출 API가 정의되지 않아 자동 실행하지 않는다. oracle 소스 SHA와 비교 집계는
별도 수용 기록으로 남긴다.

저장소 루트에서 Python은 기존 시험 환경(README의 venv)을 사용한다. 아래 명령은 **이번 구현에서 실행하지 않았다**.

```sh
python -B -I audits/audit_v4/offline_check.py -- audits/audit_v4/run.py --set kosgd2 --out audits/audit_v4/out/kosgd2.json
python -B -I audits/audit_v4/offline_check.py -- audits/audit_v4/run.py --set kosgd --out audits/audit_v4/out/kosgd.json
```

두 번째 명령은 역사 run 미지정으로 historical_calls=INCOMPLETE가 된다. 저장 호출 대조까지 하려면
파일을 생성하기 **전에** 정확한 run 폴더를 반복 지정한다(파생 actions_only 대신 원 full run).

```sh
python -B -I audits/audit_v4/offline_check.py -- audits/audit_v4/run.py --set kosgd --out audits/audit_v4/out/kosgd.json --history-run results/MODEL/RUN/A/kosgd/full
```

부분 run은 대조한 호출 수를 기록하되 전체 저장 호출 증거는 INCOMPLETE다. 과거 FAIL/PASS 모두
기존 실행을 수정하지 않으며 사전 감사로 소급하지 않는다. 서빙 후 재감사 결과는 새 파일명으로
보존한다. 보고 연동 기본 위치는 out/<set>.json이다. 다른 판은 report의 반복 가능한
`--audit-evidence <set>=<path>`로 명시 지정하며 적격 검사 통과 시에만 연결한다.
경로는 audits/audit_v4/out/ 아래 JSON으로 제한하고 자동 최신 선택은 하지 않는다.
사전 감사는 동결 입력 SHA, 사후 감사는 추가로 정확한 model/set/variant/run_id의 호출 PASS를
요구한다. v4 호출 항목의 set은 최상위 set을 상속한다. 다른 profile·호출 대조 FAIL·INCOMPLETE는
연결 미확인이다. 보고에는 모델·선택 파일명·파일 SHA 앞 12자를 남긴다.

`--oracle-source /absolute/path/ongoing_two_oracle.py`를 주면 실행하지 않고 소스 SHA만 기록한다.
`oracle_verification.status`는 자동 대조 API가 없으므로 INCOMPLETE로 남는다. Claude가 별도로
기록하는 실제 1,200/1,200 대조 증거를 이 필드가 대신하지 않는다.
