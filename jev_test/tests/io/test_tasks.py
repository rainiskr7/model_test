"""무엇: 목록·B1 읽기 검사 · 입력: tmp_path 설정 · 출력: 사본·중복·오류 대조 · 계약 §1-1."""

import pytest
import yaml

from jeveval.io.tasks import read_b1_config, read_lists


def test_lists_keep_order_and_read_all_json(tmp_path):
    (tmp_path / "options.json").write_text('{"z":"끝","a":"처음"}')
    (tmp_path / "catalog.json").write_text('[{"id":"z"}]')
    (tmp_path / "ignored.txt").write_text('invalid')
    result = read_lists(tmp_path)
    assert list(result) == ["catalog", "options"]
    assert list(result["options"]) == ["z", "a"]
    result["catalog"].clear()
    assert read_lists(tmp_path)["catalog"] == [{"id": "z"}]


@pytest.mark.parametrize("source", ['{"a":1,"a":2}', '{"x":{"a":1,"a":2}}'])
def test_duplicate_json_keys_rejected(tmp_path, source):
    (tmp_path / "bad.json").write_text(source)
    with pytest.raises(ValueError, match="duplicate"):
        read_lists(tmp_path)


def test_b1_exact_fields_and_template(tmp_path):
    config = dict(system="s", user_template="{state}{instructions}{options}", labels=["A"], params={})
    path = tmp_path / "b1.yaml"
    path.write_text(yaml.safe_dump(config))
    assert read_b1_config(path).to_dict() == config
    bad = [{k: v for k, v in config.items() if k != key} for key in config]
    bad += [{**config, "extra": 1}, {**config, "labels": None},
            {**config, "user_template": "{state!r}{instructions}{options}"}]
    for value in bad:
        path.write_text(yaml.safe_dump(value))
        with pytest.raises(ValueError):
            read_b1_config(path)
    path.write_text(yaml.safe_dump(config) + 'system: duplicate\n')
    with pytest.raises(yaml.constructor.ConstructorError):
        read_b1_config(path)
