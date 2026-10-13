"""Assembly only: load -> build -> verify -> checks -> statistics -> report."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import os
from datetime import datetime, timezone

os.environ.setdefault("RAYON_NUM_THREADS", "4")

from build import catalog as catalog_builder, labels as label_builder, requests as request_builder
from checks import consistency, coverage, leak, length, timing
from common.io import fingerprint_files, required_files
from config import ENGLISH_DIR, KOSGD_DIR, PLAN_PATH, SCHEMA_PATH, SELECTION_PATH, TOKENIZER_PATHS
from load import kosgd, selection as selection_loader, sgd_en
from report import json_out, table
from selftest import run_injections
from stats import copy_baseline, distribution, version_diff
from verify import labels_independent, source_projection


def main():
    started_at = datetime.now(timezone.utc).isoformat()
    input_paths = (required_files(KOSGD_DIR, "dialogues_*.json", 34) + [SCHEMA_PATH, SELECTION_PATH, PLAN_PATH]
                   + required_files(ENGLISH_DIR, "dialogues_*.json"))
    inputs = fingerprint_files(input_paths)
    tokenizer_inputs = fingerprint_files(list(TOKENIZER_PATHS.values()))
    korean, schema, ko_paths = kosgd.load()
    english, _ = sgd_en.load()
    selected = selection_loader.load(korean)
    catalog = catalog_builder.build(schema)
    variants = request_builder.build(korean, selected, catalog)
    labels, facts = label_builder.build(korean, selected, catalog)
    independent = labels_independent.calculate(ko_paths[:-1], SCHEMA_PATH, SELECTION_PATH)
    source = source_projection.reconstruct(ko_paths[:-1], SCHEMA_PATH, SELECTION_PATH)
    r4 = leak.check_variants(variants, source)
    r5 = coverage.check(facts)
    r6 = timing.check(korean, selected)
    r7 = consistency.check_variants(variants, labels, independent)
    injections = run_injections(variants, labels, independent, source)
    r7 = consistency.include_injection_gate(r7, injections)
    rules = {"R2v3": length.check(variants, TOKENIZER_PATHS), "R4": r4, "R5": r5, "R6": r6, "R7": r7}
    statistics = {"copy_baseline": copy_baseline.calculate(korean, selected, catalog, facts),
                  "distribution": distribution.calculate(korean, selected, facts),
                  "version_diff": version_diff.calculate(korean, english, selected, facts)}
    if fingerprint_files(input_paths) != inputs or fingerprint_files(list(TOKENIZER_PATHS.values())) != tokenizer_inputs:
        raise RuntimeError("An input changed while the audit was running")
    report = json_out.create(rules, statistics, variants, inputs, tokenizer_inputs, started_at)
    json_out.write(report, variants)
    table.print_report(report)
    return 0 if report["primary_variant"] is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
