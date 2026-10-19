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
