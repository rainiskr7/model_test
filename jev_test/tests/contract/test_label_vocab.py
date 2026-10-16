"""라벨 어휘 경계: 세 셋의 이름 목록과 CLOSE 구성 act 검증."""

import pytest

from jeveval.contract.label_vocab import validate_label_vocab
from jeveval.types import LabelVocab


@pytest.fixture
def entries(vocab):
    return dict(kosgd=vocab.kosgd_acts, kmhas=vocab.kmhas, kote_escalation=vocab.kote)


def test_valid_vocab_is_detached_record(entries, vocab):
    result = validate_label_vocab(entries)
    assert isinstance(result, LabelVocab) and result == vocab
    original = list(result.kmhas)
    entries["kmhas"].clear()
    assert result.kmhas == original
    assert len(result.kmhas) == 9


@pytest.mark.parametrize("missing", ["kosgd", "kmhas", "kote_escalation"])
def test_all_sets_required(entries, missing):
    del entries[missing]
    assert validate_label_vocab(entries) == [
        "label_vocab required for exactly: kmhas, kosgd, kote_escalation"]


@pytest.mark.parametrize("value", [None, [], "name", ["x", "x"], [""], [1], [True], [[]], [{}]])
@pytest.mark.parametrize("name", ["kosgd", "kmhas", "kote_escalation"])
def test_invalid_name_lists(entries, name, value):
    entries[name] = value
    assert validate_label_vocab(entries) == [
        f"{name}: label_vocab must be a non-empty list of unique names"]


@pytest.mark.parametrize("act", ["GOODBYE", "THANK_YOU"])
def test_close_requires_both_acts(entries, act):
    entries["kosgd"].remove(act)
    assert validate_label_vocab(entries) == [
        "kosgd: label_vocab must include GOODBYE and THANK_YOU (CLOSE)"]


def test_vocab_errors_accumulate(entries):
    entries.update(kosgd=[], kmhas=[""], kote_escalation=[False])
    assert validate_label_vocab(entries) == [
        f"{name}: label_vocab must be a non-empty list of unique names"
        for name in ("kosgd", "kmhas", "kote_escalation")]


@pytest.mark.parametrize("value", [None, [], {"extra": []}])
def test_closed_set_mapping(value):
    assert validate_label_vocab(value) == [
        "label_vocab required for exactly: kmhas, kosgd, kote_escalation"]
