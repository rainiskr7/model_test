from _harness import _assert, _assert_close, level_spec, score_run

def test_l3_spec_shape():
    specs = level_spec.LEVEL_SPECS["L3"]
    by_name = {spec.name: spec for spec in specs}
    _assert(specs[0].name == "FSM_prefix", "L3 first metric")
    _assert(by_name["FSM_prefix"].in_score is True, "FSM_prefix in_score")
    _assert(by_name["FSM_strict"].in_score is False, "FSM_strict record-only")
    _assert(
        {spec.name for spec in specs if spec.in_score}
        == {"FSM_prefix", "PSM", "ΔSteps_norm", "ArgF1_det"},
        "L3 representative metrics",
    )



def test_l3_passk_primary_resolves_to_spec():
    primary = level_spec.PASSK_PRIMARY_METRICS["L3"]
    _assert(primary == "FSM_prefix", "L3 PassK_det primary")
    spec = next((spec for spec in level_spec.LEVEL_SPECS["L3"] if spec.name == primary), None)
    _assert(spec is not None, "L3 PassK_det primary must resolve")



def test_l3_representative_score_excludes_fsm_strict():
    task = {
        "task_id": "L3-prefix-extra",
        "level": 3,
        "golden_action": [
            {"tool": "Search", "args": {"q": "alpha"}},
            {"tool": "Read", "args": {"id": "doc-1"}},
        ],
        "minimum_steps": 2,
        "arg_schema": {},
        "tool_calls": [
            {
                "tool_name": "Search",
                "arguments": {"q": "alpha"},
                "success": True,
            },
            {
                "tool_name": "Read",
                "arguments": {"id": "doc-1"},
                "success": True,
            },
            {
                "tool_name": "Search",
                "arguments": {"q": "retry"},
                "success": False,
                "error": "Pseudo-API(read): cache miss",
            },
        ],
    }
    bench_task = {
        "task_id": "L3-prefix-extra",
        "golden_action": task["golden_action"],
        "minimum_steps": 2,
    }
    summary = score_run.score_level("L3", {"results": [task]}, {"L3-prefix-extra": bench_task})
    metrics = summary["metrics"]
    _assert_close(metrics["FSM_prefix"]["score"], 1.0, "L3 FSM_prefix")
    _assert_close(metrics["FSM_strict"]["score"], 0.0, "L3 FSM_strict")
    _assert(metrics["FSM_strict"]["in_score"] is False, "FSM_strict record-only")
    expected = (
        metrics["FSM_prefix"]["score"]
        + metrics["PSM"]["score"]
        + metrics["ΔSteps_norm"]["score"]
        + metrics["ArgF1_det"]["score"]
    ) / 4
    _assert_close(summary["score"], expected, "L3 score excludes FSM_strict")
    _assert(summary["score"] > 0.0, "L3 score unaffected by zero FSM_strict")



TESTS = [
    test_l3_spec_shape,
    test_l3_passk_primary_resolves_to_spec,
    test_l3_representative_score_excludes_fsm_strict,
]
