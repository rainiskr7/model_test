"""9-0 literals captured from textnorm, including its permissive numeric parsing."""

import pytest

from shared.multimodal.benches import textnorm


@pytest.mark.parametrize("value,expected", [
    ("  ＡＢＣ　１２３ 「한글」 (TEST) [x] <Y> `Z`  ", "abc 123 한글 test x y z"),
    ("a‐b‑c‒d–e—f―g−h", "a-b-c-d-e-f-g-h"),
    ("  1 , 000 . 50\n X\t Y  ", "1,000.50 x y"),
    ("", ""), (None, ""), (True, ""), (12, ""),
    (["text"], ""), ({"text": "a"}, ""), (b"ABC", ""),
])
def test_normalize_text(value, expected):
    assert textnorm.normalize_text(value) == expected


@pytest.mark.parametrize("value,expected", [
    ("１２,５００원", 12500.0), ("￦12,500", 12500.0), ("5.2 kg", 5.2),
    ("-12.5 kg", -12.5), ("−12", 12.0), ("1e3", 13.0),
    (17, 17.0), (2.5, 2.5), (True, 1.0), (False, 0.0),
    ("--2", None), ("abc", None), ("", None), (None, None),
    ([], None), ({}, None), (b"12", None),
])
def test_normalize_number(value, expected):
    actual = textnorm.normalize_number(value)
    assert actual == expected
    assert actual is None or type(actual) is float
