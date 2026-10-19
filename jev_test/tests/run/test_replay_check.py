"""무엇: replay 순수 검사 짝 시험 · 입력: 합성 fingerprint·기록 · 출력: 호환/거부 · 계약 §5-5c."""

from copy import deepcopy

import pytest

from jeveval.run.replay_check import check_reason, compatible, complete_attempts


def fingerprint():
    return dict(schema="fingerprint/1", model="m", set="s", variant="v", files={"cfg": "a"},
                tokenizer={"t": "a"}, encoder={"rule": "e"}, external={"e": "a"}, dataset_verified=True,
                inputs=dict(run_id="old", model_cfg_path="m", task_path="t", set="s", variant="v"),
                run_id="old", code_sha256="a", env={"python": "old"}, started_at="old")


def test_only_allowed_fingerprint_differences():
    source, current = fingerprint(), fingerprint()
    current.update(run_id="new", code_sha256="b", env={"python": "new"}, started_at="new")
    current["inputs"]["run_id"] = "new"
    before = deepcopy((source, current))
    assert compatible(source, current) == [] and (source, current) == before


@pytest.mark.parametrize("field", ["schema", "model", "set", "variant", "files", "tokenizer", "encoder",
                                    "external", "dataset_verified", "inputs", "unknown", "identity"])
def test_incompatible_fingerprint(field):
    source, current = fingerprint(), fingerprint()
    if field == "identity":
        source["inputs"]["run_id"] = "different"
    elif field == "inputs":
        source["inputs"]["task_path"] = "different"
    else:
        source[field] = "different"
    assert compatible(source, current)


def test_closed_fingerprint_and_attempt_completeness():
    assert compatible(None, fingerprint())
    assert compatible({}, fingerprint())
    assert complete_attempts([], [])
    assert complete_attempts([object()], ["truncated_last_line"])
    assert complete_attempts([object()], ["missing_final_newline"])
    assert complete_attempts([object()], []) == []


@pytest.mark.parametrize("reason,valid", [(None, True), ("", True), ("가" * 200, True),
    ("a" * 201, False), ("a\nb", False), ("a\rb", False), ("a\u2028b", False), (1, False)])
def test_reason(reason, valid):
    assert (not check_reason(reason)) == valid
