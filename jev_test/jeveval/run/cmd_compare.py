"""무엇: 모델 횡단 비교 조립 · 입력: 완료 run 폴더 · 출력: compare.json · 계약 §8-6 L·⑥b-2."""

from jeveval.io import run_files, run_inputs
from jeveval.run.layout import compare_dir
from jeveval.score.bootstrap import coverage_diff, f1_diff
from jeveval.score.compare import check_comparable, common_cohort, compare_file
from jeveval.score.observations import observations, question_ids
from jeveval.score.population import population


def _metadata(ctx, stages):
    fp = ctx.fingerprint
    return dict(split_sha256=fp["files"][f"configs/splits/{ctx.task.set}.json"],
                task_sha256=fp["files"][fp["inputs"]["task_path"]],
                test_logical_ids=[f.logical_id for f in stages["test"].finals])


def _f1(stages, stage_names, seed, set_name):
    rows = {m: [r for name in stage_names for r in data[name].outcomes] for m, data in stages.items()}
    items = {m: {lid: item for name in stage_names for lid, item in data[name].items.items()}
             for m, data in stages.items()}
    cohort = common_cohort(rows, "test" if stage_names == ("test",) else "all_rows")
    obs = {m: observations(value, items[m]) for m, value in rows.items()}
    qids = sorted({q for value in items.values() for q in question_ids(value)})
    return {q: f1_diff(obs, cohort, seed=seed, set_name=set_name, question_id=q) for q in qids}


def _result(contexts, stages, thresholds):
    first = next(iter(contexts.values()))
    set_name, variant, seed = first.task.set, first.task.variant, first.plan.seed
    rows = {m: data["test"].outcomes for m, data in stages.items()}
    cohort = common_cohort(rows)
    populations = {m: population(outcomes=[r for r in rows[m] if r.logical_id in cohort],
        finals=[f for f in data["test"].finals if f.logical_id in cohort], items=data["test"].items,
        certified=False, unit="group_representative", set_name=set_name) for m, data in stages.items()}
    bootstrap = dict(coverage={"0.02": coverage_diff(rows,
        {m: t.by_tau["0.02"].t_star for m, t in thresholds.items()}, seed=seed, set_name=set_name)},
        f1={"test": _f1(stages, ("test",), seed, set_name)})
    if set_name == "fc_call_decision":
        bootstrap["f1"]["all_rows"] = _f1(stages, ("dev", "test", "extra"), seed, set_name)
    return compare_file(models=contexts, set=set_name, variant=variant, cohort_ids=cohort,
        per_model_population=populations, bootstrap=bootstrap,
        t0_status={m: ctx.cfg.t0["status"] for m, ctx in contexts.items()})


def run(*, root, run_dirs, compare_id, results="results"):
    contexts, stages, thresholds, metadata = {}, {}, {}, {}
    for directory in run_dirs:
        ctx, data, threshold = run_inputs.completed(root, directory)
        model = ctx.fingerprint["model"]
        if model in contexts:
            raise ValueError("duplicate comparison model")
        contexts[model], stages[model], thresholds[model] = ctx, data, threshold
    if len({(c.task.set, c.task.variant) for c in contexts.values()}) != 1:
        raise ValueError("comparison set/variant differs")
    metadata = {m: _metadata(ctx, stages[m]) for m, ctx in contexts.items()}
    if check_comparable(metadata):
        raise ValueError("incomparable runs")
    value = _result(contexts, stages, thresholds)
    directory = compare_dir(run_inputs.inside(root, results), compare_id, value["set"], value["variant"])
    run_files.json_bytes(value)
    run_files.make_directory(directory)
    run_files.write_json(directory / "compare.json", value)
    return dict(ok=True, warnings=[w for data in stages.values() for stage in data.values() for w in stage.warnings])
