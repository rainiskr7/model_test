"""무엇: 등록 두 판 합성 통합 · 입력: 기존 Harness와 세 호출 방식 · 출력: registered·재개 불변 · 계약 §7-4b·7-4d."""

import pytest
from jeveval.io import run_files
from jeveval.run import cmd_question_risk, cmd_score_variants
from tests.run.analysis_support import prepared, thresholds
from tests.run.file_support import output_files


@pytest.mark.parametrize('kind,scoring', [('systemone', 'separate'), ('systemone', 'joint'), ('b1', 'separate')])
def test_both_variants_registered_without_server(tmp_path, monkeypatch, kind, scoring):
    h = prepared(tmp_path, monkeypatch, kind=kind, question_scoring=scoring)
    for variant in ('full', 'actions_only'):
        h.variant = variant
        if variant == 'actions_only':
            h.run('dev'); assert h.command('threshold') == 0
        thresholds(h)
    for variant in ('full', 'actions_only'):
        h.variant = variant; h.run('test')
        assert h.command('score') == h.command('certify') == 0
        assert cmd_question_risk.run(root=tmp_path, run_dir=h.directory)['registration'] == 'registered'
        assert cmd_score_variants.run(root=tmp_path, run_dir=h.directory)['registration'] == 'registered'
        for name in ('question_risk.json', 'score_variants.json'):
            assert run_files.read_json(h.directory / name)['registration']['status'] == 'registered'
        before = output_files(h.directory); calls = len(h.sent)
        h.run('test')
        assert output_files(h.directory) == before and len(h.sent) == calls
