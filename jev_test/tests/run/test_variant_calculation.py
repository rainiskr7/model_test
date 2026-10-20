"""무엇: dev 적합과 test 적용 분리 · 입력: 합성 단계 · 출력: 동결 불변 · 계약 §7-4d."""

from dataclasses import replace
from jeveval.run import context, variant_calculation
from tests.run.analysis_support import prepared, thresholds


def test_dev_policy_not_changed_by_test_labels(tmp_path, monkeypatch):
    h = prepared(tmp_path, monkeypatch); thresholds(h); h.run('test')
    ctx = context.restore(tmp_path, h.directory)
    dev, test = context.stage(ctx, 'dev'), context.stage(ctx, 'test')
    policy = variant_calculation.development(dev)
    before = repr(policy)
    changed = replace(test, outcomes=[replace(r, wrong=not r.wrong) for r in test.outcomes])
    variant_calculation.trial(changed, policy)
    assert repr(policy) == before and variant_calculation.development(dev) == policy
