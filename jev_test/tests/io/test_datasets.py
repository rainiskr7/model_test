"""중첩 데이터셋 항목 조회와 저장소 라벨 어휘 로딩."""

from pathlib import Path

import pytest

from jeveval.io.datasets import dataset_entry, read_label_vocab
from jeveval.types import LabelVocab
from tests.run.cli_support import put_yaml

REPO = Path(__file__).resolve().parents[2]


def test_nested_dataset_entry():
    entry = {"id": "wanted", "map": {"primary_variant": "full"}}
    data = {"groups": [{"children": {"sets": [{"id": "other"}, entry]}}]}
    assert dataset_entry(data, "wanted") == entry


@pytest.mark.parametrize("entries", [[], [{"id": "other"}], [{"id": "x"}, {"id": "x"}]])
def test_missing_or_duplicate_entry(entries):
    with pytest.raises(ValueError, match="^dataset identity missing or duplicated$"):
        dataset_entry({"groups": [entries]}, "x")


def test_repository_label_vocab():
    result = read_label_vocab(REPO / "configs/datasets.yaml")
    assert result == LabelVocab(
        ["INFORM", "REQUEST", "AFFIRM", "NEGATE", "REQUEST_ALTS", "SELECT", "GOODBYE",
         "THANK_YOU", "INFORM_INTENT", "AFFIRM_INTENT", "NEGATE_INTENT"],
        ["origin", "physical", "politics", "profanity", "age", "gender", "race", "religion", "not_hate_speech"],
        ["불평/불만", "화남/분노", "짜증", "안타까움/실망", "의심/불신", "불안/걱정", "고마움", "없음"])
    assert [len(result.kosgd_acts), len(result.kmhas), len(result.kote)] == [11, 9, 8]


def test_label_vocab_loader_joins_errors(tmp_path):
    path = tmp_path / "datasets.yaml"
    names = ("kosgd", "kmhas", "kote_escalation")
    put_yaml(path, {"sets": [{"id": name, "label_vocab": []} for name in names]})
    with pytest.raises(ValueError) as exc:
        read_label_vocab(path)
    assert str(exc.value) == "; ".join(
        f"{name}: label_vocab must be a non-empty list of unique names" for name in names)


def test_family_defaults_and_conflicting_declaration_rejected(tmp_path):
    from jeveval.io.datasets import family, checked_family
    import yaml
    data = {"sets": [{"id": "kosgd"}, {"id": "kosgd2", "family": "kosgd"}]}
    assert family("kosgd", data) == family("kosgd2", data) == "kosgd"
    path = tmp_path / "configs/datasets.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(data))
    assert checked_family("kosgd2", {"family": "kosgd"}, tmp_path) == "kosgd"
    with pytest.raises(ValueError, match="family mismatch"):
        checked_family("kosgd2", {}, tmp_path)


def test_alias_uses_family_vocabulary_without_new_vocab_field():
    from pathlib import Path
    from jeveval.io.config import read_yaml
    from jeveval.io.datasets import dataset_entry, read_label_vocab
    path = Path(__file__).resolve().parents[2] / "configs/datasets.yaml"
    data = read_yaml(path)
    from jeveval.io.set_config import entry
    assert "label_vocab" not in entry(path.parents[1], "kosgd2").dataset
    assert read_label_vocab(path).kosgd_acts == dataset_entry(data, "kosgd")["label_vocab"]
