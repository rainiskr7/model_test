"""입력: tmp_path의 합성 sidecar·세션. 출력: 무결성·코호트·사본 접힘·반복 검증."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from shared.multimodal.publish.schema import make_protocol, sidecar_path
from shared.stats.selection import (
    SelectionError, candidates, check_comparison, choose_cohort, load_cohort, read_run, read_sidecars,
)
from shared.stats.tests.test_stats_item_scores_units import dtc_case


def session_case(base, model="a", session="20260101", stamp="2026-01-01T00:00:00Z", protocol=None):
    rows, manifest = dtc_case()
    source = base / "results" / model / session / "vision/multimodal/k_dtcbench"
    source.mkdir(parents=True)
    (source / "results.json").write_text(json.dumps(rows))
    (source / "summary.json").write_text(json.dumps({"run_config": {"dataset": {
        "huggingface_id": manifest["dataset"], "revision": manifest["revision"]}}}))
    directory = base / "manifests"
    directory.mkdir(exist_ok=True)
    (directory / f'k_dtcbench_{manifest["revision"]}.json').write_text(json.dumps(manifest))
    value = {"schema_version": 1, "status": "NATIVE", "publishable": True,
             "aggregation_allowed": False, "benchmark_id": "K-DTCBench", "variant": "full",
             "model": model, "session": session, "completed_at_utc": stamp,
             "protocol": make_protocol(protocol or {"temperature": 0}, {}, []),
             "counts": {"attempted": 3, "measured": 3, "errored": 0,
                        "unresolved": 0, "correct_measured": 2},
             "metrics": {"axes": [{"name": "overall", "unit": "fraction",
                                   "numerator": 2, "denominator": 3, "value": 2 / 3}]},
             "source": {"unit": source.relative_to(base).as_posix(), "artifacts": [
                 {"path": (source / name).relative_to(base).as_posix(),
                  "sha256": "sha256:" + hashlib.sha256((source / name).read_bytes()).hexdigest()}
                 for name in ("results.json", "summary.json")]}}
    sidecar_path(source).parent.mkdir()
    sidecar_path(source).write_text(json.dumps(value))
    return source, directory


def test_validated_cohort_reuses_selection_folds_bad_and_keeps_all_repeats(tmp_path):
    source, directory = session_case(tmp_path)
    session_case(tmp_path, session="20260101.bad")
    session_case(tmp_path, session="20260102", stamp="2026-01-02T00:00:00Z")
    values = read_sidecars(tmp_path, "a", "k_dtcbench")
    before = deepcopy(values)
    selected = choose_cohort(values)
    assert values == before
    assert len(selected["_selection"]["cohort_runs"]) == 2
    assert len(selected["_selection"]["folded_duplicates"]) == 1
    result = load_cohort(tmp_path, "results/a", "k_dtcbench", manifest_directory=directory)
    assert result["repetitions"] == 2
    assert len(result["items"]) == 3
    assert result["runs"][0]["source"] == source.relative_to(tmp_path).as_posix()
    assert len(result["runs"][0]["sidecar_sha256"]) == 64
    assert len(result["runs"][0]["manifest_sha256"]) == 64
    check_comparison(result, result)


@pytest.mark.parametrize("kind", ["tie", "undated", "cohorts"])
def test_ambiguity_lists_candidates_and_explicit_fingerprint_selects(tmp_path, kind):
    session_case(tmp_path, stamp=None if kind == "undated" else "2026-01-01T00:00:00Z")
    session_case(tmp_path, session="second",
                 stamp=None if kind == "undated" else "2026-01-01T00:00:00Z",
                 protocol={"temperature": 1} if kind == "cohorts" else None)
    values = read_sidecars(tmp_path, "a", "k_dtcbench")
    with pytest.raises(SelectionError) as error:
        choose_cohort(values)
    assert len(error.value.candidates) == 2
    assert set(error.value.candidates[0]) == {"source", "session", "model", "cohort", "publishable"}
    if kind == "cohorts":
        assert choose_cohort(values, values[0]["protocol"]["fingerprint"])["_selection"]["cohort_runs"]
    with pytest.raises(SelectionError):
        choose_cohort(values, "unknown")


@pytest.mark.parametrize("kind", ["missing", "missing_raw", "stale", "schema", "source", "benchmark"])
def test_sidecar_validation_fails_closed_without_raw_payload(tmp_path, kind):
    source, _ = session_case(tmp_path)
    path = sidecar_path(source)
    value = json.loads(path.read_text())
    if kind == "missing":
        path.unlink()
    elif kind == "missing_raw":
        (source / "results.json").unlink()
        session_case(tmp_path, session="other")  # Do not silently lose an incomplete repeat.
    elif kind == "stale":
        (source / "results.json").write_text("SECRET_SENTINEL")
    else:
        if kind == "schema":
            value["schema_version"] = "SECRET_SENTINEL"
        elif kind == "source":
            value["source"]["unit"] = "results/other"
        else:
            value["benchmark_id"] = "K-MMBench"
        path.write_text(json.dumps(value))
    with pytest.raises(SelectionError) as error:
        read_sidecars(tmp_path, "a", "k_dtcbench")
    assert "SECRET_SENTINEL" not in str(error.value) + json.dumps(error.value.candidates)


def test_read_bytes_must_be_bound_to_previously_validated_artifacts(tmp_path):
    source, directory = session_case(tmp_path)
    run = read_sidecars(tmp_path, "a", "k_dtcbench")[0]
    (source / "results.json").write_text((source / "results.json").read_text() + " ")
    with pytest.raises(SelectionError, match="not bound"):
        read_run(tmp_path, run, "k_dtcbench", directory)


def test_scoring_failure_and_no_publishable_cohort_are_rejected(tmp_path):
    source, directory = session_case(tmp_path)
    path = sidecar_path(source)
    value = json.loads(path.read_text())
    rows = json.loads((source / "results.json").read_text())[:-1]
    (source / "results.json").write_text(json.dumps(rows))
    value["source"]["artifacts"][0]["sha256"] = "sha256:" + hashlib.sha256(
        (source / "results.json").read_bytes()).hexdigest()
    path.write_text(json.dumps(value))
    with pytest.raises(SelectionError, match="invalid cohort run"):
        load_cohort(tmp_path, "a", "k_dtcbench", manifest_directory=directory)
    value["publishable"], value["status"] = False, "REJECTED"
    path.write_text(json.dumps(value))
    with pytest.raises(SelectionError, match="unavailable"):
        load_cohort(tmp_path, "a", "k_dtcbench", manifest_directory=directory)
    assert candidates([value])[0]["publishable"] is False


def test_model_path_containment_and_absent_sources(tmp_path):
    (tmp_path / "results/a").mkdir(parents=True)
    with pytest.raises(SelectionError, match="unavailable"):
        choose_cohort(read_sidecars(tmp_path, "a", "k_dtcbench"))
    with pytest.raises(SelectionError, match="directory"):
        read_sidecars(tmp_path, tmp_path, "k_dtcbench")
    (tmp_path / "results/outside").symlink_to(tmp_path)
    with pytest.raises(SelectionError, match="directory"):
        read_sidecars(tmp_path, "outside", "k_dtcbench")


def test_undated_run_stays_in_repetitions_with_dated_representative(tmp_path):
    _, directory = session_case(tmp_path, stamp=None)
    session_case(tmp_path, session="dated", stamp="2026-01-02T00:00:00Z")
    result = load_cohort(tmp_path, "a", "k_dtcbench", manifest_directory=directory)
    assert result["repetitions"] == 2
    assert {v["session"] for v in result["runs"]} == {"20260101", "dated"}
