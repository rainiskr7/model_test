"""무엇: 확신 CLI 전달 · 입력: 하위 명령 · 출력: 조립 인자 · 계약 §7-4d."""

from jeveval.run import cli, cmd_score_variants


def test_variants_threshold_and_history_dispatch(monkeypatch):
    seen = []
    def run(**kwargs):
        seen.append(kwargs); return dict(ok=True)
    monkeypatch.setattr(cmd_score_variants, 'run', run)
    assert cli.main(['score-variants', 'threshold', '--run-dir', 'synthetic']) == 0
    assert seen[-1]['mode'] == 'threshold' and not seen[-1]['history']
    assert cli.main(['score-variants', '--history', '--run-dir', 'synthetic']) == 0
    assert seen[-1]['mode'] == 'risk' and seen[-1]['history']


def test_t0_uses_common_command_dispatch(monkeypatch):
    from jeveval.run import cmd_t0
    seen = {}
    def run(**kwargs):
        seen.update(kwargs)
        return dict(ok=True)
    monkeypatch.setattr(cmd_t0, 'run', run)
    assert cli.main(['t0', 'judge', '--run-dir', 'synthetic']) == 0
    assert seen['stage'] == 'judge' and seen['run_dir'] == 'synthetic'
