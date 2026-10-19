"""감사 v4 오프라인 조립 CLI. kosgd2 프로필이 종전 v5 역할을 포함한다."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from audits.audit_v4 import checks, evidence, selftest
from audits.audit_v4.independent import source, labels, timing
from audits.audit_v4.offline import guard
from audits.audit_v4.preservation import snapshot, verify
from jeveval.io.paths import inside


def base_rules(root, set_name):
    try:
        dialogues, selected, cat, _, linked = source.load(root, set_name)
        return {v: dict(R5=labels.coverage(dialogues, selected, cat, v, set_name),
                        R6=timing.check(dialogues) if v == "full" else dict(status="NOT_APPLICABLE"),
                        source_links=linked) for v in ("full", "actions_only")}
    except FileNotFoundError:
        status = "INCOMPLETE"
    except Exception:
        status = "FAIL"
    return {v: dict(R5=dict(status=status), R6=dict(status="INCOMPLETE" if v == "full" else "NOT_APPLICABLE"),
                    source_links={"available": False}) for v in ("full", "actions_only")}


def aggregate(base, models, injections):
    for variant, rules in base.items():
        for rule in ("R2v3", "R4", "R7", "v4_hash"):
            statuses = []
            for model in (evidence.FROZEN if rule == "v4_hash" else evidence.MODELS):
                value = models[model].get("variants", {}).get(variant, {}).get(rule, "INCOMPLETE")
                statuses.append(value["status"] if isinstance(value, dict) else value)
            if rule == "R7":
                statuses.append(injections["status"])
            rules[rule] = dict(status=checks.combine(statuses))
        if not all(rules["source_links"].values()):
            rules["R4"]["status"] = "FAIL" if rules["R5"]["status"] != "INCOMPLETE" else "INCOMPLETE"
    return base


def run(root, set_name, out, history_runs=(), oracle_source=None):
    root = Path(root).resolve()
    out = inside(root, out)
    if not out.is_relative_to(root / "audits/audit_v4/out"):
        raise ValueError("audit output outside allowed directory")
    protected = snapshot(root)
    if out.exists():
        raise ValueError("audit output exists")
    before, code = evidence.inputs(root, set_name), evidence.code(root)
    oracle_sha = None if oracle_source is None else evidence.hashes.sha256_file(oracle_source)
    base, models = base_rules(root, set_name), {}
    worker = Path(__file__).with_name("worker.py")
    for model in evidence.MODELS:
        process = subprocess.run([sys.executable, "-B", "-I", str(worker), "--root", str(root),
                                  "--set", set_name, "--model", model], capture_output=True, text=True)
        try:
            models[model] = json.loads(process.stdout) if process.returncode == 0 else dict(status="INCOMPLETE")
        except ValueError:
            models[model] = dict(status="INCOMPLETE")
    injections = selftest.run(set_name)
    rules = aggregate(base, models, injections)
    candidates = [v for v in ("full", "actions_only") if all(rules[v][r]["status"] in ("PASS", "NOT_APPLICABLE")
                  for r in ("R2v3", "R4", "R5", "R6", "R7", "v4_hash"))]
    history = evidence.historical(root, history_runs, models, before) if set_name == "kosgd" else None
    if oracle_source is not None and oracle_sha != evidence.hashes.sha256_file(oracle_source):
        raise ValueError("oracle source changed")
    if before != evidence.inputs(root, set_name) or code != evidence.code(root):
        raise ValueError("audit inputs changed")
    result = dict(schema="audit_v4/1", set=set_name, profile=set_name, retrospective=set_name == "kosgd",
                  inputs=before, code=code, per_variant=rules, models=models, historical_calls=history,
                  primary_variant_candidate=next(iter(candidates), None), injections=injections, real_model_calls=0,
                  oracle_verification=dict(status="INCOMPLETE", source_sha256=oracle_sha))
    verify(protected, snapshot(root))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    p.add_argument("--set", choices=("kosgd", "kosgd2"), required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--history-run", action="append", default=[])
    p.add_argument("--oracle-source", help="record independent oracle source SHA only; never execute it")
    a = p.parse_args()
    try:
        with guard():
            result = run(a.root, a.set, a.out, a.history_run, a.oracle_source)
        print(json.dumps(dict(set=a.set, primary_variant_candidate=result["primary_variant_candidate"], real_model_calls=0)))
        return 0 if result["primary_variant_candidate"] == "full" else 2
    except Exception:
        print('{"status":"INCOMPLETE","error":"audit input or output unavailable"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
