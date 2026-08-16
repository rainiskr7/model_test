from _harness import (
    _assert,
    _assert_close,
    _bench_map,
    _l2_task,
    _l6_no_call_task,
    _task_id_producer,
    _toy_task,
    _with_level_specs,
    score_run,
)
from pathlib import Path

def test_agent_score_scored_task_count_weighting_differs_from_equal_mean():
    l2_tasks = [_l2_task("L2-weight-1", "A")]
    l6_tasks = [
        _l6_no_call_task("L6-weight-1"),
        _l6_no_call_task("L6-weight-2"),
        _l6_no_call_task("L6-weight-3"),
    ]
    summary = score_run.build_summary_from_loaded(
        {"L2": {"results": l2_tasks}, "L6": {"results": l6_tasks}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L2": _bench_map(l2_tasks), "L6": _bench_map(l6_tasks)},
        bench_pin_value={"tasks_sha256": {}},
    )
    _assert_close(summary["by_level"]["L2"]["score"], 1.0, "L2 score")
    _assert_close(summary["by_level"]["L6"]["score"], 0.5, "L6 score")
    _assert_close(summary["agent_score"], 0.625, "weighted agent score")
    _assert_close(summary["agent_score_equal_level"], 0.75, "equal-level agent score")
    _assert(summary["agent_score"] != summary["agent_score_equal_level"], "scores should differ")
    _assert(summary["weighting"]["weights"] == {"L2": 1, "L6": 3}, "weights")



def test_agent_score_excludes_none_score_from_weighting():
    l2_tasks = [_l2_task("L2-weight-none", "A")]
    summary = score_run.build_summary_from_loaded(
        {"L2": {"results": l2_tasks}, "L7": {"results": []}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L2": _bench_map(l2_tasks), "L7": {}},
        bench_pin_value={"tasks_sha256": {}},
    )
    _assert(summary["by_level"]["L7"]["score"] is None, "L7 should be unscorable")
    _assert_close(summary["agent_score"], 1.0, "weighted with None excluded")
    _assert(summary["weighting"]["weights"] == {"L2": 1}, "None score excluded")



def test_agent_score_no_scores_has_empty_weights():
    summary = score_run.build_summary_from_loaded(
        {"L7": {"results": []}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L7": {}},
        bench_pin_value={"tasks_sha256": {}},
    )
    _assert(summary["agent_score"] is None, "no scores weighted score")
    _assert(summary["agent_score_equal_level"] is None, "no scores equal-level score")
    _assert(summary["weighting"]["weights"] == {}, "empty weights")



def test_average_metric_records_n_tasks_for_scored_values():
    tasks = [_toy_task("score-me"), _toy_task("skip-me")]
    spec = score_run.MetricSpec("Toy", _task_id_producer({"score-me"}), True)
    entry = score_run._average_metric(tasks, spec)
    _assert_close(entry["score"], 1.0, "toy metric score")
    _assert(entry["n_tasks"] == 1, "n_tasks counts scored tasks")



def test_score_level_scored_tasks_matches_total_when_all_metrics_score_all_tasks():
    tasks = [_l2_task("L2-scored-all-1", "A"), _l2_task("L2-scored-all-2", "A")]
    summary = score_run.score_level("L2", {"results": tasks}, _bench_map(tasks))
    _assert(summary["scored_tasks"] == summary["total"], "scored_tasks should match total")



def test_score_level_scored_tasks_uses_union_across_in_score_metrics():
    tasks = [_toy_task("task-1"), _toy_task("task-2"), _toy_task("task-3")]
    specs = (
        score_run.MetricSpec("ToyA", _task_id_producer({"task-1", "task-2"}), True),
        score_run.MetricSpec("ToyB", _task_id_producer({"task-2", "task-3"}), True),
    )

    def _run():
        return score_run.score_level("L1", {"results": tasks}, _bench_map(tasks))

    summary = _with_level_specs("L1", specs, _run)
    _assert(summary["metrics"]["ToyA"]["n_tasks"] == 2, "ToyA individual count")
    _assert(summary["metrics"]["ToyB"]["n_tasks"] == 2, "ToyB individual count")
    _assert(summary["scored_tasks"] == 3, "scored_tasks must be union count")



def test_agent_score_weights_by_scored_tasks_not_total():
    l1_tasks = [_toy_task("L1-score-1"), _toy_task("L1-score-2"), _toy_task("L1-skip-3")]
    l2_tasks = [_toy_task("L2-score-1")]
    specs_l1 = (score_run.MetricSpec("ToyL1", _task_id_producer({"L1-score-1", "L1-score-2"}), True),)
    specs_l2 = (score_run.MetricSpec("ToyL2", _task_id_producer({"L2-score-1"}, 0.0), True),)
    original_l1 = score_run.LEVEL_SPECS["L1"]
    original_l2 = score_run.LEVEL_SPECS["L2"]
    score_run.LEVEL_SPECS["L1"] = specs_l1
    score_run.LEVEL_SPECS["L2"] = specs_l2
    try:
        summary = score_run.build_summary_from_loaded(
            {"L1": {"results": l1_tasks}, "L2": {"results": l2_tasks}},
            Path("/tmp/results/x/t/language/agent"),
            bench_task_maps={"L1": _bench_map(l1_tasks), "L2": _bench_map(l2_tasks)},
            bench_pin_value={"tasks_sha256": {}},
        )
    finally:
        score_run.LEVEL_SPECS["L1"] = original_l1
        score_run.LEVEL_SPECS["L2"] = original_l2

    scored_weighted = (1.0 * 2 + 0.0 * 1) / 3
    total_weighted = (1.0 * 3 + 0.0 * 1) / 4
    _assert(summary["by_level"]["L1"]["total"] == 3, "L1 total")
    _assert(summary["by_level"]["L1"]["scored_tasks"] == 2, "L1 scored_tasks")
    _assert_close(summary["agent_score"], scored_weighted, "scored task weighted score")
    _assert(summary["agent_score"] != total_weighted, "must differ from total weighting")



def test_weighting_excludes_level_with_zero_scored_tasks():
    l1_tasks = [_toy_task("L1-unscored-1"), _toy_task("L1-unscored-2")]
    l2_tasks = [_toy_task("L2-scored-1")]
    specs_l1 = (score_run.MetricSpec("ToyL1", _task_id_producer(set()), True),)
    specs_l2 = (score_run.MetricSpec("ToyL2", _task_id_producer({"L2-scored-1"}), True),)
    original_l1 = score_run.LEVEL_SPECS["L1"]
    original_l2 = score_run.LEVEL_SPECS["L2"]
    score_run.LEVEL_SPECS["L1"] = specs_l1
    score_run.LEVEL_SPECS["L2"] = specs_l2
    try:
        summary = score_run.build_summary_from_loaded(
            {"L1": {"results": l1_tasks}, "L2": {"results": l2_tasks}},
            Path("/tmp/results/x/t/language/agent"),
            bench_task_maps={"L1": _bench_map(l1_tasks), "L2": _bench_map(l2_tasks)},
            bench_pin_value={"tasks_sha256": {}},
        )
    finally:
        score_run.LEVEL_SPECS["L1"] = original_l1
        score_run.LEVEL_SPECS["L2"] = original_l2

    _assert(summary["by_level"]["L1"]["total"] == 2, "L1 total remains task count")
    _assert(summary["by_level"]["L1"]["scored_tasks"] == 0, "L1 scored_tasks zero")
    _assert("L1" not in summary["weighting"]["weights"], "zero-scored level excluded")
    _assert(summary["weighting"]["weights"] == {"L2": 1}, "only scored level weighted")



def test_weighting_scheme_is_scored_task_count():
    tasks = [_toy_task("L1-scheme")]
    specs = (score_run.MetricSpec("Toy", _task_id_producer({"L1-scheme"}), True),)

    def _run():
        return score_run.build_summary_from_loaded(
            {"L1": {"results": tasks}},
            Path("/tmp/results/x/t/language/agent"),
            bench_task_maps={"L1": _bench_map(tasks)},
            bench_pin_value={"tasks_sha256": {}},
        )

    summary = _with_level_specs("L1", specs, _run)
    _assert(summary["weighting"]["scheme"] == "scored_task_count", "weighting scheme")



def test_record_only_metrics_do_not_contribute_to_scored_tasks():
    tasks = [_toy_task("task-1"), _toy_task("task-2"), _toy_task("task-3")]
    specs = (
        score_run.MetricSpec("ToyInScore", _task_id_producer({"task-1"}), True),
        score_run.MetricSpec("ToyRecordOnly", _task_id_producer({"task-1", "task-2", "task-3"}), False),
    )

    def _run():
        return score_run.score_level("L1", {"results": tasks}, _bench_map(tasks))

    summary = _with_level_specs("L1", specs, _run)
    _assert(summary["metrics"]["ToyInScore"]["n_tasks"] == 1, "in_score n_tasks")
    _assert(summary["metrics"]["ToyRecordOnly"]["n_tasks"] == 3, "record-only n_tasks")
    _assert(summary["scored_tasks"] == 1, "record-only must not affect scored_tasks")



TESTS = [
    test_agent_score_scored_task_count_weighting_differs_from_equal_mean,
    test_agent_score_excludes_none_score_from_weighting,
    test_agent_score_no_scores_has_empty_weights,
    test_average_metric_records_n_tasks_for_scored_values,
    test_score_level_scored_tasks_matches_total_when_all_metrics_score_all_tasks,
    test_score_level_scored_tasks_uses_union_across_in_score_metrics,
    test_agent_score_weights_by_scored_tasks_not_total,
    test_weighting_excludes_level_with_zero_scored_tasks,
    test_weighting_scheme_is_scored_task_count,
    test_record_only_metrics_do_not_contribute_to_scored_tasks,
]
