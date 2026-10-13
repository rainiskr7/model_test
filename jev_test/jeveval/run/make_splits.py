"""무엇: 분할 생성 CLI · 입력: 규칙/root/set/out · 출력: 분할 JSON·요약 · 계약 §6·§8."""

import argparse
from pathlib import Path

from jeveval.data.grouping import group_rows
from jeveval.data.pool import select_pool
from jeveval.data.split import build_split_plan
from jeveval.io.config import read_yaml
from jeveval.io.sources import functionchat, klue_mrc, kmhas, korfin, kosgd, kote
from jeveval.io.splits import write_split_plan


READERS = {"kosgd": kosgd, "fc_call_decision": functionchat, "kmhas": kmhas,
           "kote_escalation": kote, "korfin_asc": korfin, "klue_mrc_answerable": klue_mrc}


def _make_plan(set_name, cfg, rules, root):
    """입출력 결과를 순수 계산에 연결한다."""
    reader = READERS[set_name]
    kwargs = {"votes_cfg": cfg["votes"]} if set_name == "kote_escalation" else {}
    rows = reader.read_rows(cfg["source"], root, **kwargs)
    groups = group_rows(rows, cfg["group_key"])
    if "expect_groups" in cfg and len(groups.members) != cfg["expect_groups"]:
        raise ValueError(f"{set_name}: expected {cfg['expect_groups']} groups, got {len(groups.members)}")
    fixed = kosgd.read_selection(cfg["pool"], root) if cfg["pool"]["kind"] == "fixed_selection" else None
    label_names = kote.read_label_names(cfg["source"], root) if "demotion" in cfg else None
    field = cfg["pool"].get("stratum_field")
    strata = {groups.row_to_group[r.row_id]: r.fields[field] for r in rows} if field else None
    pool = select_pool(groups, cfg["pool"], rules["seed"], set_name, strata, fixed)
    return build_split_plan(rows, groups, pool, set_name, cfg, rules["seed"],
                            rules["dev_fraction"], fixed, label_names)


def _summary(plan):
    """행·묶음·풀·단계·강등·충돌의 고정된 한 줄 표시."""
    n = plan.notes
    return (f"{plan.set}: rows={n['n_rows']} groups={n['n_groups_total']} "
            f"pool={n['n_pool_groups']} dev={len(plan.dev)} test={len(plan.test)} "
            f"extra={len(plan.extra)} demotions={len(plan.diagnostic_demotions)} "
            f"conflicts_total={n['label_conflict_groups_total']} "
            f"conflicts_pool={n['label_conflict_groups_pool']}")


def main(argv=None) -> int:
    """실패한 셋의 파일은 쓰지 않고 오류를 0 아닌 종료 코드로 알린다."""
    parser = argparse.ArgumentParser(description="Build deterministic evaluation splits")
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--set", choices=[*READERS, "all"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        rules = read_yaml(args.root / args.rules)
        selected = sorted(rules["sets"]) if args.set == "all" else [args.set]
        for set_name in selected:
            plan = _make_plan(set_name, rules["sets"][set_name], rules, args.root)
            write_split_plan(plan, args.out / f"{set_name}.json")
            print(_summary(plan))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f"make_splits: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
