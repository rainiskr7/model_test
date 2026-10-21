"""무엇: 등록 상태/재개 결정 시험 · 입력: 합성 run/손상 · 출력: 무쓰기 create/skip/stop · 계약 §7-4b."""

from pathlib import Path
import pytest
from ops.registration_status import read_registration_state, next_registration_action, main
from jeveval.io import run_files
from tests.run.analysis_support import prepared, thresholds
from tests.run.file_support import output_files


def test_missing_unknown_and_ready_states(tmp_path, monkeypatch, capsys):
    assert next_registration_action('unknown') == 'stop'
    assert set(read_registration_state(tmp_path, tmp_path / 'absent').values()) == {'missing'}
    h = prepared(tmp_path, monkeypatch)
    state = read_registration_state(tmp_path, h.directory)
    assert state['dev'] == state['threshold'] == 'ready'
    assert state['question-threshold'] == 'missing'
    before = output_files(h.directory)
    assert main([str(h.directory), 'threshold']) == 0
    assert capsys.readouterr().out.splitlines()[-1] == 'skip'
    assert output_files(h.directory) == before


@pytest.mark.parametrize('point', ['ordinary', 'question', 'variant', 'question_seal.json', 'variant_seal.json', 'seal.json'])
def test_each_threshold_and_seal_restart(tmp_path, monkeypatch, point):
    h = prepared(tmp_path, monkeypatch)
    if point != 'ordinary': h.command('question-threshold')
    if point not in ('ordinary', 'question'):
        from jeveval.run import cmd_score_variants
        cmd_score_variants.run(root=tmp_path, run_dir=h.directory, mode='threshold')
    if point.endswith('seal.json'):
        original = run_files.write_json
        def crash(path, value):
            original(path, value)
            if path.name == point: raise OSError('synthetic')
        with monkeypatch.context() as patch:
            patch.setattr(run_files, 'write_json', crash)
            with pytest.raises(OSError): h.run('test')
    before = output_files(h.directory)
    state = read_registration_state(tmp_path, h.directory)
    assert output_files(h.directory) == before
    if point in ('question_seal.json', 'variant_seal.json'):
        assert set(state.values()) == {'damaged'}
        assert main([str(h.directory), 'preflight']) == 2
    else:
        assert 'damaged' not in state.values()
        assert state['threshold'] == 'ready'
        if point == 'seal.json':
            assert state['test'] == 'missing'
            h.run('test')
            assert read_registration_state(tmp_path, h.directory)['test'] == 'sealed'


@pytest.mark.parametrize('artifact', ['threshold.json', 'question_threshold.json', 'variant_threshold.json'])
def test_modified_threshold_stops_before_writes(tmp_path, monkeypatch, artifact):
    h = prepared(tmp_path, monkeypatch); thresholds(h)
    path = h.directory / artifact
    data = run_files.read_json(path); data['run_id'] = 'foreign'; run_files.write_json(path, data)
    before = output_files(h.directory)
    assert set(read_registration_state(tmp_path, h.directory).values()) == {'damaged'}
    assert output_files(h.directory) == before


@pytest.mark.parametrize('stage', ['dev', 'test'])
@pytest.mark.parametrize('variant', ['full', 'actions_only'])
def test_completed_stage_requires_resume_integrity(tmp_path, monkeypatch, stage, variant):
    h = prepared(tmp_path, monkeypatch)
    thresholds(h)
    if stage == 'test': h.run('test')
    if variant == 'actions_only':
        h.variant = variant; h.run('dev'); assert h.command('threshold') == 0
        thresholds(h)
        if stage == 'test': h.run('test')
        path = h.directory / stage / 'derived.json'
        value = run_files.read_json(path); value['derived_from'] = 'foreign'
        run_files.write_json(path, value)
    else:
        path = h.directory / stage / 'attempts.jsonl'
        path.write_bytes(path.read_bytes() + b'{invalid tail\n')
    before, sent = output_files(h.directory), len(h.sent)
    assert set(read_registration_state(tmp_path, h.directory).values()) == {'damaged'}
    assert output_files(h.directory) == before and len(h.sent) == sent
