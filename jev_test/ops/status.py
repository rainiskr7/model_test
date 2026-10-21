"""무엇: 단계 수량 관측 · 입력: 모델/run · 출력: 원문 없는 TSV · 계약 §7-6."""

from collections import Counter
from pathlib import Path
import sys

from jeveval.contract.stages import stage_names
from jeveval.io import records, run_files
from jeveval.io.paths import identifier
from jeveval.io.splits import read_split_plan


VARIANTS = (("klue_mrc_answerable", "default"), ("korfin_asc", "default"),
            ("fc_call_decision", "default"), ("kmhas", "default"), ("kote_escalation", "default"),
            ("kosgd", "full"), ("kosgd", "actions_only"),
            ("kosgd2", "full"), ("kosgd2", "actions_only"))


def rows(root, model, run_id):
    model, run_id = identifier(model), identifier(run_id)
    for name, variant in VARIANTS:
        plan = read_split_plan(root / f"configs/splits/{name}.json")
        directory = root / "results" / model / run_id / "A" / name / variant
        for stage in stage_names(name):
            expected = plan.extra if stage == "extra" else [plan.representative[g] for g in getattr(plan, stage)]
            finals, fw = records.read_finals(directory / stage / "final.jsonl")
            attempts, aw = records.read_attempts(directory / stage / "attempts.jsonl")
            ids = {f.logical_id for f in finals}
            counts = Counter(f.status for f in finals)
            presence = [run_files.exists(directory / path) for path in
                        ("test/seal.json", "threshold.json", "risk.json", "scores.json", "summary.json",
                         f"{stage}/derived.json", f"{stage}/replay.json", "selective.json",
                         "test/question_seal.json", "test/variant_seal.json")]
            yield [name, variant, stage, len(expected), len(ids), ids == set(expected),
                   ",".join(f"{s}:{counts[s]}" for s in sorted(counts)), len(attempts),
                   len({a.call_id for a in attempts}), ",".join(fw + aw) or "-", *presence]


def main():
    print("set\tvariant\tstage\texpected_logical\tunique_final\tids_equal\tfinal_statuses\t"
          "parsed_attempt_lines\tunique_calls\twarnings\tseal\tthreshold\trisk\tscores\tsummary\tderived\treplay\tselective\tquestion_seal_present\tvariant_seal_present")
    try:
        for row in rows(Path.cwd(), *sys.argv[1:]):
            print("\t".join(map(str, row)))
    except Exception:
        print("status input check failed; no completion claim", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
