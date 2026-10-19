# 감사 기록 (보존본)

세션 임시 폴더에서 10-13 에 복사한 **과거 실행의 증거**다. 여기서 다시 실행하지 않는다 — `audit_v3/run.py` 는 `out/` 을 덮어쓰고, 입력을 `HERE.parent` 기준(`data_kosgd/`, `data_sgd_en/`, `tokenizers/`, `kosgd_audit/`)과 절대경로(계획, Qwen3.8 토크나이저)로 찾는다. 재실행이 필요하면 새 폴더에 복사해 입력 위치를 명세에 적고 돌린다.

| 폴더 | 무엇 | 실행 기록 |
|---|---|---|
| `kosgd_audit/` | 10-12 KoSGD 재구성 감사(R1–R3) + 3,000 턴 선정(seed 20261012) | `run_record.txt` |
| `audit_v3/` | 10-13 감사 v3(R2v3·R4·R5·R6·R7) — 주 지표 판(전체판)을 정한 근거 | `my_run_record.txt` (Claude 실행: 코드 sha256 · exit code) |

- `MANIFEST.sha256` — 여기 있는 파일 전부. 세션 폴더 원본과 같음을 10-13 에 대조했다.
- `INPUTS.sha256` — 감사 입력(KoSGD·영어 SGD JSON, 토크나이저)의 해시. 데이터 자체는 저장소에 넣지 않았다.
- `EXCLUDED.sha256` — 넣지 않은 파일의 해시: Codex 작업 로그(원문이 섞일 수 있음), `out/example_*.json`(KoSGD 대화 원문 — 라이선스 확인 전).
- **보존되지 않은 것**: 감사 v3 실행 당시의 계획 원문(sha256 `b0533de0…`, `my_run_record.txt`). 그 뒤 계획에 결과 문단이 추가돼 해시가 바뀌었다. §7-1 규칙 표 자체를 실행 뒤 고친 기록은 없다(개정 12 는 규칙을 고치지 않고 다음 판 규칙을 따로 적는다).

## 개정 15 Phase A 추가

`kosgd2_selection/select_turns.py`는 새 풀 선정 코드이며 이 폴더에는 실행 selection을
미리 생성하지 않는다. 정렬·옛 대화 제외·USER 없는 대화 제외·seed 20261019 연속 choice로
대화당 한 USER 턴을 선택한다. stdout에는 G/제외 수 통계만, selection에는 ID·해시만 남긴다.
기존 감사 폴더와 해시 증거는 변경하지 않는다.

감사 v4(실제 systemone/B1 바이트·독립 원본·세 encoder), v5(kosgd2 최종 13질문·두 판)는
계약 판 5 명세만 등록했다. 스크립트 구현·복사·실행은 Phase B다. 기존 v3의 경로만 바꿔
새 문항의 PASS 증거로 삼을 수 없다. 입력/스크립트 해시·완전한 분모·오류 주입을 함께 기록한다.

## kosgd2_selection — 판 5 보정 1 재생성 절차

기존 판 5 selection은 보존한다. 보정 1 D1a는 T0 fixture의 KoSGD 대화를 결과에서 제외하고,
그 대화도 기존 순서대로 RNG choice를 소비해 나머지 대표 턴을 유지한다.
`select_turns.py --source dataset/kosgd2 --excluded audits/kosgd_audit/audit_result.json
--t0-fixture configs/t0/fixture_v1.json --out .work/kosgd2_selection.corrected.json`으로 별도 파일을 만든다.
CLI는 --t0-fixture 누락·잘못된 fixture·참조 원본 부재·옛 풀 교집합·기존 출력 덮어쓰기를 거부한다.
새 증거에는 t0_fixture_sha256, n_t0_excluded, exclusion_reason=frozen_boundary_t0_out_of_pool을 기록한다.

**현재 상태: 실데이터 재생성 미실행.** 커밋된 selection.json 및 configs/splits/kosgd2.json은 아직 1,201대화다.
Claude는 보정 selection이 기존 것에서 26_00068 하나만 제거했는지(나머지 1,200턴 동일) 검증한 뒤 반영하고,
새 분할 pool1200/dev240/test960·gold oracle1200/1200·모든 T0 참조의 가족 풀 밖 여부를 검증한다.
합성 시험 통과를 이 실데이터 검증의 증거로 쓰지 않는다. 기존 kosgd_audit 등 다른 감사 폴더는 수정하지 않는다.
