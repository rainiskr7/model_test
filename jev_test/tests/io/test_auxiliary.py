"""무엇: 보조 격리 행렬 · 입력: 선택 파일 손상 · 출력: 주 역사/인증/비교 불변 · 계약 §7-4c."""

import pytest
from jeveval.io import history, run_files
from jeveval.run import history_check, cmd_certify, cmd_compare
from tests.run.compare_support import pair


@pytest.mark.parametrize('attack', ['missing', 'valid', 'json', 'identity', 'hash', 'range'])
def test_selective_does_not_affect_primary(tmp_path, monkeypatch, attack):
    h, other = pair(tmp_path, monkeypatch)
    directories = [h.directory, other.directory]
    before = {n: (h.directory / n).read_bytes() for n in ('risk.json', 'scores.json')}
    primary = history_check.check(history.read(tmp_path, h.directory))
    cmd_compare.run(root=tmp_path, run_dirs=directories, compare_id='before')
    path = h.directory / 'selective.json'
    value = run_files.read_json(path)
    if attack == 'missing': path.unlink()
    elif attack == 'json': path.write_text('{')
    elif attack != 'valid':
        if attack == 'identity': value['run_id'] = 'other'
        if attack == 'hash': value['inputs']['risk.json'] = '0'*64
        if attack == 'range': value['auroc'] = 1.5
        run_files.write_json(path, value)
    saved = history.read(tmp_path, h.directory)
    assert history_check.check(saved) == primary
    assert saved.aux['selective']['status'] == (attack if attack in ('missing', 'valid') else 'invalid')
    assert cmd_certify.run(root=tmp_path, run_dir=h.directory)['ok']
    cmd_compare.run(root=tmp_path, run_dirs=directories, compare_id='after')
    base = tmp_path / 'results/_compare'
    assert (base / 'before/A/klue_mrc_answerable/default/compare.json').read_bytes() == (base / 'after/A/klue_mrc_answerable/default/compare.json').read_bytes()
    assert {n: (h.directory / n).read_bytes() for n in before} == before
