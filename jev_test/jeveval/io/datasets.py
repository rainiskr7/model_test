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
    if any(family(set_id, data) != set_id for set_id in SETS):
        raise ValueError("label vocabulary requires family representatives")
    result = validate_label_vocab({set_id: dataset_entry(data, set_id).get("label_vocab") for set_id in SETS})
    if isinstance(result, list):
        raise ValueError("; ".join(result))
    return result


def family(set_id, data):
    """셋 정체성과 독립인 가족을 조회한다. 어휘는 가족 대표 셋을 공유한다."""
    from jeveval.io.paths import identifier
    return identifier(dataset_entry(data, set_id).get("family", set_id))


def checked_family(set_id, cfg, root, selected=None):
    """두 설정의 가족 선언을 대조한다. 별칭에는 datasets 선언이 필수다."""
    from pathlib import Path
    if selected is None and (Path(root) / "configs/splits/rules.yaml").is_file():
        from jeveval.io.set_config import entry
        selected = entry(root, set_id)
    if selected is not None:
        if (selected.set_id != set_id or selected.split_rules != cfg
                or selected.family != cfg.get("family", set_id)):
            raise ValueError("dataset/rules family mismatch")
        return selected.family
    path = Path(root) / "configs/datasets.yaml"
    declared = cfg.get("family", set_id)
    if path.exists():
        if family(set_id, read_yaml(path)) != declared:
            raise ValueError("dataset/rules family mismatch")
    elif declared != set_id:
        raise ValueError("alias requires datasets family")
    return declared
