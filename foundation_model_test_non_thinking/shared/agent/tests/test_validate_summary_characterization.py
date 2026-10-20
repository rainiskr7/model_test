"""Freeze validator output observed at HEAD 946d789791175c504cfff48d08c05b719864e072.

Fixture helpers are minimally adapted from test_agent_scoring.py: importing that
module eagerly loads unrelated modules and reads/executes runner helper ASTs.
No metric producers, benchmark checkout, or saved result artifacts are needed.
"""

import copy
import json

import pytest


from shared.agent.scoring import validate_run


def _level_matrix(specs):
    by_level = {}
    for index, (level, metric_specs) in enumerate(specs.items(), start=1):
        level_value = index / 10.0 if level != "L7" else None
        metric_value = level_value if level_value is not None else 0.5
        metrics = {
            spec.name: {
                "score": metric_value,
                "status": "ok",
                "in_score": spec.in_score,
                "n_tasks": 1,
                "n_scored": 1,
                "n_errors": 0,
                "task_spread": {"n_perfect": 0, "n_zero": 0, "n_partial": 1},
            }
            for spec in metric_specs
        }
        for name in validate_run.JUDGE_METRICS:
            metrics[name] = {
                "score": None, "status": "judge_missing", "in_score": False,
            }
        by_level[level] = {
            "total": 1,
            "score": level_value,
            "applied_metrics": sum(spec.in_score for spec in metric_specs),
            "metrics": metrics,
        }
    return by_level


def _validation_summary(version=2):
    summary = {
        "scoring_version": "agent_det_v2",
        "native_tool_calling": True,
        "agent_score": 0.35,
        "scored_levels": 6,
        "required_levels": 6,
        "agent_score_status": "complete",
        "by_level": _level_matrix(validate_run.LEVEL_SPECS),
    }
    if version >= 3:
        summary["scoring_v3"] = {
            "scoring_version": "agent_det_v3",
            "agent_score": 0.35,
            "scored_levels": 6,
            "required_levels": 6,
            "agent_score_status": "complete",
            "by_level": _level_matrix(validate_run.LEVEL_SPECS_V3),
            "task_data": {"join_needed": False},
        }
    if version >= 4:
        summary["scoring_v4"] = copy.deepcopy(summary["scoring_v3"])
        summary["scoring_v4"].update({
            "scoring_version": "agent_det_v4",
            "agent_score": 0.34,
            "scored_levels": 5,
            "required_levels": 5,
            "headline_levels": ["L1", "L2", "L3", "L5", "L6"],
            "excluded_levels": ["L4"],
        })
        summary["headline_denominators"] = {
            "agent_det_v2": ["L1", "L2", "L3", "L4", "L5", "L6"],
            "agent_det_v3": ["L1", "L2", "L3", "L4", "L5", "L6"],
            "agent_det_v4": ["L1", "L2", "L3", "L5", "L6"],
        }
    return summary


def _write_validation_fixture(results_dir, summary, native_overrides=None):
    native_overrides = native_overrides or {}
    (results_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    for level in summary["by_level"]:
        raw = {
            "metadata": {
                "success_rate": 0.5,
                "native_tool_calling": native_overrides.get(level, True),
            },
            "results": [{}],
        }
        (results_dir / f"{level}.json").write_text(json.dumps(raw), encoding="utf-8")


def _case_fixture(case, results_dir):
    version = {
        "v2_v3_valid": 3,
        "v4_valid": 4,
        "v4_wrong_level_sets": 4,
        "cache_miss_warning": 3,
        "version_mismatch": 4,
    }.get(case, 2)
    summary = _validation_summary(version)
    if case == "v4_wrong_level_sets":
        summary["scoring_v4"]["headline_levels"] = [
            "L1", "L2", "L3", "L4", "L5", "L6",
        ]
        summary["scoring_v4"]["excluded_levels"] = []
        summary["headline_denominators"]["agent_det_v4"] = [
            "L1", "L2", "L3", "L4", "L5", "L6",
        ]
    elif case == "cache_miss_warning":
        # Reverse insertion order and the exact 20% boundary are intentional.
        summary["cache_miss_diagnostics"] = {"by_level": {
            "L5": {"miss_rate": 0.5, "cache_misses": 2, "total_calls": 4},
            "L2": {"miss_rate": 0.2, "cache_misses": 1, "total_calls": 5},
            "L1": {"miss_rate": 0.25, "cache_misses": 1, "total_calls": 4},
        }}
    elif case == "version_mismatch":
        summary["scoring_version"] = "wrong-v2"
        summary["scoring_v3"]["scoring_version"] = "wrong-v3"
        summary["scoring_v4"]["scoring_version"] = "wrong-v4"
    elif case == "score_out_of_range":
        summary["by_level"]["L1"]["score"] = 1.2
        summary["by_level"]["L1"]["metrics"]["ToolAcc"]["score"] = -0.1
        summary["agent_score"] = 1.1
    elif case == "l7_record_only_violation":
        l7 = summary["by_level"]["L7"]
        l7["score"] = 0.7
        l7["metrics"]["ContextRetention_det"]["in_score"] = True
        l7["metrics"]["ResultFieldCoverage_det"]["in_score"] = True

    native_overrides = (
        {"L1": False, "L2": False} if case == "native_mode_mismatch" else None
    )
    _write_validation_fixture(results_dir, summary, native_overrides)
    if case == "raw_json_parse_error":
        (results_dir / "L1.json").write_text("[", encoding="utf-8")
    return summary


# These complete, ordered lists and return codes were recorded by executing the
# unchanged HEAD validator against _case_fixture, not reconstructed from rules.
# The optional summary/raw count case is omitted: HEAD does not compare counts.
@pytest.mark.parametrize(
    "case, expected_failures, expected_warnings, expected_rc",
    [
        ("v2_only_valid", [], [], 0),
        ("v2_v3_valid", [], [], 0),
        ("v4_valid", [], [], 0),
        (
            "v4_wrong_level_sets",
            [
                "scoring_v4.headline_levels must be exactly ['L1', 'L2', 'L3', 'L5', 'L6']",
                "scoring_v4.excluded_levels must be exactly ['L4']",
                "headline_denominators must spell out the exact v2, v3, and v4 level sets",
            ],
            [],
            1,
        ),
        (
            "cache_miss_warning",
            [],
            [
                "L1 cache miss rate 25.0% exceeds warning threshold 20% "
                "(1/4 executed tool calls); diagnostic only, score unchanged",
                "L5 cache miss rate 50.0% exceeds warning threshold 20% "
                "(2/4 executed tool calls); diagnostic only, score unchanged",
            ],
            0,
        ),
        (
            "version_mismatch",
            [
                "scoring_version mismatch: expected 'agent_det_v2', got 'wrong-v2'",
                "scoring_v3.scoring_version mismatch: expected 'agent_det_v3', got 'wrong-v3'",
                "scoring_v4.scoring_version mismatch: expected 'agent_det_v4', got 'wrong-v4'",
            ],
            [],
            1,
        ),
        (
            "score_out_of_range",
            [
                "L1.score must be finite and within [0, 1], got 1.2",
                "L1.ToolAcc.score must be finite and within [0, 1], got -0.1",
                "agent_score must be finite and within [0, 1], got 1.1",
                "agent_score must be finite if and only if status is complete",
                "agent_score_status is complete if and only if all six scorable levels have scores",
            ],
            [],
            1,
        ),
        (
            "l7_record_only_violation",
            [
                "L7.ContextRetention_det must be present with in_score false",
                "L7.ResultFieldCoverage_det must be present with in_score false",
                "L7 must be absent from the denominator and have a null level score",
            ],
            [],
            1,
        ),
        (
            "native_mode_mismatch",
            [
                "L1.json native_tool_calling=False does not match summary=True",
                "L2.json native_tool_calling=False does not match summary=True",
                "native_tool_calling disagrees across raw levels: "
                "L1=False, L2=False, L3=True, L4=True, L5=True, L6=True, L7=True",
            ],
            [],
            1,
        ),
        (
            "raw_json_parse_error",
            [
                "L1.json could not be parsed: JSONDecodeError: "
                "Expecting value: line 1 column 2 (char 1)",
            ],
            [],
            2,
        ),
    ],
    ids=[
        "v2_only_valid",
        "v2_v3_valid",
        "v4_valid",
        "v4_wrong_level_sets",
        "cache_miss_warning",
        "version_mismatch",
        "score_out_of_range",
        "l7_record_only_violation",
        "native_mode_mismatch",
        "raw_json_parse_error",
    ],
)
def test_validate_summary_characterization(
    tmp_path, capsys, case, expected_failures, expected_warnings, expected_rc
):
    results_dir = tmp_path
    summary = _case_fixture(case, results_dir)

    failures, warnings = validate_run.validate_summary(summary, results_dir)
    assert [
        message.replace(str(results_dir), "<results_dir>") for message in failures
    ] == expected_failures
    assert [
        message.replace(str(results_dir), "<results_dir>") for message in warnings
    ] == expected_warnings

    rc = validate_run.main(["--results-dir", str(results_dir)])
    capsys.readouterr()  # Capture and discard stdout/stderr; CLI prose may change.
    assert rc == expected_rc
