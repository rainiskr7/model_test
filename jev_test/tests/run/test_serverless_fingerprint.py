"""무엇: 현재/역사 코드 지문 경계 · 입력: 완료 합성 run과 코드 변화 · 출력: 재개/비교 거부·보고 허용 · 계약 §5-1b."""

import pytest
from jeveval.io import history
from jeveval.run import cmd_compare, cmd_report, history_check, history_stage
from tests.run.history_support import finished
from tests.run.file_support import output_files


def test_code_change_blocks_resume_compare_but_allows_history_report(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    before = output_files(h.directory)
    (tmp_path / 'jeveval/new_module.py').write_text('VALUE = 1\n')
    calls = len(h.sent)
    with pytest.raises(ValueError): h.run('test')
    with pytest.raises(ValueError, match='frozen inputs'):
        cmd_compare.run(root=tmp_path, run_dirs=[h.directory], compare_id='new')
    assert len(h.sent) == calls and output_files(h.directory) == before
    saved = history.read(tmp_path, h.directory)
    assert history_check.check(saved).status == 'verified_complete'
    assert history_stage.restore(tmp_path, saved, 'test').finals
    assert cmd_report.run(root=tmp_path, run_id='r1', models=['synthetic'], out='history.md')['damaged'] == 0
    assert output_files(h.directory) == before
