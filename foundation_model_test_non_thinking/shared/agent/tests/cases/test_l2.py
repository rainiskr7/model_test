from _harness import _assert, _assert_close, level_spec, score_run

def test_l2_spec_shape():
    in_score = [spec for spec in level_spec.LEVEL_SPECS["L2"] if spec.in_score]
    _assert(
        [spec.name for spec in in_score] == ["SelectAcc", "CallEM", "ArgF1_det"],
        "L2 representative metrics",
    )



def test_l2_passk_primary_resolves_to_spec():
    primary = level_spec.PASSK_PRIMARY_METRICS["L2"]
    _assert(primary == "SelectAcc", "L2 PassK_det primary")
    spec = next((spec for spec in level_spec.LEVEL_SPECS["L2"] if spec.name == primary), None)
    _assert(spec is not None, "L2 PassK_det primary must resolve")



def test_l2_correct_tool_wrong_args_not_full_score():
    task = {
        "task_id": "L2-wrong-args",
        "level": 2,
        "golden_action": [{"tool": "A", "args": {"q": "gold", "count": 30}}],
        "tool_calls": [
            {
                "tool_name": "A",
                "arguments": {"q": "actual"},
                "success": True,
            }
        ],
    }
    bench_task = {"task_id": "L2-wrong-args", "golden_action": task["golden_action"]}
    summary = score_run.score_level("L2", {"results": [task]}, {"L2-wrong-args": bench_task})
    metrics = summary["metrics"]
    _assert_close(metrics["SelectAcc"]["score"], 1.0, "L2 SelectAcc ignores args")
    _assert(metrics["CallEM"]["score"] < 1.0, "L2 CallEM catches wrong args")
    _assert(metrics["ArgF1_det"]["score"] < 1.0, "L2 ArgF1_det catches wrong args")
    _assert(summary["score"] < 1.0, "L2 representative score must not be full")



TESTS = [
    test_l2_spec_shape,
    test_l2_passk_primary_resolves_to_spec,
    test_l2_correct_tool_wrong_args_not_full_score,
]
