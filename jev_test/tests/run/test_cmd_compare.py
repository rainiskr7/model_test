"""무엇: compare CLI 거부/모집단 · 입력: 합성 완료 폴더 · 출력: 비교/무변경 · 계약 ⑥b-2 R2·R3·R7."""

from copy import deepcopy

import pytest

from jeveval.io import run_files, run_inputs
from jeveval.run import cli, cmd_compare
from jeveval.run.layout import compare_dir
from tests.run.cli_support import output_files
from tests.run.compare_support import pair


def compare(h, other):
    return cli.main(["compare", "--run-dirs", str(h.directory), str(other.directory), "--compare-id", "c1"])


def result(h):
    return run_files.read_json(compare_dir(h.root / "results", "c1", h.set, h.variant) / "compare.json")


def test_compare_common_ok_excludes_failure_but_coverage_keeps_it(tmp_path, monkeypatch):
    h, other = pair(tmp_path, monkeypatch, fail=True)
    assert compare(h, other) == 0
    value = result(h)
    assert value["common_cohort"]["n"] == 1
    for pop in value["common_cohort"]["per_model"].values():
        assert pop["certified"] is False and pop["counts"]["n_sampled"] == 1
    coverage = value["bootstrap"]["coverage"]["0.02"]
    assert coverage["n_groups"] == 2 and coverage["reps"] == 2000
    assert coverage["pairs"][0]["estimate"] == -.5
    assert value["t0_status"] == {"second": "passed", "synthetic": "not_run"}
    assert value["t0_not_passed"] == ["synthetic"]
    before = output_files(h.root / "results/_compare")
    assert compare(other, h) == 0
    assert output_files(h.root / "results/_compare") == before


def test_functionchat_two_f1_cohorts_keep_group_clusters(tmp_path, monkeypatch):
    h, other = pair(tmp_path, monkeypatch, "fc_call_decision")
    assert compare(h, other) == 0
    f1 = result(h)["bootstrap"]["f1"]
    assert "tool" not in f1["test"] and "tool" not in f1["all_rows"]
    assert all(cell["n_groups"] == 1 for cell in f1["test"].values())
    assert all(cell["n_groups"] == 2 for cell in f1["all_rows"].values())
    assert f1["test"] and f1["all_rows"]


@pytest.mark.parametrize("defect", ["duplicate", "fingerprint", "dev", "test", "threshold", "seal", "no_seal"])
def test_compare_rejects_before_writing(tmp_path, monkeypatch, defect):
    h, other = pair(tmp_path, monkeypatch)
    if defect in ("dev", "test"):
        (other.directory / defect / "final.jsonl").write_text("")
    elif defect == "no_seal":
        (other.directory / "test/seal.json").unlink()
    elif defect in ("threshold", "fingerprint", "seal"):
        name = "test/seal" if defect == "seal" else defect
        path = other.directory / f"{name}.json"
        value = run_files.read_json(path)
        value["threshold_sha256" if defect == "seal" else "model"] = "changed"
        run_files.write_json(path, value)
    before = output_files(tmp_path)
    assert compare(h, h if defect == "duplicate" else other) == 1
    assert output_files(tmp_path) == before


@pytest.mark.parametrize("field", ["split", "task", "set", "variant", "ids"])
def test_compare_c4_and_identity_rejection_after_preflight(tmp_path, monkeypatch, field):
    h, other = pair(tmp_path, monkeypatch)
    # 실제 선행을 통과한 객체의 비교 필드만 변경해 C4 거부 경계 자체를 검증한다.
    restored = {str(x.directory): run_inputs.completed(tmp_path, x.directory) for x in (h, other)}
    ctx, stages, threshold = deepcopy(restored[str(other.directory)])
    if field in ("set", "variant"):
        from dataclasses import replace
        ctx.task = replace(ctx.task, **{field: "different"})
    elif field == "ids":
        stages["test"].finals = []
    else:
        key = f"configs/splits/{ctx.task.set}.json" if field == "split" else ctx.fingerprint["inputs"]["task_path"]
        ctx.fingerprint["files"][key] = "changed"
    restored[str(other.directory)] = ctx, stages, threshold
    monkeypatch.setattr(run_inputs, "completed", lambda root, directory: restored[str(directory)])
    before = output_files(tmp_path)
    assert compare(h, other) == 1
    assert output_files(tmp_path) == before


def test_compare_functionchat_requires_extra(tmp_path, monkeypatch):
    h, other = pair(tmp_path, monkeypatch, "fc_call_decision")
    (other.directory / "extra/final.jsonl").unlink()
    assert compare(h, other) == 1


def test_compare_one_model_and_external_destination_rejected(tmp_path, monkeypatch):
    h, other = pair(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        cmd_compare.run(root=tmp_path, run_dirs=[h.directory], compare_id="c")
    with pytest.raises(ValueError):
        cmd_compare.run(root=tmp_path, run_dirs=[h.directory, other.directory], compare_id="c", results="../outside")
