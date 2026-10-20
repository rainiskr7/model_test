"""Normalization remains idempotent for every character it can replace."""

import pytest

from shared.resultspath.model_dir import safe_model_name


@pytest.mark.parametrize("model,expected", [
    ("", ""),
    ("maker/model-name:v1", "maker_model_name_v1"),
    ("/:-_", "____"),
    ("한글/模型-ß:V1.0", "한글_模型_ß_V1.0"),
    ("model_'\"\n", "model_'\"\n"),
])
def test_normalization_is_idempotent(model, expected):
    normalized = safe_model_name(model)
    assert normalized == expected
    assert safe_model_name(normalized) == normalized
