# 구현 인계 — 서버 없는 계획 2판

## 변경 파일의 책임

| 파일 | 책임 |
|---|---|
| [JEV_TEST_PLAN.md](../../JEV_TEST_PLAN.md) | vLLM 현행 버전 사실 정리 |
| [P1_CONTRACT.md](../../P1_CONTRACT.md) | 구현 상태 두 줄 정리와 §9c 수용/운영 계약; 역사 블록 보존 |
| [audits/serverless_20261021/IMPLEMENTATION.md](../../audits/serverless_20261021/IMPLEMENTATION.md) | 파일 책임과 재사용/새 함수 검색 근거 |
| [audits/serverless_20261021/README.md](../../audits/serverless_20261021/README.md) | 수용 도구 실행법·범위·제약 |
| [audits/serverless_20261021/contract_map_check.py](../../audits/serverless_20261021/contract_map_check.py) | 보존 SHA/원문 앵커/현행 제목/지도 행 검사 |
| [audits/serverless_20261021/dup_check.py](../../audits/serverless_20261021/dup_check.py) | Git base와 현재 코드의 새 중복 그룹 비교 |
| [audits/serverless_20261021/function_shapes.py](../../audits/serverless_20261021/function_shapes.py) | AST 인자/지역 이름 정규화 및 함수 본문 해시 |
| [audits/serverless_20261021/t0_compare.py](../../audits/serverless_20261021/t0_compare.py) | 독립 worker 둘의 실제 SHA 연결·산출물/help 비교 |
| [audits/serverless_20261021/t0_worker.py](../../audits/serverless_20261021/t0_worker.py) | 선택한 한 트리에서 기존 가짜 참조로 T0 다섯 단계 실행 |
| [audits/stage2_20261021/compare_runs.py](../../audits/stage2_20261021/compare_runs.py) | 기존 비교기에 엄격한 감사 줄 전용 모드 추가 |
| [audits/stage2_20261021/normalize.py](../../audits/stage2_20261021/normalize.py) | 기존 기본값 유지, 감사 줄·정확 바이트 보존 옵션 |
| [audits/stage2_20261021/shape_check.py](../../audits/stage2_20261021/shape_check.py) | 새 도구/ops 상태기의 형태와 짝 시험 검사 |
| [audits/stage2_20261021/test_runner.py](../../audits/stage2_20261021/test_runner.py) | 기존 데이터/네트워크 접근 차단기를 worker와 공유 |
| [jeveval/IMPACT.md](../../jeveval/IMPACT.md) | 변경 영향·불변 경계·짝 시험 지도 |
| [jeveval/README.md](../../jeveval/README.md) | 새 기능과 기존 재사용 경로 지도 |
| [jeveval/io/audit_evidence.py](../../jeveval/io/audit_evidence.py) | 출처/원천 기록 읽기와 주장 범위를 구분한 감사 문구 |
| [jeveval/run/cli.py](../../jeveval/run/cli.py) | 모든 명령에 handler.run 공통 호출 |
| [jeveval/run/cmd_run.py](../../jeveval/run/cmd_run.py) | 직접/파생 resume 선검사를 읽기 전용 함수로 공유 |
| [jeveval/run/cmd_t0.py](../../jeveval/run/cmd_t0.py) | 다섯 단계별 진입점과 공통 입력 검증; 호환 dispatch |
| [jeveval/run/history_check.py](../../jeveval/run/history_check.py) | 기존 파생 출처 순수 검사를 공유 함수로 호출 |
| [jeveval/score/audit_selection.py](../../jeveval/score/audit_selection.py) | 직접/파생 감사 선택; 출처 검사는 derived_provenance에 위임 |
| [ops/README.md](../../ops/README.md) | kosgd2 순서·재개·손상 정지 운영 설명 |
| [ops/kosgd2_steps.sh](../../ops/kosgd2_steps.sh) | 단계 순서와 공통 action/skip 처리 후 기존 실행 함수 호출 |
| [ops/lane.sh](../../ops/lane.sh) | 기존 진입점에서 kosgd2 순서 파일 선택 |
| [ops/lib.sh](../../ops/lib.sh) | kosgd2 task/판/파생 식별·OPTIONAL_SETS; 기존 재시도 유지 |
| [ops/registration_status.py](../../ops/registration_status.py) | 등록 증거 읽기와 순수 create/skip/stop 결정 |
| [ops/status.py](../../ops/status.py) | 질문/변형 seal 존재 관측 열 |
| [tests/audits/test_compare_runs.py](../../tests/audits/test_compare_runs.py) | 정확한 파생 감사 변경 수와 나머지 바이트 불변 |
| [tests/audits/test_contract_map_check.py](../../tests/audits/test_contract_map_check.py) | 여섯 블록·fence·Unicode·누락/중복/대상 검사 |
| [tests/audits/test_dup_check.py](../../tests/audits/test_dup_check.py) | 중복 성장·base object 읽기·보호 범위·shell 문법 |
| [tests/audits/test_function_shapes.py](../../tests/audits/test_function_shapes.py) | 인자/지역/중첩 scope 정규화와 전역/속성 보존 |
| [tests/audits/test_normalize.py](../../tests/audits/test_normalize.py) | 감사 줄/줄 끝 보존 및 기존 정규화 호환 |
| [tests/audits/test_shape_check.py](../../tests/audits/test_shape_check.py) | 새 범위/짝 시험 규칙 |
| [tests/audits/test_t0_compare.py](../../tests/audits/test_t0_compare.py) | SHA 연결 선검사·정확한 두 필드 정규화·scratch 경계 |
| [tests/audits/test_t0_worker.py](../../tests/audits/test_t0_worker.py) | 기존 가짜 runtime의 독립 프로세스 실행 |
| [tests/io/test_audit_evidence.py](../../tests/io/test_audit_evidence.py) | 파생 PASS 문구와 출처/원천/설정 음성 행렬 |
| [tests/ops/test_kosgd2_steps.py](../../tests/ops/test_kosgd2_steps.py) | 명령 순서·실패 정지·STOP·lock; 기존 ops harness 재사용 |
| [tests/ops/test_registration_status.py](../../tests/ops/test_registration_status.py) | threshold/seal 중단 행렬·손상/완료 기록 검사·무쓰기 |
| [tests/ops/test_status.py](../../tests/ops/test_status.py) | 두 등록 seal의 존재만 관측하며 유효성은 주장하지 않음 |
| [tests/run/analysis_support.py](../../tests/run/analysis_support.py) | 기존 선언 준비기에 모델 종류·질문 방식·시작 여부 인자 |
| [tests/run/cli_support.py](../../tests/run/cli_support.py) | 기존 Harness에 question_scoring 주입 |
| [tests/run/test_cmd_t0.py](../../tests/run/test_cmd_t0.py) | 단계별 유효 인자만 허용 |
| [tests/run/test_serverless_fingerprint.py](../../tests/run/test_serverless_fingerprint.py) | 코드 변경 시 resume/compare 거부, 역사/report 허용 |
| [tests/run/test_serverless_pipeline.py](../../tests/run/test_serverless_pipeline.py) | 세 호출 방식에서 두 판 등록 사슬과 재개 불변 |
| [tests/score/test_audit_selection.py](../../tests/score/test_audit_selection.py) | 직접/파생 감사 범위 순수 선택 |
| [tests/t0_io/test_live.py](../../tests/t0_io/test_live.py) | 기존 실패 주입을 CLI의 단계별 진입점에 연결; nodeid 유지 |
| [jeveval/score/derived_provenance.py](../../jeveval/score/derived_provenance.py) | 파생 출처·원천 호출 SHA·원천 정체성 순수 검사 |
| [tests/score/test_derived_provenance.py](../../tests/score/test_derived_provenance.py) | 기존 역사/감사 시험을 유지하고 순수 검사 경계를 추가 확인 |
| [jeveval/run/variant_registration.py](../../jeveval/run/variant_registration.py) | 기존 dev 재계산과 등록 판정을 check_development로 공유 |
| [jeveval/run/analysis_gate.py](../../jeveval/run/analysis_gate.py) | 공통 dev 검증 호출; 선검사·봉인 계획 순서 유지 |
| [tests/run/test_variant_registration.py](../../tests/run/test_variant_registration.py) | 기존 nodeid에서 공통 검증의 정상/손상 결과 확인 |
| [tests/run/test_cli.py](../../tests/run/test_cli.py) | T0도 공통 handler.run으로 전달되는지 확인 |

## 재사용한 기존 함수

다음 줄 번호는 현재 작업 트리 기준이다. 새 결정 로직과 기존 로직의 이동/조립을 구분한다.

| 기존 함수·위치 | 재사용 방식 |
|---|---|
| `jeveval/score/audit_selection.py:10` `select_audit_evidence` | 직접 선택과 파생 원천 선택의 적격/규칙/호출 PASS 검사 |
| `jeveval/run/history_check.py:74` `_origins` | 내부의 stage 출처 검사만 check_derived_origin으로 이동; 역사 호출도 공유 |
| `jeveval/io/derived_stage.py:19` `read_derived_stage` | 파생 및 full의 marker/final/attempt/tail 판독 |
| `jeveval/run/derived_resume.py:25` `resume_derived` | 완료 파생 단계의 생략 전 원천 기반 재구성 검증 |
| `jeveval/run/resume_check.py:6` `check_resume` | 직접 단계의 기존 계획/attempt/final 선검사 |
| `jeveval/run/cmd_threshold.py:10` `recompute` | 일반 threshold의 dev 재계산 검증 |
| `jeveval/io/question_registration.py:26` `read` | 질문 등록 증거 읽기 |
| `jeveval/io/analysis_artifacts.py:13` `read` | 변형 등록 증거 읽기 |
| `jeveval/run/question_registration.py:38` `check` | 질문 등록 상태 검사 |
| `jeveval/run/variant_registration.py:37` `check` | 변형 등록 상태 검사 |
| `jeveval/score/question_outcomes.py:35` `observations` | 질문 dev 관측 계산 |
| `jeveval/score/question_risk.py:39` `thresholds` | 질문 dev threshold 재계산 |
| `jeveval/run/variant_calculation.py:10` `development` | 변형 dev threshold 재계산 |
| `jeveval/run/seal.py:27` `check_seal` | 주 seal 검증 |
| `jeveval/io/t0_inputs.py:94` `freeze` | T0 inputs 동결 |
| `jeveval/io/t0_inputs.py:123` `load` | T0 저장 입력 읽기 |
| `jeveval/io/t0_chain.py:66` `fingerprint` | T0 저장 입력 지문 확인 |
| `jeveval/run/t0_reference.py:71` `execute` | reference 단계 구현 |
| `jeveval/run/t0_server.py:23` `execute` | server 단계 구현 |
| `jeveval/run/t0_evaluate.py:23` `tolerance` | tolerance 단계 구현 |
| `jeveval/run/t0_evaluate.py:50` `evaluate` | judge 단계 구현 |
| `tests/t0_io/support.py:27` `setup` | 기존 fixture factory와 fake runtime |
| `tests/t0_io/support.py:72` `inputs` | 기존 합성 T0 inputs 호출 |
| `tests/t0_io/support.py:77` `stage` | 기존 합성 T0 stage 호출 |
| `tests/t0_io/support.py:81` `fake_post` | 고정 AttemptResult 응답 |
| `tests/run/analysis_support.py:10` `prepared` | 등록 선언·합성 dev 준비; 옵션만 일반화 |
| `tests/run/analysis_support.py:27` `thresholds` | 두 등록 threshold 생성 |
| `tests/run/cli_support.py:133` `post` | Harness의 systemone/B1 합성 응답 |
| `audits/stage2_20261021/normalize.py:44` `report` | 감사 줄 보존 옵션 추가; 복제하지 않음 |
| `audits/stage2_20261021/compare_evidence.py:20` `parse` | 비교 JSON 판독 |
| `audits/publish_check/git_objects.py:6` `git` | 안전한 argv Git object 조회 |
| `audits/publish_check/git_objects.py:13` `resolve` | base revision 해석 |
| `jeveval/io/hashes.py:54` `code_sha256` | 선택한 소스의 실제 코드 지문 |
| `jeveval/io/run_files.py:22` `json_bytes` | 정규화 뒤 기존 canonical JSON 형식 |

`tests/ops/conftest.py`의 기존 가짜 PY/명령 로그·`test_live_lane_lock_and_stop_now`를 그대로 재사용한다.
`ops/lib.sh`의 step/run_stage/finish·lane의 lock/STOP 경계도 새 구현으로 복사하지 않는다.

## 새 함수별 검색과 결정

검색 범위: jeveval, ops, audits의 Python/shell과 tests의 support/conftest 및 관련 짝 시험.
아래 검색어를 rg로 대조했다. “없음”은 같은 책임의 기존 함수가 없다는 뜻이며 범용 main/AST visitor 이름의 부재를 뜻하지 않는다.
이동한 로직은 새 구현이 아니라 위 기존 함수를 추출/호출했다. 새 시험은 기존 fixture를 재사용해 추가 계약만 검증한다.

| 파일·새 함수(중첩/메서드 포함) | 검색어·판정 |
|---|---|
| `audits/serverless_20261021/contract_map_check.py` — `extract_preserved_blocks:26`, `index_current_sections:44`, `verify_source_anchor:66`, `table_rows:73`, `check_mapping_targets:87`, `check:107`, `main:138` | `preserved_blocks / source_anchor / mapping_targets / current_sections`: 같은 검사기 없음. Git 읽기는 git 재사용. |
| `audits/serverless_20261021/dup_check.py` — `selected:16`, `sources:30`, `groups:48`, `new_groups:66`, `check:73`, `main:79` | `duplicate / body_hash / new_groups / ls-tree`: 함수 중복 비교기 없음. Git 조회/resolve 재사용. |
| `audits/serverless_20261021/function_shapes.py` — `without_docstring:8`, `Bindings.__init__:17`, `Bindings.bind:25`, `Bindings.visit_Name:29`, `Bindings.visit_FunctionDef:33`, `Bindings.visit_Lambda:39`, `Bindings.visit_Global:42`, `Bindings.visit_Nonlocal:45`, `Bindings.visit_ListComp:48`, `Bindings.visit_ExceptHandler:55`, `Bindings.visit_alias:59`, `Bindings.visit_MatchAs:62`, `Bindings.visit_MatchMapping:68`, `scope_names:73`, `Normalize.__init__:83`, `Normalize.visit_Name:87`, `Normalize.visit_arg:91`, `Normalize.visit_ExceptHandler:95`, `Normalize.visit_FunctionDef:99`, `Normalize.visit_Lambda:113`, `Normalize.visit_alias:119`, `Normalize.visit_Nonlocal:124`, `Normalize.visit_ListComp:128`, `Normalize.visit_MatchAs:141`, `Normalize.visit_MatchMapping:147`, `body_hash:152`, `functions:161`, `functions.walk:164` | `NodeTransformer / ast.dump / scope_names / body_hash`: AST 지역명 정규화기 없음. shape_rules는 형태 규칙이므로 역할이 다름. |
| `audits/serverless_20261021/t0_compare.py` — `normalized_outputs:21`, `compare:47`, `main:65` | `normalized_outputs / fingerprint_sha256 / independent`: 독립 두 트리의 제한된 필드 바이트 비교기 없음. code_sha256/json_bytes/parse 재사용. |
| `audits/serverless_20261021/t0_worker.py` — `execute:15`, `main:47` | `fake_post / setup / t0 / subprocess`: 단계/응답은 기존 support 재사용. 한 트리 독립 프로세스 진입점 없음. |
| `audits/stage2_20261021/compare_runs.py` — `compare_audit_report:62`, `report_result:85` | `compare_audit_report / report / 미완·한계`: 감사 변경 줄 수·문구 전용 판정 없음. normalize.report를 확장해 공유. |
| `audits/stage2_20261021/test_runner.py` — `protect:9`, `protect.guard:13` | `addaudithook / guard / protect`: 기존 main의 guard를 추출. 새로운 접근 차단기 복제 없음. |
| `jeveval/io/audit_evidence.py` — `read_derived_provenance:51` | `derived_from / read_derived_stage / _origins`: 판독/출처 검사는 재사용. 감사용 전체 stage 원천 결합 함수 없음. |
| `jeveval/run/cmd_run.py` — `read_resume_inputs:46` | `check_resume / resume_derived / _derived`: 기존 run 분기를 추출. allow_tail 기본값으로 기존 동작 유지. |
| `jeveval/run/cmd_t0.py` — `run_inputs:41`, `load_verified_t0_bundle:59`, `run_reference:68`, `run_server:82`, `run_tolerance:89`, `run_judge:94`, `stage_handler:100` | `t0_reference / t0_server / t0_evaluate / stage_handler`: 단계 구현은 전부 재사용. 합집합 run에서 단계별 조립과 공통 읽기를 추출. |
| `jeveval/score/audit_selection.py` — `select_direct_audit_evidence:37`, `select_derived_audit_evidence:43` | `_origins / derived_from / select_audit_evidence / request_sha256`: 직접 선택은 기존 함수 조립. 출처·호출 SHA·원천 정체성 검사는 derived_provenance로 이동. |
| `ops/registration_status.py` — `next_registration_action:19`, `_threshold_states:24`, `read_registration_state:53`, `main:91` | `registration / check / recompute / check_seal / check_resume`: 기존 검증기 재사용. ops create/skip/stop 상태 조립기는 없음. |
| `tests/audits/test_compare_runs.py` — `test_audit_only_report_checks_exactly_three_changed_lines:48` | `test_compare_runs / test_audit_only_report_checks_exactly_three_changed_lines`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/audits/test_contract_map_check.py` — `test_repository_map_preserves_six_blocks_and_all_tables:10`, `test_fenced_headings_are_not_current_and_payload_is_exact:17`, `test_anchor_uses_unicode_characters_and_full_preserved_excerpt:25`, `test_missing_duplicate_rows_and_targets_fail:34` | `test_contract_map_check / test_repository_map_preserves_six_blocks_and_all_tables / test_fenced_headings_are_not_current_and_payload_is_exact / test_anchor_uses_unicode_characters_and_full_preserved_excerpt / test_missing_duplicate_rows_and_targets_fail`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/audits/test_dup_check.py` — `test_groups_and_existing_duplicate_growth:9`, `test_protected_paths_and_scope:18`, `test_base_is_read_without_checkout_and_new_copy_fails:25`, `test_base_is_read_without_checkout_and_new_copy_fails.git:26`, `test_repeated_same_name_growth_and_bash_function_syntax:37` | `test_dup_check / test_groups_and_existing_duplicate_growth / test_protected_paths_and_scope / test_base_is_read_without_checkout_and_new_copy_fails / test_base_is_read_without_checkout_and_new_copy_fails.git / test_repeated_same_name_growth_and_bash_function_syntax`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/audits/test_function_shapes.py` — `test_arguments_locals_and_docstrings_are_normalized:6`, `test_globals_and_attributes_are_not_normalized:14`, `test_method_qualified_names_and_lines_are_reported:20`, `test_nested_scope_import_alias_and_comprehension_bindings:25` | `test_function_shapes / test_arguments_locals_and_docstrings_are_normalized / test_globals_and_attributes_are_not_normalized / test_method_qualified_names_and_lines_are_reported / test_nested_scope_import_alias_and_comprehension_bindings`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/audits/test_normalize.py` — `test_report_can_preserve_audits_and_exact_lines:23` | `test_normalize / test_report_can_preserve_audits_and_exact_lines`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/audits/test_shape_check.py` — `test_new_tools_and_ops_have_explicit_shape_and_pairing_scope:14` | `test_shape_check / test_new_tools_and_ops_have_explicit_shape_and_pairing_scope`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/audits/test_t0_compare.py` — `artifacts:9`, `test_only_two_fields_normalized_after_actual_link_validation:22`, `test_scratch_cannot_be_existing_or_inside_source:37` | `test_t0_compare / artifacts / test_only_two_fields_normalized_after_actual_link_validation / test_scratch_cannot_be_existing_or_inside_source`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/audits/test_t0_worker.py` — `test_worker_uses_existing_fake_runtime_without_network:10` | `test_t0_worker / test_worker_uses_existing_fake_runtime_without_network`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/io/test_audit_evidence.py` — `derived_audit:71`, `test_derived_source_link_keeps_hypothetical_scope:89`, `test_derived_unverified_provenance_never_promotes:105` | `test_audit_evidence / derived_audit / test_derived_source_link_keeps_hypothetical_scope / test_derived_unverified_provenance_never_promotes`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/ops/test_kosgd2_steps.py` — `test_dry_run_registration_order_and_no_writes:12`, `test_failure_never_runs_following_stage:33`, `test_preflight_damage_and_stop_have_no_evaluation_calls:43`, `test_kosgd2_live_lock_and_stop_now:55` | `test_kosgd2_steps / test_dry_run_registration_order_and_no_writes / test_failure_never_runs_following_stage / test_preflight_damage_and_stop_have_no_evaluation_calls / test_kosgd2_live_lock_and_stop_now`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/ops/test_registration_status.py` — `test_missing_unknown_and_ready_states:11`, `test_each_threshold_and_seal_restart:25`, `test_modified_threshold_stops_before_writes:55`, `test_completed_stage_requires_resume_integrity:66` | `test_registration_status / test_missing_unknown_and_ready_states / test_each_threshold_and_seal_restart / test_modified_threshold_stops_before_writes / test_completed_stage_requires_resume_integrity`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/ops/test_status.py` — `test_registration_columns_observe_presence_without_claiming_validity:8` | `test_status / test_registration_columns_observe_presence_without_claiming_validity`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/run/test_cmd_t0.py` — `test_stage_entrypoints_reject_foreign_seams:49` | `test_cmd_t0 / test_stage_entrypoints_reject_foreign_seams`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/run/test_serverless_fingerprint.py` — `test_code_change_blocks_resume_compare_but_allows_history_report:10` | `test_serverless_fingerprint / test_code_change_blocks_resume_compare_but_allows_history_report`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/run/test_serverless_pipeline.py` — `test_both_variants_registered_without_server:11` | `test_serverless_pipeline / test_both_variants_registered_without_server`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `tests/score/test_audit_selection.py` — `test_explicit_selection_scope_and_joint_fallback:47` | `test_audit_selection / test_explicit_selection_scope_and_joint_fallback`: 같은 시나리오 시험 없음; 기존 fixture/Harness 및 지원 함수 재사용. |
| `ops/kosgd2_steps.sh` — `kosgd2_action`, `kosgd2_needed`, `kosgd2_stage`, `kosgd2_threshold`, `run_kosgd2` | `run_kosgd / run_stage / threshold / finish`: 등록 상태에 따른 kosgd2 순서 없음. 실제 실행은 기존 lib 함수를 호출. |

## 계획과 달라진 부분·해석

- `contract_map_check.py`는 사용자 최종 지시에 맞춰 새 audits/serverless_20261021 폴더에 둔다.
- cmd_t0.run은 기존 Python 시험/호출 및 CLI의 공통 진입점으로 남긴다. 단계 선택은 stage_handler 한 곳에서 한다.
- 완료 단계 생략의 검증을 위해 cmd_run의 기존 resume 선검사를 읽기 전용 함수로 추출했다. 일반 run 동작은 유지한다.
- C2는 출처 파일명/SHA까지 동일해야 한다. 새 감사 파일을 선택한 보고서와 문구만 비교하려는 요구는 동시에 만족할 수 없다. 같은 명시 감사 증거로 문구 비교 후 새 감사 출처는 별도 검증한다.
- 전체 무네트워크 수용은 소켓 시험 3개 파일을 명시 제외하고 그중 T0의 무소켓 시험은 따로 실행한다. skip/xfail을 추가하지 않는다.
- C5의 실제 감사 v4 재실행·실보고서 비교는 금지 범위이므로 운영자 작업으로 남는다. 합성 등록 경로만 검증한다.
- 위 C2 해석 외 새 미해결 SPEC_AMBIGUOUS는 없다. 도구는 계약 의미의 전수 반영이나 실데이터 타당성을 자동 인증하지 않는다.

## 초기 구현 실행 명령·결과 (F1–F7 보정 전)

기준 HEAD는 4d8ba94이며 커밋하지 않았다. `PY`는 기존 프로젝트 의존성과 pytest가 있는 Python이다.
실저장소 dataset/.work/results 접근 및 네트워크는 test_runner의 감사 훅으로 차단했다.
외부 임시 폴더의 합성 데이터/결과만 사용했다. 저장소 밖 baseline export는 허용된 코드/설정/시험만 담았다.

| 명령(경로 변수는 외부 임시 경로) | 결과 |
|---|---|
| `git archive 57ddf76 jev_test/jeveval jev_test/tests jev_test/configs reranker_test/evalcommon/schema.py`를 외부 임시 경로로 추출 | 실제 데이터/결과 제외, checkout 없음 |
| `PYTHONDONTWRITEBYTECODE=1 "$PY" -B audits/stage2_20261021/test_runner.py tests -q -p no:cacheprovider --basetemp="$SCRATCH" --ignore=tests/client/test_http_live.py --ignore=tests/run/test_executor_live.py --ignore=tests/t0_io/test_live.py` | 최종 제품 코드에서 2,757 passed, 201.22s |
| 같은 runner로 `tests/t0_io/test_live.py -k 'not test_cli_all_stages_with_loopback'` | 무소켓 3 passed |
| 같은 runner로 `tests/ops/test_status.py` | 마지막에 추가한 짝 시험 1 passed; 준비 단계 stdout을 비운 뒤 관측 검증 |
| 같은 runner의 `tests --collect-only -q -p no:cacheprovider`, `JEV_NODEIDS_OUT` 지정 | 2,786 nodeid; 기준 2,717개 모두 유지, 69개 추가 |
| `python3 -B audits/stage2_20261021/shape_check.py --before "$BEFORE" --after "$AFTER"` | ok=true, 위반 0, 삭제/새 skip·xfail 0 |
| `python3 -B audits/serverless_20261021/contract_map_check.py` | 6블록 및 21/5/7/6행 PASS |
| `python3 -B audits/serverless_20261021/dup_check.py --base 57ddf76` | ok=true, 기존 그룹 3, new_groups=[] |
| `"$PY" -B audits/serverless_20261021/t0_compare.py --base-tree "$BASE" --current-tree "$CURRENT" --scratch "$NEW_SCRATCH"` | 독립 프로세스 2, 산출물 21/help 5, differences=[] |
| `bash -n ops/lane.sh ops/lib.sh ops/kosgd2_steps.sh` 및 `git diff --check` | PASS |
| 변경 경로·추가 텍스트 검사 | 금지 트리 변경 0, 추가 홈 절대경로 0 |

기존 중복 3그룹은 JSON 고유 key 판독 함수들 1그룹과 lane/replay의 `kosgd`, `one_set` 2그룹이다.
보고서 비교기의 합성 양성/음성 시험은 통과했다. 실 C2 보고서, 감사 v4 재실행, 실 run·파일럿·T0는 실행하지 않았다.
네트워크 시험 제외는 사용자 금지에 따른 것이며 실행 가능한 수용 검사를 막은 샌드박스 오류는 없다.

## Claude 검토 F1–F7 보정

- F1: `derived_provenance.py:6` check_derived_origin, `:20` source_calls_match를 이동했다. audit_selection에는 재수출 별칭이 없다. 원천 정체성 조건도 `:35` source_identity_matches로 이동해 선택기가 새 모듈을 사용한다. 검색어 `derived_from / request_sha256 / source_identity_matches`: 기존 검사를 이동했으며 중복 구현하지 않았다.
- F2–F3: CLI는 handler.run만 호출한다. 단계 분배는 cmd_t0.stage_handler 한 곳이다. 인코더/체크포인트 주석은 57ddf76 원문 그대로 복원했다.
- F4: `ops/kosgd2_steps.sh:9` kosgd2_needed가 action/skip 후 전달 명령을 실행한다. 검색어 `kosgd2_action / 생략: 검증됨`: 두 실행기의 같은 머리를 추출했다.
- F5: `variant_registration.py:12` check_development가 development→check 흐름을 공유한다. 검색어 `variant_calculation.development / sealed=started`: analysis_gate와 ops의 기존 흐름을 추출했다. dev 경고 거부와 gate 예외/봉인 순서는 호출자에 남긴다.
- 질문 쪽에는 추출할 같은 재계산 흐름이 없다. `question_gate.py:17`은 증거를 읽고 `:19`, `:22`에서 check만 호출한다. `ops/registration_status.py:36`은 observations→thresholds 재계산을 추가한다. 양쪽은 이미 question_registration.check를 공유하므로 question_gate를 바꾸지 않았다.
- F6–F7: 한 줄 문구를 “이어지는 actions_only 규칙”으로 통일했다. OPTIONAL_SETS는 기본 실행에 포함되지 않으며 명시 SETS 선택만 허용한다.

### F1–F7 변경 파일과 실행 결과

이번 보정의 코드 12파일: jeveval/score/{derived_provenance,audit_selection}.py, jeveval/run/{history_check,cli,cmd_t0,variant_registration,analysis_gate}.py, jeveval/io/audit_evidence.py, ops/{kosgd2_steps.sh,registration_status.py,lib.sh}, audits/stage2_20261021/compare_runs.py.
시험 6파일: tests/score/test_derived_provenance.py, tests/run/{test_variant_registration,test_cli}.py, tests/io/test_audit_evidence.py, tests/audits/test_compare_runs.py, tests/ops/test_kosgd2_steps.py. 문서 5파일: jeveval/{README,IMPACT}.md, ops/README.md, P1_CONTRACT.md, 이 IMPLEMENTATION.md.
- `test_runner.py tests/score/test_derived_provenance.py tests/score/test_audit_selection.py tests/io/test_audit_evidence.py tests/run/test_history_check.py tests/run/test_cli.py tests/run/test_cmd_t0.py tests/run/test_analysis_gate.py tests/run/test_question_gate.py tests/run/test_variant_registration.py tests/run/test_question_registration.py tests/run/test_serverless_pipeline.py tests/ops tests/audits/test_compare_runs.py tests/audits/test_contract_map_check.py tests/t0_io --ignore=tests/t0_io/test_live.py -q -p no:cacheprovider --basetemp=/tmp/jev-fixes-related`: 232 passed (116.61s).
- `test_runner.py tests/ops/test_kosgd2_steps.py tests/t0_io/test_live.py -k 'shared_action_guard or not test_cli_all_stages_with_loopback' -q -p no:cacheprovider --basetemp=/tmp/jev-fixes-guards`: 25 passed, 네트워크 시험 6 deselected. 두 시험 실행은 일부 겹치므로 합산하지 않는다.
- 전체 collection 2,786→2,810, 기존 nodeid 삭제 0·새 skip/xfail 0. `shape_check.py --before /tmp/jev-fixes-before.json --after /tmp/jev-fixes-after.json`: 위반 0.
- `dup_check.py --base 4d8ba94`: ok=true, 기존 중복 그룹 3, new_groups=[]. `contract_map_check.py`: 여섯 블록 및 21/5/7/6행 PASS.
- `t0_compare.py --base-tree "$BASE" --current-tree "$CURRENT" --scratch /tmp/jev-fixes-t0`: 독립 프로세스 2, 산출물 21/help 5, differences=[].
- `bash -n ops/kosgd2_steps.sh ops/lib.sh`, `git diff --check`: PASS. 실제 데이터/결과·네트워크 접근 없이 실행했으며 커밋하지 않았다.
