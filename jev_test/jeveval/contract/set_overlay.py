"""무엇: overlay 순수 검사 · 입력: 원시 설정·공용 정체성·읽은 tasks · 출력: 오류 목록 · 계약 판 5 보정 1 §1-1."""

import re


def _identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) is not None


def _nested_id(value, seen=None):
    seen = set() if seen is None else seen
    if not isinstance(value, (dict, list)):
        return False
    if id(value) in seen:
        return True
    seen = seen | {id(value)}
    if isinstance(value, dict) and "id" in value:
        return True
    return any(_nested_id(v, seen) for v in (value.values() if isinstance(value, dict) else value))


def task_names(value):
    """파일 조회 전에 이름·중복·디렉터리 탈출을 검사한다."""
    names = value.get("tasks") if isinstance(value, dict) else None
    if (not isinstance(names, list) or not names or
            any(not isinstance(n, str) or not n.endswith(".yaml") or
                not _identifier(n[:-5]) or n == "b1.yaml" for n in names) or
            len(set(names)) != len(names)):
        return []
    return names


def validate_overlay(value, stem, base_ids, base_families, tasks_on_disk) -> list[str]:
    """base_ids는 공용 양쪽 ID 합집합, base_families는 교집합의 대표 ID 집합이다."""
    if not isinstance(value, dict) or set(value) != {"schema", "id", "tasks", "dataset", "split_rules"}:
        return ["overlay requires exactly schema/id/tasks/dataset/split_rules"]
    errors = []
    if value["schema"] != "set_overlay/1":
        errors.append("invalid overlay schema")
    if not _identifier(stem) or value["id"] != stem or stem in base_ids:
        errors.append("overlay identity conflicts with stem or base")
    data, rules = value["dataset"], value["split_rules"]
    if not isinstance(data, dict) or not isinstance(rules, dict):
        return errors + ["overlay dataset/split_rules must be objects"]
    if data.get("id") != stem or any(_nested_id(v) for v in data.values()):
        errors.append("overlay dataset identity missing or nested id")
    family = data.get("family")
    if not _identifier(family) or family not in base_families or rules.get("family") != family:
        errors.append("overlay family requires matching base representative")
    if set(rules) & {"seed", "dev_fraction", "sets", "schema", "lists"}:
        errors.append("overlay split_rules cannot declare globals")
    names = task_names(value)
    if not names or any(n not in tasks_on_disk or tasks_on_disk[n].set != stem for n in names):
        errors.append("overlay tasks missing or set mismatch")
    mapping = data.get("map")
    primary = mapping.get("primary_variant") if isinstance(mapping, dict) else None
    variants = [tasks_on_disk[n].variant for n in names if n in tasks_on_disk]
    if not _identifier(primary) or primary not in variants or len(set(variants)) != len(variants):
        errors.append("overlay primary variant missing or ambiguous tasks")
    return errors
