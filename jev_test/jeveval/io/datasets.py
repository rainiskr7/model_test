"""무엇: datasets.yaml 항목 조회·라벨 어휘 읽기 · 입력: datasets.yaml 경로/객체·셋 id · 출력: 항목 dict·LabelVocab · 계약 §6-2·§8-1."""

from jeveval.contract.label_vocab import SETS, validate_label_vocab
from jeveval.io.config import read_yaml
from jeveval.types import LabelVocab


def _entries(value, set_id):
    if isinstance(value, dict):
        if value.get("id") == set_id:
            yield value
        for child in value.values():
            yield from _entries(child, set_id)
    elif isinstance(value, list):
        for child in value:
            yield from _entries(child, set_id)


def dataset_entry(data, set_id) -> dict:
    """어느 그룹에 있든 id 가 같은 항목 하나만 돌려준다. 없거나 둘이면 거부."""
    matches = list(_entries(data, set_id))
    if len(matches) != 1:
        raise ValueError("dataset identity missing or duplicated")
    return matches[0]


def read_label_vocab(path) -> LabelVocab:
    """세 셋 항목의 label_vocab 을 읽어 순수 검사기로 위임한다."""
    data = read_yaml(path)
    result = validate_label_vocab({set_id: dataset_entry(data, set_id).get("label_vocab") for set_id in SETS})
    if isinstance(result, list):
        raise ValueError("; ".join(result))
    return result
