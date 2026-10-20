"""무엇: 단일 실행 채점 명령 · 입력: 완료 단계·봉인 · 출력: risk/scores/summary · 계약 §7."""

from hashlib import sha256

from jeveval.contract.stages import stage_names
from jeveval.io.set_config import entry
from jeveval.score.set_metrics import metric_spec
from jeveval.io import records, run_files
from jeveval.io.hashes import sha256_file
from jeveval.run import context
from jeveval.run.seal import check_seal
from jeveval.run.summary import summary_from_risk
from jeveval.score.cost import cost_by_stage
from jeveval.score.population import population, score_table
from jeveval.score.risk import risk_cell, risk_file
from jeveval.score.threshold import TAUS
from jeveval.score.selective_artifact import build
from jeveval.types import ThresholdFile


def run(*, root, run_dir):
    ctx = context.restore(root, run_dir)
    spec = metric_spec(entry(ctx.root, ctx.task.set).family)
    directory = ctx.directory
    if not run_files.exists(directory / "test/seal.json") or check_seal(directory):
        raise ValueError("valid seal required")
    names = stage_names(ctx.task.set)
    stages = {name: context.stage(ctx, name) for name in names}
    warnings = [w for data in stages.values() for w in data.warnings]
    threshold = run_files.read_json(directory / "threshold.json", ThresholdFile)
    context.check_identity(ctx, threshold.to_dict())
    cells = {tau: risk_cell(tau=tau, threshold=threshold.by_tau[tau],
        dev=stages["dev"].outcomes, test=stages["test"].outcomes,
        test_items=stages["test"].items, spec=spec) for tau in TAUS}
    risk = risk_file(**context.identity(ctx), cells=cells,
                     threshold_sha256=sha256_file(directory / "threshold.json"))
    test = stages["test"]
    populations = {"test": population(outcomes=test.outcomes, finals=test.finals, items=test.items,
        certified=True, unit="group_representative", set_name=ctx.task.set, spec=spec)}
    if "extra" in stages:
        populations["all_rows"] = population(
            outcomes=[r for data in stages.values() for r in data.outcomes],
            finals=[f for data in stages.values() for f in data.finals],
            items={lid: item for data in stages.values() for lid, item in data.items.items()},
            certified=False, unit="row", set_name=ctx.task.set, spec=spec)
    costs = _costs(directory, stages, warnings)
    scores = score_table(**context.identity(ctx), populations=populations,
                         cost=cost_by_stage(costs, ctx.cfg.kind))
    summary = summary_from_risk(risk=risk, model=ctx.cfg.id, set=ctx.task.set,
        variant=ctx.task.variant, primary_variant=context.primary_variant(ctx),
        t0_status=ctx.cfg.t0["status"])
    if summary is None and run_files.exists(directory / "summary.json"):
        raise ValueError("nonprimary summary already exists")
    selective = build(test.outcomes, context.identity(ctx),
        {"risk.json": sha256(run_files.json_bytes(risk)).hexdigest(),
         "test/final.jsonl": sha256_file(directory / "test/final.jsonl")}, risk)
    outputs = {"risk.json": risk, "scores.json": scores, "selective.json": selective}
    if summary is not None:
        outputs["summary.json"] = summary
    for value in outputs.values():
        run_files.json_bytes(value)
    for name, value in outputs.items():
        run_files.write_json(directory / name, value)
    return dict(ok=True, warnings=warnings)


def _costs(directory, stages, warnings):
    """단계 비용 입력을 읽고 파생 출처를 확인한다."""
    costs = {}
    for name, data in stages.items():
        attempts, pending = records.read_attempts(directory / name / "attempts.jsonl")
        warnings.extend(pending)
        marker = directory / name / "derived.json"
        source = run_files.read_json(marker)["derived_from"] if run_files.exists(marker) else None
        if any(f.derived_from != source for f in data.finals) or (source is not None and attempts):
            raise ValueError("derived provenance mismatch")
        costs[name] = (data.finals, attempts, source)
    return costs
