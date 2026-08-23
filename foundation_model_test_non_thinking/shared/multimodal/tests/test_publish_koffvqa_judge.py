from __future__ import annotations

import pytest

from shared.multimodal.benches.koffvqa_api_judge import resolve_columns, valid_score


def test_koffvqa_exact_default_columns():
    columns = ["index", "question", "answer", "category", "l2-category", "prediction"]
    assert resolve_columns(columns) == ("question", "answer", "prediction")


def test_koffvqa_fuzzy_names_are_not_accepted():
    with pytest.raises(ValueError):
        resolve_columns(["my_question_text", "answer", "prediction"])


def test_koffvqa_explicit_overrides_and_duplicate_binding_guard():
    columns = ["q", "rubric", "output"]
    assert resolve_columns(columns, "q", "rubric", "output") == ("q", "rubric", "output")
    with pytest.raises(ValueError):
        resolve_columns(columns, "q", "rubric", "rubric")


@pytest.mark.parametrize("score", [0, 1, 10])
def test_integer_score_is_valid(score):
    assert valid_score(score)


@pytest.mark.parametrize("score", [True, False, -1, 11, 5.0, "5", None])
def test_non_integer_or_out_of_range_score_is_invalid(score):
    assert not valid_score(score)
