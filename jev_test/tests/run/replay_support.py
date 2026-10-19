"""무엇: 혼합 replay 통합 표본 · 입력: 합성 Harness · 출력: 다섯 상태의 test · 계약 §5-5c."""

from dataclasses import replace

from jeveval.io import records
from jeveval.io.splits import write_split_plan
from jeveval.run import context, stage_inputs


def mixed_source(h, monkeypatch):
    """실제 계획/실행기로 기록한 뒤 partial/retry/missing 시점의 attempts를 재현한다."""
    loaded = {s: stage_inputs.load_items(root=h.root, task_path=h.args["task"], stage=s)
              for s in ("dev", "test", "extra")}
    base = loaded["test"][0]
    names = ("complete", "partial", "retry", "missing", "local")
    items = [replace(base, group_id=n, item_id=n) for n in names]
    items[-1] = replace(items[-1], state_fields={})
    groups = {**{g: h.plan.groups[g] for g in h.plan.dev}, **{n: [n] for n in names}}
    reps = {**{g: h.plan.representative[g] for g in h.plan.dev}, **{n: f"{h.set}:{n}:{n}" for n in names}}
    h.plan = replace(h.plan, groups=groups, representative=reps, test=sorted(names), extra=[])
    write_split_plan(h.plan, h.root / f"configs/splits/{h.set}.json")
    loaded.update(test=items, extra=[])
    monkeypatch.setattr(stage_inputs, "load_items", lambda **kw: loaded[kw["stage"]])
    monkeypatch.setattr(context, "load_items", lambda **kw: loaded[kw["stage"]])
    h.run("dev")
    h.command("threshold")
    h.run("test")
    path = h.directory / "test/attempts.jsonl"
    original, _ = records.read_attempts(path)
    selected, seen = [], set()
    for row in original:
        name = row.logical_id.split(":")[1]
        first = name not in seen
        seen.add(name)
        if name == "missing" or name == "partial" and not first:
            continue
        if name == "retry" and first:
            row = replace(row, terminal=False, http_status=503, response_raw="{}")
        selected.append(row)
    path.write_bytes(b"".join(records.record_line(a) for a in selected))
    return {f"{i.set}:{i.group_id}:{i.item_id}" for i in items}
