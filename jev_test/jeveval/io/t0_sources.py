"""무엇: T0 공개 원본·풀 읽기 · 입력: root/분할 규칙 · 출력: T0Sources · 계약 §8-7 T-c."""

from pathlib import Path

from jeveval.data.grouping import group_rows
from jeveval.io.config import read_yaml
from jeveval.io.sources import read_set_rows
from jeveval.io.splits import read_split_plan
from jeveval.types.t0_io import T0Sources

PUBLIC_SETS = ("kmhas", "kote_escalation", "korfin_asc", "klue_mrc_answerable", "kosgd", "kosgd2")


def read_sources(root, selected=PUBLIC_SETS):
    """명시된 공개 셋 경로만 허용한다. FunctionChat/AI-Hub는 reader 호출 전에 거부한다."""
    root = Path(root).resolve()
    rules = read_yaml(root / "configs/splits/rules.yaml")
    rows, groups, pools = {}, {}, {}
    for name in selected:
        if name not in PUBLIC_SETS:
            raise ValueError("T0 source set forbidden")
        cfg = rules["sets"][name]
        base = (root / "dataset" / name).resolve()
        if not base.is_relative_to(root / "dataset") or base.name != name:
            raise ValueError("T0 source outside public set")
        for key in ("file", "dir", "votes"):
            if key in cfg["source"] and not (root / cfg["source"][key]).resolve().is_relative_to(base):
                raise ValueError("T0 source outside public set")
        rows[name] = read_set_rows(name, cfg, root)
        groups[name] = group_rows(rows[name], cfg["group_key"])
        pools[name] = set(read_split_plan(root / "configs/splits" / f"{name}.json").groups)
    families = {name: rules["sets"][name].get("family", name) for name in rows}
    for name, fam in families.items():
        for other, cfg in rules["sets"].items():
            if other != name and cfg.get("family", other) == fam:
                pools[name].update(read_split_plan(root / "configs/splits" / f"{other}.json").groups)
    return T0Sources(rows, groups, pools, rules["seed"], families)
