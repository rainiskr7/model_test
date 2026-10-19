"""무엇: 격리 셋 설정 읽기 · 입력: root/공용 경로/셋 · 출력: SetEntry·catalog · 계약 판 5 보정 1 §1-1."""

from copy import deepcopy
from pathlib import Path

import yaml

from jeveval.contract.set_overlay import task_names, validate_overlay
from jeveval.io.config import load_taskspec, read_yaml
from jeveval.io.datasets import dataset_entry, family
from jeveval.io.paths import identifier, inside
from jeveval.io.set_tasks import BASE_TASKS
from jeveval.types.set_config import SetEntry

DATASETS = "configs/datasets.yaml"
RULES = "configs/splits/rules.yaml"


def _ids(value):
    if isinstance(value, dict):
        if "id" in value:
            yield identifier(value["id"])
        for child in value.values():
            yield from _ids(child)
    elif isinstance(value, list):
        for child in value:
            yield from _ids(child)


def _read(root, path, *, confined=True):
    try:
        return read_yaml(inside(root, path) if confined else Path(root) / path)
    except yaml.YAMLError as exc:
        raise ValueError("invalid set configuration YAML") from exc


def _base(root, datasets, rules):
    data, split = _read(root, datasets, confined=False), _read(root, rules, confined=False)
    ids = set(_ids(data))
    if not isinstance(split, dict) or not isinstance(split.get("sets"), dict):
        raise ValueError("base rules sets must be an object")
    for name, config in split["sets"].items():
        identifier(name)
        if not isinstance(config, dict):
            raise ValueError("base set rules must be an object")
    return data, split["sets"], ids


def _base_entry(name, data, rules):
    record = dataset_entry(data, name)
    fam = family(name, data)
    if not isinstance(rules[name], dict) or rules[name].get("family", name) != fam:
        raise ValueError("dataset/rules family mismatch")
    return SetEntry(name, fam, deepcopy(record), deepcopy(rules[name]), None,
                    tuple("configs/tasks/" + p for p in BASE_TASKS.get(name, ())))


def _overlay(root, path, data, rules, ids):
    value = _read(root, path)
    tasks = {name: load_taskspec(inside(root, Path("configs/tasks") / name))
             for name in task_names(value)}
    representatives = {name for name in ids & rules.keys()
                       if family(name, data) == name and rules[name].get("family", name) == name}
    errors = validate_overlay(value, Path(path).stem, ids | rules.keys(), representatives, tasks)
    if errors:
        raise ValueError("; ".join(errors))
    name = value["id"]
    return SetEntry(name, value["dataset"]["family"], deepcopy(value["dataset"]),
                    deepcopy(value["split_rules"]), Path(path).as_posix(),
                    tuple("configs/tasks/" + n for n in value["tasks"]))


def entry(root, set_id, *, datasets=DATASETS, rules=RULES) -> SetEntry:
    """기존 셋은 overlay 디렉터리에 접근하지 않는다. 새 셋은 자기 파일만 읽는다."""
    identifier(set_id)
    data, configs, ids = _base(root, datasets, rules)
    if set_id in ids & configs.keys():
        return _base_entry(set_id, data, configs)
    if set_id in ids | configs.keys():
        raise ValueError("set is missing from one base configuration")
    return _overlay(root, f"configs/sets/{set_id}.yaml", data, configs, ids)


def catalog(root, *, datasets=DATASETS, rules=RULES) -> list[SetEntry]:
    """전체 검증 전용: 공용 실행 셋과 모든 overlay를 정렬해 반환한다."""
    data, configs, ids = _base(root, datasets, rules)
    if not configs.keys() <= ids:
        raise ValueError("base rules set missing dataset")
    result = [_base_entry(name, data, configs) for name in sorted(configs)]
    directory = inside(root, "configs/sets")
    for path in sorted(directory.glob("*.yaml")):
        result.append(_overlay(root, path.relative_to(Path(root).resolve()).as_posix(), data, configs, ids))
    return sorted(result, key=lambda item: item.set_id)


def evidence_paths(selected) -> tuple[str, ...]:
    """overlay의 task·선정·제외 입력도 동결한다. 원본은 기존 SHA256SUMS로 대조한다."""
    if selected.overlay_path is None:
        return ()
    pool = selected.split_rules.get("pool", {})
    paths = [selected.overlay_path, *selected.task_files]
    if "path" in pool:
        paths.append(pool["path"])
    for rule in pool.get("exclude", []):
        paths.append(rule["path"])
    if any(not isinstance(p, str) or Path(p).is_absolute() or ".." in Path(p).parts for p in paths):
        raise ValueError("overlay evidence must use root-relative paths")
    return tuple(sorted(set(paths)))
