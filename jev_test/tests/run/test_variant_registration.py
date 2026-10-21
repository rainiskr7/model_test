"""무엇: 변형 등록 사슬 · 입력: 합성 봉인/복사 · 출력: 등록/손상 · 계약 §7-4d."""

from jeveval.io import analysis_artifacts
from jeveval.run import context
from jeveval.run.variant_registration import check, check_development
from tests.run.analysis_support import prepared, thresholds


def test_registration_and_recomputed_policy(tmp_path, monkeypatch):
    h = prepared(tmp_path, monkeypatch); thresholds(h); h.run('test')
    e = analysis_artifacts.read(tmp_path, h.directory)
    dev = context.stage(context.restore(tmp_path, h.directory), 'dev')
    assert check(e) == 'registered'
    assert check_development(e, dev, sealed=True) == 'registered'
    assert check(e, {'calibrators': {'foreign': {}}}) == 'registration_damaged'
    e['artifacts']['test/variant_seal.json']['run_id'] = 'foreign'
    assert check(e) == 'registration_damaged'
    assert check_development(e, dev, sealed=True) == 'registration_damaged'
