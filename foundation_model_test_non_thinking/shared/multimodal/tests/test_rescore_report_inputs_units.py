"""입력: tmp_path 코호트·manifest·수집 범위. 출력: 바인딩·평균·별칭·범위 검증."""

import hashlib
import json

import pytest

from shared.multimodal.publish.report import collect
from shared.multimodal.rescore.report_inputs import build_inputs, folder_matches, scope_sidecars
from shared.multimodal.tests.test_publish_select_report import sidecar
from shared.multimodal.tests.test_rescore_kmmbench_circular_units import circular_case
from shared.stats.selection import read_collected_run


def circular_session(base, model="a", session="r1", passed=True, stamp="2026-01-01T00:00:00Z"):
    rows, manifest = circular_case((2, 3))
    rows[0]["correct"] = passed
    source = base / "results" / model / session / "vision/multimodal/k_mmbench"
    source.mkdir(parents=True)
    (source / "results.json").write_text(json.dumps(rows))
    (source / "summary.json").write_text(json.dumps({"run_config": {"dataset": {
        "huggingface_id": manifest["dataset"], "revision": manifest["revision"]}}}))
    directory = base / "manifests"
    directory.mkdir(exist_ok=True)
    (directory / f'k_mmbench_{manifest["revision"]}.json').write_text(json.dumps(manifest))
    unit = source.relative_to(base).as_posix()
    correct = sum(r["correct"] for r in rows)
    value = sidecar(session, stamp, model=model, source=unit, benchmark="K-MMBench",
                    axes=[{"name": "overall", "unit": "fraction", "numerator": correct,
                           "denominator": len(rows), "value": correct / len(rows)}],
                    artifacts=[{"path": unit + "/" + name, "sha256": "sha256:" + hashlib.sha256(
                        (source / name).read_bytes()).hexdigest()} for name in ("results.json", "summary.json")])
    value["counts"].update(attempted=len(rows), measured=len(rows), correct_measured=correct)
    (source / "_derived").mkdir()
    (source / "_derived/publish.json").write_text(json.dumps(value))
    return source, directory


def configure(base, directory, monkeypatch, pairs=()):
    path = base / "pairs.yaml"
    path.write_text(json.dumps(list(pairs)))
    monkeypatch.setattr("shared.multimodal.rescore.report_inputs.read_collected_run",
                        lambda base, run, bench: read_collected_run(base, run, bench, directory))
    return path


def test_same_runs_mean_and_alias_copies_fold_without_global_rescan(tmp_path, monkeypatch):
    source, directory = circular_session(tmp_path)
    circular_session(tmp_path, model="alias", session="r1.bad")
    circular_session(tmp_path, model="alias", session="r2", passed=False, stamp="2026-01-02T00:00:00Z")
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/model_identity.json").write_text(json.dumps({"a": "a", "alias": "a"}))
    pairs_path = configure(tmp_path, directory, monkeypatch)
    values, missing = collect(tmp_path)
    assert not missing
    result = build_inputs(tmp_path, values, pairs_path=pairs_path)
    value, = result["official"]
    assert value["repetitions"] == 2 and len(value["folded_duplicates"]) == 1
    assert value["old_mean"] == 0.9 and value["new_mean"] == 0.75
    assert value["representative"].endswith("alias/r2/vision/multimodal/k_mmbench")
    assert value["runs"][0]["source"] == source.relative_to(tmp_path).as_posix()
    # Only supplied records count, even though more valid runs exist on disk.
    scoped, _ = collect(tmp_path, "r1")
    limited = build_inputs(tmp_path, scoped, pairs_path=pairs_path)["official"][0]
    assert limited["repetitions"] == 1 and limited["new_mean"] == 1
    strict = build_inputs(tmp_path, scoped, values, pairs_path=pairs_path)["official"][0]
    assert strict["repetitions"] == 2 and strict["new_mean"] == 0.75


@pytest.mark.parametrize("problem", ["missing_sidecar", "changed_sidecar", "revision", "artifact", "missing_raw"])
def test_binding_rejects_bad_cohort_without_numbers(tmp_path, monkeypatch, problem):
    source, directory = circular_session(tmp_path)
    path = configure(tmp_path, directory, monkeypatch)
    values, _ = collect(tmp_path)
    sidepath = source / "_derived/publish.json"
    if problem == "missing_sidecar":
        sidepath.unlink()
    elif problem == "changed_sidecar":
        value = json.loads(sidepath.read_text())
        value["session"] = "changed"
        sidepath.write_text(json.dumps(value))
    elif problem == "revision":
        summary = json.loads((source / "summary.json").read_text())
        summary["run_config"]["dataset"]["revision"] = "unsupported"
        (source / "summary.json").write_text(json.dumps(summary))
        value = json.loads(sidepath.read_text())
        value["source"]["artifacts"][1]["sha256"] = "sha256:" + hashlib.sha256(
            (source / "summary.json").read_bytes()).hexdigest()
        sidepath.write_text(json.dumps(value))
        values, _ = collect(tmp_path)
    elif problem == "artifact":
        (source / "results.json").write_text((source / "results.json").read_text() + " ")
    else:
        (source / "results.json").unlink()
    result = build_inputs(tmp_path, values, pairs_path=path)
    assert not result["official"] and len(result["rejected"]) == 1


def test_missing_or_rejected_collected_sidecar_does_not_trigger_rescore(tmp_path, monkeypatch):
    source, directory = circular_session(tmp_path)
    path = configure(tmp_path, directory, monkeypatch)
    sidepath = source / "_derived/publish.json"
    value = json.loads(sidepath.read_text())
    value.update(publishable=False, status="REJECTED")
    sidepath.write_text(json.dumps(value))
    values, _ = collect(tmp_path)
    monkeypatch.setattr("shared.multimodal.rescore.report_inputs.read_collected_run",
                        lambda *args: pytest.fail("rejected source must not be scored"))
    assert not build_inputs(tmp_path, values, pairs_path=path)["official"]
    sidepath.unlink()
    values, missing = collect(tmp_path)
    assert missing and not build_inputs(tmp_path, values, pairs_path=path)["official"]


def test_pairs_use_supplied_scope_and_only_selection_errors_are_soft(tmp_path, monkeypatch):
    _, directory = circular_session(tmp_path)
    circular_session(tmp_path, model="b", passed=False)
    pairs = [{"a": "a", "b": "b", "bench": "k_mmbench"}]
    path = configure(tmp_path, directory, monkeypatch, pairs)
    values, _ = collect(tmp_path)
    result = build_inputs(tmp_path, values, pairs_path=path)
    assert result["pairs"][0]["result"]["difference"] == 0.5
    result = build_inputs(tmp_path, [values[0]], pairs_path=path)
    assert "error" in result["pairs"][0]  # Must not rediscover b from disk.
    def fail(*args):
        raise RuntimeError("implementation failure")
    monkeypatch.setattr("shared.multimodal.rescore.report_inputs.read_collected_run", fail)
    with pytest.raises(RuntimeError, match="implementation"):
        build_inputs(tmp_path, values, pairs_path=path)


def test_scope_and_folder_rules_do_not_include_other_cohorts(tmp_path):
    one = sidecar("r1", None, benchmark="K-MMBench", item_digest="one")
    other = sidecar("r2", None, benchmark="K-MMBench", item_digest="two")
    assert scope_sidecars([one], [one, other]) == [one]
    assert scope_sidecars([], [one, other]) == []
    run = {"source": {"unit": "results/a/r1/vision/multimodal/k_mmbench"}}
    assert folder_matches(tmp_path, run, "a", "k_mmbench")
    run["source"]["unit"] = str(tmp_path / run["source"]["unit"])
    assert folder_matches(tmp_path, run, "a", "k_mmbench")
    assert not folder_matches(tmp_path, run, "b", "k_mmbench")
    run["source"]["unit"] = "/outside/results/a/r1/k_mmbench"
    assert not folder_matches(tmp_path, run, "a", "k_mmbench")


def test_ambiguous_representatives_have_no_numeric_official_row(tmp_path, monkeypatch):
    _, directory = circular_session(tmp_path)
    circular_session(tmp_path, session="r2", passed=False)  # Same completion timestamp.
    path = configure(tmp_path, directory, monkeypatch)
    values, _ = collect(tmp_path)
    result = build_inputs(tmp_path, values, pairs_path=path)
    assert not result["official"]
    assert result["rejected"][0]["reason"] == "대표 선택 모호"


def test_empty_scope_does_not_read_existing_raw_sources(tmp_path, monkeypatch):
    _, directory = circular_session(tmp_path)
    path = configure(tmp_path, directory, monkeypatch)
    monkeypatch.setattr("shared.multimodal.rescore.report_inputs.read_collected_run",
                        lambda *args: pytest.fail("empty scope must not read source"))
    result = build_inputs(tmp_path, [], pairs_path=path)
    assert result["official"] == result["selected"] == result["pairs"] == []
