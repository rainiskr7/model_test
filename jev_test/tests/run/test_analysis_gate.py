"""무엇: 다중 봉인 행렬 · 입력: 선언/중단/손상 · 출력: 선검사와 재개 거부 · 계약 §7-4d."""

import pytest
from jeveval.io import run_files
from tests.run.analysis_support import prepared, thresholds
from tests.run.file_support import output_files


def seal_cases(declared_only=False):
    result = []
    for kinds in ((), ('question_risk',), ('score_variants',), ('question_risk', 'score_variants')):
        if declared_only and not kinds:
            continue
        names = (['question_seal.json'] if 'question_risk' in kinds else [])
        names += (['variant_seal.json'] if 'score_variants' in kinds else []) + ['seal.json']
        result.extend((kinds, name) for name in names)
    return result


@pytest.mark.parametrize('kinds', [(), ('question_risk',), ('score_variants',), ('question_risk', 'score_variants')])
def test_four_declarations_and_seal_order(tmp_path, monkeypatch, kinds):
    h = prepared(tmp_path, monkeypatch, kinds); thresholds(h, kinds)
    writes, original = [], run_files.write_json
    def track(path, value):
        writes.append(path.name); return original(path, value)
    monkeypatch.setattr(run_files, 'write_json', track)
    h.run('test'); h.run('test')
    expected = (["question_seal.json"] if 'question_risk' in kinds else [])
    expected += (["variant_seal.json"] if 'score_variants' in kinds else []) + ['seal.json']
    assert [n for n in writes if n.endswith('seal.json')] == expected


@pytest.mark.parametrize('kinds,seal', seal_cases())
def test_crash_after_each_seal(tmp_path, monkeypatch, kinds, seal):
    h = prepared(tmp_path, monkeypatch, kinds); thresholds(h, kinds)
    original = run_files.write_json
    def crash(path, value):
        original(path, value)
        if path.name == seal: raise OSError('synthetic interruption')
    monkeypatch.setattr(run_files, 'write_json', crash)
    with pytest.raises(OSError): h.run('test')
    monkeypatch.setattr(run_files, 'write_json', original)
    if seal == 'seal.json': h.run('test')
    else:
        before = output_files(h.directory)
        with pytest.raises(ValueError): h.run('test')
        assert output_files(h.directory) == before


@pytest.mark.parametrize('kinds,name', seal_cases(declared_only=True))
@pytest.mark.parametrize('attack', ['delete', 'copy', 'tamper'])
def test_seal_attacks_stop_before_writes(tmp_path, monkeypatch, kinds, name, attack):
    h = prepared(tmp_path, monkeypatch, kinds); thresholds(h, kinds); h.run('test')
    path = h.directory / 'test' / name
    if attack == 'delete': path.unlink()
    else:
        value = run_files.read_json(path)
        if name == 'seal.json': key = 'threshold_sha256'
        else: key = 'run_id' if attack == 'copy' else 'fingerprint_sha256'
        value[key] = 'foreign'; run_files.write_json(path, value)
    before = output_files(h.directory)
    with pytest.raises(ValueError): h.run('test')
    assert output_files(h.directory) == before


@pytest.mark.parametrize('marker', ['attempts.jsonl', 'replay.json'])
def test_empty_start_markers_and_missing_policy_are_not_downgraded(tmp_path, monkeypatch, marker):
    from jeveval.run import cmd_score_variants
    h = prepared(tmp_path, monkeypatch)
    folder = h.directory / 'test'; folder.mkdir()
    (folder / marker).write_bytes(b'')
    before = output_files(h.directory)
    with pytest.raises(ValueError): cmd_score_variants.run(root=tmp_path, run_dir=h.directory, mode='threshold')
    with pytest.raises(ValueError): h.run('test')
    assert output_files(h.directory) == before


def test_missing_second_policy_leaves_no_first_seal(tmp_path, monkeypatch):
    h = prepared(tmp_path, monkeypatch)
    assert h.command('question-threshold') == 0
    before = output_files(h.directory)
    with pytest.raises(ValueError): h.run('test')
    assert output_files(h.directory) == before
