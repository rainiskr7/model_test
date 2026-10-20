"""Directory spelling contracts using only temporary trees."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from shared.resultspath.model_dir import results_model_dir_name


@pytest.mark.parametrize('spelling,model,expected', [
    ('Model_A', 'Model/A', 'Model_A'),
    ('Model_A', 'model-a', 'Model_A'),
    ('Straße', 'STRASSE', 'Straße'),
    (None, 'new/model:v1', 'new_model_v1'),
])
def test_spelling(tmp_path, spelling, model, expected):
    if spelling:
        (tmp_path / 'results' / spelling).mkdir(parents=True)
    assert results_model_dir_name(tmp_path, model) == expected


def test_nonmatching_and_file(tmp_path):
    (tmp_path / 'results/other').mkdir(parents=True)
    (tmp_path / 'results/MODEL_A').touch()
    assert results_model_dir_name(tmp_path, 'model/a') == 'model_a'


def test_ambiguous_even_with_exact_match(tmp_path, monkeypatch):
    root = tmp_path / 'results'
    root.mkdir()
    (root / 'Model_A').mkdir()
    # Preserve the case-sensitive filesystem contract on macOS too.
    original = Path.iterdir
    entries = [SimpleNamespace(name=n, is_dir=lambda: True) for n in ('model_a', 'Model_A')]
    monkeypatch.setattr(Path, 'iterdir', lambda p: iter(entries) if p == root else original(p))
    with pytest.raises(ValueError) as exc:
        results_model_dir_name(tmp_path, 'Model/A')
    assert str(exc.value) == "case-fold ambiguous results model directory for 'Model_A': ['Model_A', 'model_a']"
