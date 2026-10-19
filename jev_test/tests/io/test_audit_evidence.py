"""감사 존재/연결/불일치와 보고 문구의 범위를 검증한다."""

from jeveval.io import audit_evidence, run_files
from tests.run.history_support import finished


def test_missing_linked_and_stale_audit(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch, "kosgd", "full")
    assert audit_evidence.summary(tmp_path, h.directory) is None
    fp = run_files.read_json(h.directory / "fingerprint.json")
    audit = dict(schema="audit_v4/1", set="kosgd", profile="kosgd", retrospective=True,
                 inputs=dict(files=fp["files"]), code=dict(audit_sha256="a"*64),
                 models=dict(synthetic=dict(variants=dict(full=dict(measurement_config=False)))),
                 per_variant=dict(full={r: dict(status="PASS") for r in audit_evidence.RULES}),
                 historical_calls=dict(status="INCOMPLETE"))
    target = tmp_path / "audits/audit_v4/out/kosgd.json"
    target.parent.mkdir(parents=True)
    run_files.write_json(target, audit)
    text = audit_evidence.summary(tmp_path, h.directory)
    assert "사후 감사" in text and "script=aaaaaaaaaaaa" in text and "뒷받침" in text
    audit["inputs"]["files"][fp["inputs"]["task_path"]] = "b"*64
    run_files.write_json(target, audit)
    assert "연결 불가" in audit_evidence.summary(tmp_path, h.directory)


def test_only_audit_line_changes_and_existing_report_is_preserved(tmp_path, monkeypatch):
    from jeveval.run import cmd_report
    import pytest
    h = finished(tmp_path, monkeypatch, "kosgd", "full")
    cmd_report.run(root=tmp_path, run_id="r1", models=["synthetic"], out="before.md")
    before = (tmp_path / "before.md").read_bytes()
    fp = run_files.read_json(h.directory / "fingerprint.json")
    audit = dict(schema="audit_v4/1", set="kosgd", profile="kosgd", retrospective=True,
                 inputs=dict(files=fp["files"]), code=dict(audit_sha256="a"*64),
                 models=dict(synthetic=dict(variants=dict(full=dict(measurement_config=False)))),
                 per_variant=dict(full={r: dict(status="PASS") for r in audit_evidence.RULES}),
                 historical_calls=dict(status="PASS"))
    path = tmp_path / "audits/audit_v4/out/kosgd.json"
    path.parent.mkdir(parents=True)
    run_files.write_json(path, audit)
    cmd_report.run(root=tmp_path, run_id="r1", models=["synthetic"], out="after.md")
    after = (tmp_path / "after.md").read_bytes()
    strip = lambda b: [line for line in b.decode().splitlines() if not line.startswith("미완·한계:")]
    assert strip(before) == strip(after) and before != after
    assert (tmp_path / "before.md").read_bytes() == before
    with pytest.raises(ValueError):
        cmd_report.run(root=tmp_path, run_id="r1", models=["synthetic"], out="before.md")
