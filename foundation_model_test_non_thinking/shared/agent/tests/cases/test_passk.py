from _harness import _assert, _assert_close, score_run

def test_passk_det_passes_if_one_repetition_primary_is_full():
    records = []
    for index in range(5):
        tool = "A" if index == 3 else "B"
        records.append({
            "rep_index": index,
            "success": True,
            "tool_calls": [{"tool_name": tool, "arguments": {}, "success": True}],
        })
    task = {
        "task_id": "L2-passk",
        "level": 2,
        "golden_action": [{"tool": "A", "args": {}}],
        "tool_calls": [],
        "repetitions": 5,
        "repetition_results": [True] * 5,
        "repetition_records": records,
    }
    bench_task = {"task_id": "L2-passk", "golden_action": task["golden_action"]}
    summary = score_run.score_level("L2", {"results": [task]}, {"L2-passk": bench_task})
    entry = summary["metrics"]["PassK_det"]
    _assert_close(entry["score"], 1.0, "PassK_det one full repetition passes")
    _assert(entry["primary_metric"] == "SelectAcc", "L2 primary")
    _assert(entry["k"] == 5, "PassK_det k")



def test_passk_det_not_in_representative_score():
    records = []
    for index in range(5):
        tool = "A" if index == 0 else "B"
        records.append({
            "rep_index": index,
            "success": True,
            "tool_calls": [{"tool_name": tool, "arguments": {}, "success": True}],
        })
    task = {
        "task_id": "L2-passk-score",
        "level": 2,
        "golden_action": [{"tool": "A", "args": {}}],
        "tool_calls": [],
        "repetitions": 5,
        "repetition_results": [True] * 5,
        "repetition_records": records,
    }
    bench_task = {"task_id": "L2-passk-score", "golden_action": task["golden_action"]}
    summary = score_run.score_level("L2", {"results": [task]}, {"L2-passk-score": bench_task})
    _assert_close(summary["metrics"]["SelectAcc"]["score"], 0.2, "SelectAcc repeated average")
    _assert_close(summary["metrics"]["PassK_det"]["score"], 1.0, "PassK_det score")
    _assert(summary["metrics"]["PassK_det"]["in_score"] is False, "PassK_det in_score")
    _assert_close(
        summary["score"],
        0.13333333333333333,
        "PassK_det excluded from representative score",
    )



TESTS = [
    test_passk_det_passes_if_one_repetition_primary_is_full,
    test_passk_det_not_in_representative_score,
]
