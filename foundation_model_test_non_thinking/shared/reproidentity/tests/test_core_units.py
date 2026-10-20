"""Literal contracts captured from the two original repro helpers."""

import pytest

from shared.reproidentity.core import digest, metadata_identity


@pytest.mark.parametrize("values,expected", [
    ([], "e3b0c44298fc1c14"),
    (["b", "a"], "7e18f737311b2dc3"),
    (["한글", "a"], "be39c9ed819679c0"),
    (["a", "a"], "99b4ae0e261695ce"),
])
def test_digest_keeps_order_independence_unicode_and_duplicates(values, expected):
    assert digest(iter(values)) == expected
    assert digest(reversed(values)) == expected


@pytest.mark.parametrize("values,expected", [
    ([], None),
    ([None], None),
    ([{"b": 2, "a": "한글"}, {"a": "한글", "b": 2}], {"a": "한글", "b": 2}),
    ([True, False], ("false", "true")),
    ([1, "1"], ('"1"', "1")),
])
def test_metadata_identity_preserves_types_and_conflicts(values, expected):
    assert metadata_identity(iter(values)) == expected


def test_invalid_inputs_keep_type_errors():
    with pytest.raises(TypeError):
        digest([1])
    with pytest.raises(TypeError):
        metadata_identity([object()])
