"""R4 contracts captured by executing original blocks on synthetic inputs."""
import shared.taubench.scoring.score_run as subject


def test_observed_protocol_mismatch():
    failures, warnings = ['existing'], []
    subject._validate_observed_user_protocol({'harness_integrity': {'upstream_result_evidence': {'user_protocol': {'mismatch': ['model']}}}}, failures=failures, warnings=warnings)
    actual = (failures, warnings)
    assert actual == (['existing', "사용자 시뮬레이터 프로토콜이 선언과 다르다 — 다른 런과 비교할 수 없다: ['model']"], [])


def test_observed_protocol_unpinned():
    failures, warnings = [], []
    subject._validate_observed_user_protocol({'harness_integrity': {'upstream_result_evidence': {'user_protocol': {'pinned': False}}}}, failures=failures, warnings=warnings)
    actual = (failures, warnings)
    assert actual == ([], ['사용자 시뮬레이터 인자가 기록돼 있지 않다 — 이 런은 모델 간 비교에 쓸 수 없다'])


def test_domain_coverage_out_of_scope():
    failures, warnings = [], []
    subject._validate_domain_coverage({'by_domain': {'retail': {'runnable_tasks': 0, 'status': 'not_measured'}}}, failures=failures, warnings=warnings)
    actual = (failures, warnings)
    assert actual == ([], [])


def test_domain_coverage_partial_infrastructure():
    failures, warnings = [], []
    subject._validate_domain_coverage({'harness_integrity': {'trials': 2}, 'by_domain': {'retail': {'runnable_tasks': 3, 'measured': 2, 'trials': [1, 2], 'benchmark_eligible': False, 'coverage': {'official_task_count': 4}, 'termination_reasons': {'infrastructure_error': 2}, 'candidate_protocol_failures': {'empty': 1}, 'incompletion_attribution': {'environment': {'timeout': 1}}}}}, failures=failures, warnings=warnings)
    actual = (failures, warnings)
    assert actual == (['by_domain.retail: 3개 과제 중 2개만 측정됐다 — 부분 실행이다',
      'by_domain.retail: 시행 수가 과제마다 다르다 (선언 2, 관측 [1, 2]) — Pass^k 를 낼 수 없다',
      'by_domain.retail: 완주 실패 1건 (environment=1) — 완전 측정이 아니다'],
     ['by_domain.retail: 공식 split 4건 중 3건만 대상이다 — 도메인 점수가 아니라 부분집합 점수로만 인용할 것'])
