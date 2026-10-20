"""명령 모듈의 검증 및 쓰기 경계."""

import pytest

from jeveval.io import run_files
from jeveval.run import cmd_run
from tests.run.cli_support import Harness
from tests.run.file_support import output_files, put_yaml


@pytest.mark.parametrize("failure", ["auth", "missing", "measurer", "items"])
@pytest.mark.parametrize("stage", ["dev", "test"])
def test_run_failure_before_any_write(h, monkeypatch, failure, stage):
    if stage == "test":
        h.run("dev")
        assert h.command("threshold") == 0
    sent = len(h.sent)
    if failure == "auth":
        monkeypatch.delenv("JEV_TEST_KEY")
    elif failure == "missing":
        path = h.root / h.args["model"]
        import yaml
        cfg = yaml.safe_load(path.read_text())
        cfg["served_name"] = None
        put_yaml(path, cfg)
    elif failure == "measurer":
        monkeypatch.setattr(cmd_run, "measurer_for", lambda cfg: (_ for _ in ()).throw(ValueError("secret")))
    else:
        monkeypatch.setattr(cmd_run.stage_inputs, "load_items", lambda **kw: (_ for _ in ()).throw(ValueError("secret")))
    before = output_files(h.root)
    with pytest.raises(ValueError):
        if failure == "measurer":
            cmd_run.run(**h.args, stage=stage, post=h.post)
        else:
            h.run(stage)
    assert output_files(h.root) == before and len(h.sent) == sent



def test_check_config_missing_fields_never_sends_or_writes(h, monkeypatch):
    from jeveval.io.config import read_yaml
    path = h.root / h.args["model"]
    config = read_yaml(path)
    config["served_name"] = None
    put_yaml(path, config)
    before = output_files(h.root)
    result = h.run("dev", check_config=True)
    assert result["ok"] is False and "served_name" in result["missing_for_run"]
    assert h.sent == [] and output_files(h.root) == before


@pytest.mark.parametrize("set_name", ["klue_mrc_answerable", "kosgd", "fc_call_decision"])
def test_extra_stage_only_functionchat(tmp_path, set_name):
    h = Harness(tmp_path, set_name, "full" if set_name == "kosgd" else "default")
    before = output_files(h.root)
    if set_name == "fc_call_decision":
        assert h.run("extra", check_config=True)["ok"] is True
    else:
        with pytest.raises(ValueError, match="^extra only supported for FunctionChat$"):
            h.run("extra", check_config=True)
    assert output_files(h.root) == before and h.sent == []


@pytest.mark.parametrize("secret", [None, "", "bad\nkey", "bad\x7fkey"])
def test_authentication_rejected_before_writes(h, monkeypatch, secret):
    if secret is None:
        monkeypatch.delenv("JEV_TEST_KEY")
    else:
        monkeypatch.setenv("JEV_TEST_KEY", secret)
    before = output_files(h.root)
    with pytest.raises(ValueError, match="^authentication unavailable$"):
        h.run("dev")
    assert output_files(h.root) == before and h.sent == []


def test_separate_actions_only_uses_derived_writer_without_auth(tmp_path, monkeypatch):
    h = Harness(tmp_path, "kosgd", "full")
    monkeypatch.setenv("JEV_TEST_KEY", "key")
    h.run("dev")
    sent, source = len(h.sent), output_files(h.directory)
    h.variant = "actions_only"
    monkeypatch.delenv("JEV_TEST_KEY")
    calls, original = [], cmd_run.derived_stage.write_derived_stage
    resume, gate = cmd_run.derived_resume.resume_derived, cmd_run.gate.prepare_stage
    def checked(*args, **kwargs):
        count = resume(*args, **kwargs)
        calls.append(("resume", kwargs.get("allow_tail", False), count))
        return count
    def prepared(**kwargs):
        result = gate(**kwargs)
        calls.append(("gate",))
        return result
    def write(directory, stage, finals, provenance, existing):
        calls.append(("write", directory, stage, provenance, existing))
        return original(directory, stage, finals, provenance, existing)
    monkeypatch.setattr(cmd_run.derived_resume, "resume_derived", checked)
    monkeypatch.setattr(cmd_run.gate, "prepare_stage", prepared)
    monkeypatch.setattr(cmd_run.derived_stage, "write_derived_stage", write)
    result = h.run("dev")
    assert result["derived"] is True and len(h.sent) == sent
    provenance = (h.directory.parent / "full").relative_to(h.root).as_posix()
    assert calls == [("resume", True, 0), ("gate",), ("resume", False, 0),
                     ("write", h.directory, "dev", provenance, 0)]
    assert run_files.read_json(h.directory / "dev/derived.json") == {"derived_from": provenance}
    assert output_files(h.directory.parent / "full") == source
    calls.clear()
    assert h.run("dev")["derived"] is True
    assert calls == [("resume", True, 1), ("gate",), ("resume", False, 1),
                     ("write", h.directory, "dev", provenance, 1)]
    assert len(h.sent) == sent


def test_offline_without_auth_uses_dummy_url_and_refuses_post(h, monkeypatch):
    monkeypatch.delenv("JEV_TEST_KEY")
    result = h.run("dev", offline=True)
    assert result["n_sent"] == 0 and result["n_deferred"] == 1 and not h.sent
    assert "replay.invalid" not in (h.directory / "fingerprint.json").read_text()
    with pytest.raises(RuntimeError, match="offline run must not send"):
        cmd_run._refuse()


def test_offline_conflict_before_any_write(h):
    before = output_files(h.root)
    with pytest.raises(ValueError, match="mutually exclusive"):
        h.run("dev", offline=True, base_url="http://localhost:1")
    assert output_files(h.root) == before and not h.sent


def test_offline_keeps_t0_and_missing_config_checks(h, monkeypatch):
    calls = []
    def reject(root, path):
        calls.append(path)
        raise ValueError("T0 rejected")
    monkeypatch.setattr(cmd_run.t0, "verify_for_run", reject)
    before = output_files(h.root)
    with pytest.raises(ValueError, match="T0 rejected"):
        h.run("dev", offline=True)
    assert calls and output_files(h.root) == before
    from jeveval.io.config import read_yaml
    path = h.root / h.args["model"]
    cfg = read_yaml(path)
    cfg["tokenizer"]["files_sha256"] = {}
    put_yaml(path, cfg)
    before = output_files(h.root)
    with pytest.raises(ValueError, match="incomplete run configuration"):
        h.run("dev", offline=True)
    assert output_files(h.root) == before
