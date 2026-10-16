"""라벨 어휘 자료형의 JSON 및 불변 대입 경계."""

from jeveval.types.labels import LabelVocab
from tests.types.record_support import check_record


def test_label_vocab_record_boundaries():
    check_record(LabelVocab(["GOODBYE", "THANK_YOU"], ["origin"], ["없음"]))


def test_label_vocab_from_dict_detaches_lists():
    payload = dict(kosgd_acts=["GOODBYE", "THANK_YOU"], kmhas=["origin"], kote=["없음"])
    value = LabelVocab.from_dict(payload)
    payload["kmhas"].clear()
    assert value.kmhas == ["origin"]
