"""무엇: 원본 묶음 계산 · 입력: SourceRow·규칙 · 출력: Groups · 계약 §6 보정 6."""

from collections import defaultdict
import json

from jeveval.types import Groups, SourceRow


def _identifier(value: str) -> str:
    """logical_id의 구분자와 빈 ID를 거부한다."""
    if not isinstance(value, str) or not value or ":" in value:
        raise ValueError("IDs must be nonempty strings without ':'")
    return value


def _components(rows: list[SourceRow]) -> list[list[SourceRow]]:
    """첫 USER 내용 또는 전체 도구 객체의 일치를 union-find로 연결한다."""
    parent = {row.row_id: row.row_id for row in rows}

    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    seen = {}
    for row in rows:
        messages = row.fields["input_messages"]
        user = next((m for m in messages if m["role"] == "user"), None)
        if user is None or not isinstance(user["content"], str):
            raise ValueError("FunctionChat requires a user content string")
        tools = json.dumps(row.fields["input_tools"], sort_keys=True, ensure_ascii=False)
        for key in (("user", user["content"]), ("tools", tools)):
            if key in seen:
                a, b = find(row.row_id), find(seen[key])
                parent[max(a, b)] = min(a, b)
            else:
                seen[key] = row.row_id
    buckets = defaultdict(list)
    for row in rows:
        buckets[find(row.row_id)].append(row)
    return list(buckets.values())


def _buckets(rows: list[SourceRow], rule: str) -> list[list[SourceRow]]:
    """문자열을 변환하지 않고 정확 일치로 묶는다."""
    if rule == "fc_components":
        return _components(rows)
    if rule not in {"dialogue_id", "text", "SRC", "context"}:
        raise ValueError(f"unknown grouping rule: {rule}")
    buckets = defaultdict(list)
    for row in rows:
        key = row.fields[rule]
        if not isinstance(key, str):
            raise ValueError(f"{rule} must be a string")
        buckets[key].append(row)
    return list(buckets.values())


def _group_id(rows: list[SourceRow], rule: str) -> str:
    """셋별 최소 ID 규칙으로 원문이 아닌 묶음 ID를 만든다."""
    if rule == "dialogue_id":
        return rows[0].fields["dialogue_id"]
    if rule == "SRC":
        return min(row.fields["SID"] for row in rows).split("_")[0]
    if rule == "context":
        if len({row.fields["source"] for row in rows}) != 1:
            raise ValueError("KLUE context has inconsistent source")
        return min(row.fields["guid"] for row in rows)
    return str(min(int(row.row_id) for row in rows))


def group_rows(rows: list[SourceRow], rule: str) -> Groups:
    """원본 연결은 모두 유지하되 KorFin 구성원은 SRC 항목 하나로 축약한다."""
    if len({row.set for row in rows}) > 1:
        raise ValueError("cannot group different sets")
    seen = set()
    for row in rows:
        _identifier(row.row_id)
        if row.row_id in seen:
            raise ValueError(f"duplicate row_id: {row.row_id}")
        seen.add(row.row_id)
    mapping, members = {}, {}
    for bucket in _buckets(rows, rule):
        gid = _identifier(_group_id(bucket, rule))
        if gid in members:
            raise ValueError(f"group_id collision: {gid}")
        items = []
        for row in bucket:
            mapping[row.row_id] = gid
            item = str(row.fields["turn_index"]) if rule == "dialogue_id" else row.row_id
            items.append(_identifier(gid if rule == "SRC" else item))
        if rule != "SRC" and len(set(items)) != len(items):
            raise ValueError(f"duplicate item_id in group: {gid}")
        members[gid] = [gid] if rule == "SRC" else sorted(items)
    return Groups(dict(sorted(mapping.items())), dict(sorted(members.items())))
