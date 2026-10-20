# 구현 변경 기록 — 계획 2판

실제 dataset/.work/results는 검증 입력으로 사용하지 않았다. 합성 fixture로 구현을 검사했다.

| 파일 | 변경 |
|---|---|
| [CONTRACT_MAP.md](../../CONTRACT_MAP.md) | 보정 5의 현행 절·기존 대응 행의 확장 관계 추가. 기존 원문 해시 보존. |
| [P1_CONTRACT.md](../../P1_CONTRACT.md) | §5-1b aux 격리, §7-4b 복수 선언, §7-4c 선택적 예측, §7-4d 확신 변형, §7-6 family/감사, §9b 수용 도구 추가. §11 역사 payload 보존. |
| [audits/audit_v4/README.md](../../audits/audit_v4/README.md) | 기본 감사 경로 유지, 다른 판은 명시 옵션과 적격 검사로 연결. |
| [audits/stage2_20261021/CHANGES.md](../../audits/stage2_20261021/CHANGES.md) | 전체 파일별 변경 요약과 실행 검증 기록(이 문서). |
| [audits/stage2_20261021/README.md](../../audits/stage2_20261021/README.md) | C1/C2/C3 실행법·명시 정규화 경로·독립성 범위·SPEC_AMBIGUOUS 기록. |
| [audits/stage2_20261021/check_oracle.py](../../audits/stage2_20261021/check_oracle.py) | 새 모듈: 실제 run oracle 대조 CLI · 입력: 명시 run 폴더 · 출력: 원문 없는 차이 · 계약 §9 C3. |
| [audits/stage2_20261021/compare_evidence.py](../../audits/stage2_20261021/compare_evidence.py) | 새 모듈: C2 바이트 증거 확인 · 입력: 명시 변형 폴더 · 출력: 검증된 객체/정체성 · 계약 §9 C2. |
| [audits/stage2_20261021/compare_runs.py](../../audits/stage2_20261021/compare_runs.py) | 새 모듈: C2 run/compare/보고 회귀 CLI · 입력: 명시 옛/새 경로 · 출력: 차이 경로 · 계약 §9 C2. |
| [audits/stage2_20261021/normalize.py](../../audits/stage2_20261021/normalize.py) | 새 모듈: C2 명시 경로 정규화 · 입력: 검증된 파일 객체/run 정체성 · 출력: 비교 객체 · 계약 §9 C2. |
| [audits/stage2_20261021/oracle.py](../../audits/stage2_20261021/oracle.py) | 새 모듈: 독립 선택 지표 oracle · 입력: 요청 관측/가정 · 출력: 전수 대조 통계 · 계약 §9 C3. |
| [audits/stage2_20261021/shape_check.py](../../audits/stage2_20261021/shape_check.py) | 새 모듈: 형태·짝 시험·nodeid 검사 · 입력: 저장소/manifest · 출력: 위반 목록 · 계약 §9 C1. |
| [audits/stage2_20261021/shape_rules.py](../../audits/stage2_20261021/shape_rules.py) | 새 모듈: 형태 순수 AST 규칙 · 입력: 경로/소스 · 출력: 위반 목록 · 계약 §9 C1·C4. |
| [audits/stage2_20261021/test_runner.py](../../audits/stage2_20261021/test_runner.py) | 새 모듈: 보호 경로 차단 시험 · 입력: pytest 인자 · 출력: 결과/nodeid manifest · 계약 §9 C1. |
| [configs/analysis/score_variants_v1.yaml](../../configs/analysis/score_variants_v1.yaml) | 후보·단위·PAV·항등 fallback·계단 적용·선택·주장 범위의 닫힌 정책. |
| [configs/sets/kosgd2.yaml](../../configs/sets/kosgd2.yaml) | analysis를 question_risk + score_variants 매핑으로 확장. 선정·분할·task는 불변. |
| [jeveval/IMPACT.md](../../jeveval/IMPACT.md) | WP1~4·수용 도구의 소유·시험·운영 영향 추가. compare family 의미 설명 갱신. |
| [jeveval/README.md](../../jeveval/README.md) | 새 모듈 기능 지도, 기존 의존 방향과 좁은 예외, 등록/replay/역사/감사 명령 사용법. |
| [jeveval/contract/analysis_declarations.py](../../jeveval/contract/analysis_declarations.py) | 새 모듈: 분석 선언 정규화 · 입력: overlay analysis 값 · 출력: 종류별 경로 · 계약 §7-4b·7-4d. |
| [jeveval/contract/set_overlay.py](../../jeveval/contract/set_overlay.py) | 선택 analysis 값을 정규화하여 문자열과 두 종류 매핑 검사. |
| [jeveval/data/items/kosgd_requests.py](../../jeveval/data/items/kosgd_requests.py) | 기존 모듈 docstring의 계약 § 표기만 보완. |
| [jeveval/io/analysis.py](../../jeveval/io/analysis.py) | 첫 fingerprint의 overlay에서 선언 종류별 정책·해시를 검증. |
| [jeveval/io/analysis_artifacts.py](../../jeveval/io/analysis_artifacts.py) | 새 모듈: 확신 등록 증거 I/O · 입력: root/run · 출력: 정책·파일·해시 · 계약 §7-4d. |
| [jeveval/io/archive.py](../../jeveval/io/archive.py) | selective.json이 있으면 선택 수집. |
| [jeveval/io/audit_evidence.py](../../jeveval/io/audit_evidence.py) | 새 모듈: 명시 감사 증거 읽기 · 입력: root/run/선택 경로 · 출력: 출처 포함 감사 줄 · 계약 §7-6. |
| [jeveval/io/auxiliary.py](../../jeveval/io/auxiliary.py) | 새 모듈: 보조 파일 격리 읽기 · 입력: 역사 경로/증거 · 출력: aux 상태 · 계약 §7-4c. |
| [jeveval/io/history.py](../../jeveval/io/history.py) | selective 읽기 실패를 주 errors와 분리한 aux에 보존. |
| [jeveval/io/question_registration.py](../../jeveval/io/question_registration.py) | 정규화 선언 조회로 전환; variant_seal도 시작 표식. |
| [jeveval/io/report_analysis.py](../../jeveval/io/report_analysis.py) | 새 모듈: 보조 절 렌더 · 입력: 검증된 보고 타입 · 출력: Markdown 줄 · 계약 §7-6. |
| [jeveval/io/report_markdown.py](../../jeveval/io/report_markdown.py) | 검증된 ReportSelective·ReportScoreVariants를 독립 절로 렌더. |
| [jeveval/io/set_config.py](../../jeveval/io/set_config.py) | SetEntry.analysis를 정규화하고 모든 선언 파일을 지문 증거에 포함. |
| [jeveval/io/variant_policy.py](../../jeveval/io/variant_policy.py) | 새 모듈: 확신 변형 정책 읽기 · 입력: 정책 경로 · 출력: 검증된 정책/해시 · 계약 §7-4d. |
| [jeveval/run/analysis_gate.py](../../jeveval/run/analysis_gate.py) | 새 모듈: 다중 분석 test gate · 입력: run/동결 선언 · 출력: 순서 있는 봉인 계획 · 계약 §7-4d. |
| [jeveval/run/auxiliary_report.py](../../jeveval/run/auxiliary_report.py) | 새 모듈: 보조 보고 검증 조립 · 입력: 역사/주 상태 · 출력: 독립 보조 절 · 계약 §7-4c·7-4d. |
| [jeveval/run/cli.py](../../jeveval/run/cli.py) | score-variants threshold/risk/--history 및 반복 --audit-evidence 등록. |
| [jeveval/run/cmd_compare.py](../../jeveval/run/cmd_compare.py) | family spec을 population·관측·qid·F1 호출까지 전달. 실제 set seed 유지. |
| [jeveval/run/cmd_replay.py](../../jeveval/run/cmd_replay.py) | 등록 test 복사 전 동일 test gate로 봉인; 미등록 경로는 유지. |
| [jeveval/run/cmd_report.py](../../jeveval/run/cmd_report.py) | family 분해 플래그·명시 감사 선택·보조 보고 조립 연결. |
| [jeveval/run/cmd_score.py](../../jeveval/run/cmd_score.py) | spec 전달, selective/1 추가; 전부 직렬화 검사 뒤 쓰기. 비용 읽기를 별도 함수로 분리. |
| [jeveval/run/cmd_score_variants.py](../../jeveval/run/cmd_score_variants.py) | 새 모듈: 확신 변형 명령 · 입력: run/threshold 또는 risk/history · 출력: 보조 파일 · 계약 §7-4d. |
| [jeveval/run/fingerprint.py](../../jeveval/run/fingerprint.py) | 각 선언의 종류와 정책을 검증한 뒤 evidence_paths 전체 결합. |
| [jeveval/run/gate.py](../../jeveval/run/gate.py) | 전부 선검사 뒤 question→variant→주 seal 순서로 쓰기. |
| [jeveval/run/length.py](../../jeveval/run/length.py) | types 공통 길이 경계 사용. None 거부 계약 유지. |
| [jeveval/run/question_gate.py](../../jeveval/run/question_gate.py) | 분석 파일 존재 대신 정규화 question_risk 선언으로 gate 선택. |
| [jeveval/run/variant_calculation.py](../../jeveval/run/variant_calculation.py) | 새 모듈: 변형 계산 조립 · 입력: 복원 단계 · 출력: dev 정책/test 표 · 계약 §7-4d. |
| [jeveval/run/variant_registration.py](../../jeveval/run/variant_registration.py) | 새 모듈: 확신 등록 사슬 검사 · 입력: 증거/dev 재계산 · 출력: 등록 상태/봉인 · 계약 §7-4d. |
| [jeveval/score/audit_selection.py](../../jeveval/score/audit_selection.py) | 새 모듈: 감사 증거 적격 판정 · 입력: 읽힌 감사/fingerprint · 출력: 규칙·연결 여부 · 계약 §7-6. |
| [jeveval/score/bootstrap.py](../../jeveval/score/bootstrap.py) | tool/set 이름 의미 판정 대신 명시 f1_defined. RNG 문자열 불변. |
| [jeveval/score/isotonic.py](../../jeveval/score/isotonic.py) | 새 모듈: PAV 단조 보정 · 입력: 점수/정오 관측 · 출력: 계단 보정기/점수 · 계약 §7-4d. |
| [jeveval/score/observations.py](../../jeveval/score/observations.py) | FC 제외·KorFin pooled를 전달받은 spec으로 결정. |
| [jeveval/score/population.py](../../jeveval/score/population.py) | 셋별 의미를 spec으로 전환; qstats는 명시 f1_defined; 기존 결과 구조 유지. |
| [jeveval/score/power.py](../../jeveval/score/power.py) | 새 모듈: 조건부 CP 통과 확률 · 입력: 관측 n/τ/가정 위험 · 출력: 확률 · 계약 §7-4c. |
| [jeveval/score/risk.py](../../jeveval/score/risk.py) | risk_mix로 spec 전달. 주 CP·상태·risk/1 계산 불변. |
| [jeveval/score/risk_mix.py](../../jeveval/score/risk_mix.py) | service/stratum 분포를 spec으로 결정; 공유 길이 상수·빈 Item None 유지. |
| [jeveval/score/selective.py](../../jeveval/score/selective.py) | 새 모듈: 선택적 예측 통계 · 입력: test 대표 outcome · 출력: RC/부분 AURC/AUROC · 계약 §7-4c. |
| [jeveval/score/selective_artifact.py](../../jeveval/score/selective_artifact.py) | 새 모듈: 보조 통계 파일 계약 · 입력: 집계/출처 · 출력: selective/1·검증 · 계약 §7-4c. |
| [jeveval/score/set_metrics.py](../../jeveval/score/set_metrics.py) | 새 모듈: family 지표 의미 · 입력: family 이름 · 출력: 불변 MetricSpec · 계약 §7-6. |
| [jeveval/score/variant_risk.py](../../jeveval/score/variant_risk.py) | 새 모듈: 동결 확신 정책 적용 · 입력: test 후보/선택 · 출력: τ별 CP 셀 · 계약 §7-4d. |
| [jeveval/score/variant_scores.py](../../jeveval/score/variant_scores.py) | 새 모듈: 확신 후보 투영 · 입력: 요청/질문 단위/보정기 · 출력: 후보별 요청 점수 · 계약 §7-4d. |
| [jeveval/score/variant_selection.py](../../jeveval/score/variant_selection.py) | 새 모듈: dev 후보 선택 · 입력: 후보별 dev 요청 · 출력: τ별 동결 선택 · 계약 §7-4d. |
| [jeveval/types/history.py](../../jeveval/types/history.py) | 주 오류와 별도인 aux 상태 필드. |
| [jeveval/types/kosgd_requests.py](../../jeveval/types/kosgd_requests.py) | 기존 모듈 docstring의 계약 § 표기만 보완. |
| [jeveval/types/length_buckets.py](../../jeveval/types/length_buckets.py) | 새 모듈: 길이 구간 경계 · 입력: 없음 · 출력: 공유 불변 경계 · 계약 §4-3·7-4. |
| [jeveval/types/report.py](../../jeveval/types/report.py) | ReportSelective·ReportScoreVariants 및 ReportVariant 선택 필드. |
| [jeveval/types/set_config.py](../../jeveval/types/set_config.py) | analysis 정규화 매핑 타입. |
| [ops/status.py](../../ops/status.py) | kosgd2 두 변형·독립 selective 파일 유무 열 추가. |
| [tests/audits/stage2_support.py](../../tests/audits/stage2_support.py) | 시험: C2 합성 run 복제 · 입력: 완료 Harness · 출력: 유효한 새 provenance · 계약 §9 C2. |
| [tests/audits/test_check_oracle.py](../../tests/audits/test_check_oracle.py) | 시험: oracle CLI 조립 · 입력: 합성 완료 run · 출력: 원문 없는 대조 결과 · 계약 §9 C3. |
| [tests/audits/test_compare_evidence.py](../../tests/audits/test_compare_evidence.py) | 시험: C2 증거 선검사 · 입력: 합성 run/손상 · 출력: 해시·크기 거부 · 계약 §9 C2. |
| [tests/audits/test_compare_runs.py](../../tests/audits/test_compare_runs.py) | 시험: C2 허용 필드 회귀 · 입력: 합성 직접/파생 run · 출력: 수치 변경 실패 · 계약 §9 C2. |
| [tests/audits/test_normalize.py](../../tests/audits/test_normalize.py) | 시험: 명시 경로 정규화 · 입력: 허용/비허용 필드 · 출력: 보존 범위 · 계약 §9 C2. |
| [tests/audits/test_oracle.py](../../tests/audits/test_oracle.py) | 시험: 독립 oracle 대조 · 입력: 무효/동점/경계 · 출력: 구현과 1e-12 일치 · 계약 §9 C3. |
| [tests/audits/test_shape_check.py](../../tests/audits/test_shape_check.py) | 시험: nodeid/skip 보존 검사 · 입력: 수집 manifest · 출력: 회귀 검출 · 계약 §9 C1. |
| [tests/audits/test_shape_rules.py](../../tests/audits/test_shape_rules.py) | 시험: AST 경계 공격 · 입력: 합성 Python · 출력: 길이/의존/효과 거부 · 계약 §9 C1. |
| [tests/audits/test_test_runner.py](../../tests/audits/test_test_runner.py) | 시험: 보호 시험 실행기 계약 · 입력: runner AST · 출력: 보호 경로 고정 · 계약 §9 C1. |
| [tests/contract/test_analysis_declarations.py](../../tests/contract/test_analysis_declarations.py) | 시험: 다중 선언 정규화 · 입력: 구 문자열/매핑 · 출력: 종류·경로 거부 · 계약 §7-4d. |
| [tests/contract/test_stages.py](../../tests/contract/test_stages.py) | 시험: 단계 소유 단일화 · 입력: 원 셋/별칭 · 출력: 기존 단계와 AST 경계 · 계약 §6-1. |
| [tests/io/test_analysis_artifacts.py](../../tests/io/test_analysis_artifacts.py) | 시험: 변형 증거 읽기 · 입력: 합성 run/손상 · 출력: 상태와 쓰기 보호 · 계약 §7-4d. |
| [tests/io/test_audit_evidence.py](../../tests/io/test_audit_evidence.py) | 시험: 감사 존재/연결 검사 · 입력: 합성 증거 · 출력: 보고 범위 · 계약 §7-6. |
| [tests/io/test_auxiliary.py](../../tests/io/test_auxiliary.py) | 시험: 보조 격리 행렬 · 입력: 선택 파일 손상 · 출력: 주 역사/인증/비교 불변 · 계약 §7-4c. |
| [tests/io/test_report_analysis.py](../../tests/io/test_report_analysis.py) | 시험: 보조 절 구분 · 입력: 보고 타입 · 출력: 제목/조건부 설명 · 계약 §7-6. |
| [tests/io/test_set_config.py](../../tests/io/test_set_config.py) | 시험: 설정 조회 격리 · 입력: 합성 공용/overlay · 출력: 단일 읽기·전체 거부 · 계약 판 5 보정 1 §9. |
| [tests/io/test_variant_policy.py](../../tests/io/test_variant_policy.py) | 시험: 닫힌 변형 정책 · 입력: manifest/종류 혼동 · 출력: 해시/거부 · 계약 §7-4d. |
| [tests/ops/test_readonly.py](../../tests/ops/test_readonly.py) | 시험: status/dry-run 무전송·무쓰기. 입력: 합성 split/기록. 출력: 트리 바이트와 mtime 동일 · 계약 §5-5. |
| [tests/run/analysis_support.py](../../tests/run/analysis_support.py) | 시험: 다중 선언 합성 run · 입력: tmp_path/선언 종류 · 출력: dev 완료 Harness · 계약 §9. |
| [tests/run/test_analysis_gate.py](../../tests/run/test_analysis_gate.py) | 시험: 다중 봉인 행렬 · 입력: 선언/중단/손상 · 출력: 선검사와 재개 거부 · 계약 §7-4d. |
| [tests/run/test_auxiliary_report.py](../../tests/run/test_auxiliary_report.py) | 시험: 보조 보고 검증 · 입력: 새/옛/손상 합성 run · 출력: 독립 절 · 계약 §7-6. |
| [tests/run/test_cli.py](../../tests/run/test_cli.py) | 시험: 확신 CLI 전달 · 입력: 하위 명령 · 출력: 조립 인자 · 계약 §7-4d. |
| [tests/run/test_cmd_replay.py](../../tests/run/test_cmd_replay.py) | 시험: replay 명령 짝 시험 · 입력: 합성 출처/대상 · 출력: 검사·쓰기 순서·멱등 · 계약 §5-5c. |
| [tests/run/test_cmd_score.py](../../tests/run/test_cmd_score.py) | 시험: score 명령 경계 · 입력: 합성 단계 · 출력: 집계·쓰기 순서 · 계약 §7. |
| [tests/run/test_cmd_score_variants.py](../../tests/run/test_cmd_score_variants.py) | 시험: 확신 명령 통합 · 입력: 등록/역사 합성 run · 출력: 주 바이트 보존 · 계약 §7-4d. |
| [tests/run/test_stage_regression.py](../../tests/run/test_stage_regression.py) | 시험: 역사·단계 고정 회귀 · 입력: d41e8b9 합성 관측 · 출력: 현행 결과 동치 · 계약 §9 C6. |
| [tests/run/test_variant_calculation.py](../../tests/run/test_variant_calculation.py) | 시험: dev 적합과 test 적용 분리 · 입력: 합성 단계 · 출력: 동결 불변 · 계약 §7-4d. |
| [tests/run/test_variant_registration.py](../../tests/run/test_variant_registration.py) | 시험: 변형 등록 사슬 · 입력: 합성 봉인/복사 · 출력: 등록/손상 · 계약 §7-4d. |
| [tests/score/population_support.py](../../tests/score/population_support.py) | 시험: 모집단 합성 입력 · 입력: 질문/예측 · 출력: Item/final/outcome · 계약 §7-6 시험. |
| [tests/score/test_audit_selection.py](../../tests/score/test_audit_selection.py) | 시험: 감사 적격 선택 · 입력: 사전/사후 합성 증거 · 출력: 정확 tuple 연결 · 계약 §7-6. |
| [tests/score/test_bootstrap.py](../../tests/score/test_bootstrap.py) | 시험: paired 묶음 재표집 검증 · 입력: 합성 outcome/Observation · 출력: 점추정·CI · 계약 §7-7. |
| [tests/score/test_isotonic.py](../../tests/score/test_isotonic.py) | 시험: 순수 PAV 검증 · 입력: 동점/역전/희소 · 출력: 가중 블록/계단 · 계약 §7-4d. |
| [tests/score/test_observations.py](../../tests/score/test_observations.py) | 시험: 성공 질문 F1 입력 · 입력: 합성 Item/outcome · 출력: 마스크/고정 칸/pooled · 계약 §7-2·7-7. |
| [tests/score/test_power.py](../../tests/score/test_power.py) | 시험: 조건부 검정력 경계 · 입력: n/τ/r · 출력: 이항 oracle 일치 · 계약 §7-4c. |
| [tests/score/test_risk_mix.py](../../tests/score/test_risk_mix.py) | 시험: 채점→위험 분포 경계 · 입력: fixture·합성 질문 · 출력: 분모·분포 검증 · 계약 §7-3~4. |
| [tests/score/test_selective.py](../../tests/score/test_selective.py) | 시험: 선택적 통계 경계 · 입력: 합성 대표 · 출력: 동점/분모/적분 · 계약 §7-4c. |
| [tests/score/test_selective_artifact.py](../../tests/score/test_selective_artifact.py) | 시험: 보조 집계 계약 · 입력: 합성 집계/변조 · 출력: 정확한 거부 · 계약 §7-4c. |
| [tests/score/test_set_metrics.py](../../tests/score/test_set_metrics.py) | 시험: family 의미 분리 · 입력: 별칭/비표준 ID/빈 표본 · 출력: 의미 승계 · 계약 §7-6. |
| [tests/score/test_variant_risk.py](../../tests/score/test_variant_risk.py) | 시험: 동결 후보 test 적용 · 입력: 고정 정책/시험 · 출력: 주 CP 경계 동일 · 계약 §7-4d. |
| [tests/score/test_variant_scores.py](../../tests/score/test_variant_scores.py) | 시험: 후보 단위 의미 · 입력: 성공/결측/칸 묶음 · 출력: min 동일/곱 · 계약 §7-4d. |
| [tests/score/test_variant_selection.py](../../tests/score/test_variant_selection.py) | 시험: 후보 선택 경계 · 입력: dev 후보 · 출력: 고정 동점/NO_THRESHOLD · 계약 §7-4d. |
| [tests/types/test_length_buckets.py](../../tests/types/test_length_buckets.py) | 시험: 공유 길이 경계 · 입력: 경계/미측정 · 출력: wrapper 계약 보존 · 계약 §4-3. |

## 검증 명령·결과

실행 Python: `../foundation_model_test_non_thinking/.venv/bin/python`(저장소 기준 상대 경로).
모든 pytest는 `PYTHONDONTWRITEBYTECODE=1`, `-B`, `-p no:cacheprovider`와 보호 test_runner를 사용했다.

- 변경 영역 `tests/score tests/io tests/contract tests/run tests/audits tests/types`: 2,053 통과, 기존 localhost 시험 1개는 network guard로 실행 불가.
- 전체 tests에서 client/run live 두 파일 제외: 2,669 통과, 기존 T0 localhost 시험 6개는 같은 제한으로 실행 불가.
- 마지막 수정의 `test_compare_evidence.py test_compare_runs.py test_oracle.py test_variant_policy.py`: 21 통과.
- 최종 전체 오프라인 시험: **2,669 통과, 실패/skip/xfail 0**, 119.65초. live 파일 3개 제외.
- 제외 파일 중 T0 무소켓 시험을 별도로 실행: **3 통과, 6 deselected**. 실행 가능한 총 2,672개 통과. 네트워크가 필요한 기존 25개는 미실행.
- 전체 수집: 기존 2,557 → 현재 2,697 nodeid, 기존 삭제 0. 신규 140개.
- `shape_check.py --before /tmp/jev-stage2-baseline.json --after /tmp/jev-stage2-collected-final.json`: 0위반, 새 skip/xfail 0.

실 run C2·C3 및 새 감사 실행은 운영자에게 남긴 수용 작업이다. 이 구현 작업에서는 실행하지 않았다.
SPEC_AMBIGUOUS의 확정 사항과 실행 명령은 [README](README.md)에 있다.

최종 실행 명령(아래 python은 위 venv 경로):

```sh
PYTHONDONTWRITEBYTECODE=1 python -B audits/stage2_20261021/test_runner.py tests -q -p no:cacheprovider \
  --basetemp=/tmp/jev-stage2-offline-complete \
  --ignore=tests/client/test_http_live.py --ignore=tests/run/test_executor_live.py --ignore=tests/t0_io/test_live.py
PYTHONDONTWRITEBYTECODE=1 python -B audits/stage2_20261021/test_runner.py tests/t0_io/test_live.py \
  -k 'not test_cli_all_stages_with_loopback' -q -p no:cacheprovider --basetemp=/tmp/jev-stage2-t0-no-socket
PYTHONDONTWRITEBYTECODE=1 JEV_NODEIDS_OUT=/tmp/jev-stage2-collected-final.json \
  python -B audits/stage2_20261021/test_runner.py tests --collect-only -q -p no:cacheprovider
python -B audits/stage2_20261021/shape_check.py \
  --before /tmp/jev-stage2-baseline.json --after /tmp/jev-stage2-collected-final.json
```

`git diff --check`는 0 오류이며 기존 `audits/audit_v4/out`의 git diff도 없다.
커밋하지 않았다. 기존 결과·보고서·감사 산출물은 수정하지 않았다.
