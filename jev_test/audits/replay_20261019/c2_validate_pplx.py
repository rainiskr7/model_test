"""무엇: C2 현재 검증기 감사 · 입력: results 루트/run_id · 출력: 요청 단위 집계 · 계약 판 4."""

from collections import Counter
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jeveval.contract.response import validate_response
from jeveval.io import records, run_files
from jeveval.io.paths import identifier, inside
from jeveval.run import context, stage_inputs
from jeveval.run.plan_calls import plan_calls
from jeveval.run.resume_check import check_resume


def stage_summary(ctx, folder, stage):
    attempts, pending = records.read_attempts(folder / stage / "attempts.jsonl")
    if pending:
        raise ValueError("pending source")
    items = stage_inputs.load_items(root=ctx.root, task_path=ctx.task_path, stage=stage)
    plans = [p for item in items for p in plan_calls(item, ctx.task, ctx.cfg, ctx.b1)]
    if check_resume(plans, attempts, [], ctx.policy.max_attempts):
        raise ValueError("source plans differ")
    by_id = {p.call_id: p for p in plans}
    reasons, warnings = Counter(), Counter()
    n_requests = n_choice = n_range = n_choice_requests = n_differs = 0
    for row in attempts:
        if row.http_status != 200:
            continue
        request = by_id[row.call_id].request
        valid = validate_response(row.response_raw, request)
        n_requests += 1
        reasons[valid.reason or "valid"] += 1
        warnings.update(valid.warnings)
        choice_ids = [qid for qid, q in request.questions.items() if q["type"] == "choice"]
        n_choice += len(choice_ids)
        n_choice_requests += bool(choice_ids)
        n_differs += bool(choice_ids) and "confidence_differs" in valid.warnings
        if valid.answers is not None:
            for qid in choice_ids:
                c = valid.answers[qid]["confidence"]
                n_range += type(c) in (float, int) and math.isfinite(c) and 0 <= c <= 1
    return dict(set=ctx.task.set, variant=ctx.task.variant, stage=stage, n_requests=n_requests,
                n_choice_requests=n_choice_requests, n_choice_answers=n_choice, n_choice_in_range=n_range,
                n_choice_requests_warned=n_differs, reasons=dict(reasons), warnings=dict(warnings))


def audit(results_root, run_id):
    base = inside(ROOT, results_root) / "pplx_v1_1" / identifier(run_id)
    folders = sorted(base.glob("A/*/*/fingerprint.json"))
    if not folders:
        raise ValueError("source runs missing")
    rows = []
    for path in folders:
        fp = run_files.read_json(path)
        ctx = context.configuration(ROOT, fp["inputs"]["model_cfg_path"], fp["inputs"]["task_path"])
        if ctx.cfg.id != "pplx_v1_1" or ctx.cfg.kind != "systemone":
            raise ValueError("unexpected model")
        if ctx.task.variant == "actions_only" and ctx.cfg.question_scoring == "separate":
            continue
        for stage in ("dev", "test", "extra"):
            if run_files.exists(path.parent / stage / "attempts.jsonl"):
                rows.append(stage_summary(ctx, path.parent, stage))
    ok = bool(rows) and all(r["reasons"].get("valid", 0) == r["n_requests"]
        and r["n_choice_answers"] == r["n_choice_in_range"]
        and r["n_choice_requests"] == r["n_choice_requests_warned"]
        and (r["n_choice_requests"] or not r["warnings"].get("confidence_differs", 0)) for r in rows)
    return dict(ok=ok, rows=rows, n_requests=sum(r["n_requests"] for r in rows),
                n_choice_requests=sum(r["n_choice_requests"] for r in rows),
                n_choice_answers=sum(r["n_choice_answers"] for r in rows))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("arguments")
        result = audit(*sys.argv[1:])
    except Exception:
        result = dict(ok=False, error="audit input or validation failed")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if result["ok"] else 1)
