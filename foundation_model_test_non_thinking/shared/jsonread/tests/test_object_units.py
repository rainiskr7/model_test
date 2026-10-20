"""The shared reader retains both scorers' object and error contracts."""

import json

import pytest

from shared.jsonread.object import load_json_object


def test_utf8_object_and_key_order(tmp_path):
    path = tmp_path / "artifact.json"
    path.write_text('{"z": "한글", "a": [1, null, true]}', encoding="utf-8")
    actual = load_json_object(path)
    assert actual == {"z": "한글", "a": [1, None, True]}
    assert list(actual) == ["z", "a"]


@pytest.mark.parametrize("text", ["[]", "null", '"text"', "0", "false"])
def test_nonobject_error_message(tmp_path, text):
    path = tmp_path / "artifact.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        load_json_object(path)
    assert type(exc.value) is ValueError
    assert str(exc.value) == f"expected JSON object: {path}"


def test_decoder_and_filesystem_errors_are_not_wrapped(tmp_path):
    path = tmp_path / "artifact.json"
    with pytest.raises(FileNotFoundError):
        load_json_object(path)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_json_object(path)
