"""명령 모듈의 검증 및 쓰기 경계."""

import pytest

from jeveval.io import run_files
from jeveval.run import cmd_run
from tests.run.cli_support import Harness
from tests.run.file_support import output_files, put_yaml


def test_threshold_never_opens_other_stage_and_incomplete_dev_rejected(h, monkeypatch):
    from pathlib import Path
    h.run("dev")
    original = Path.open
    forbidden = [h.directory / "test", h.directory / "extra"]
    def guarded(path, *args, **kwargs):
        assert not any(p == path or p in path.parents for p in forbidden)
        return original(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", guarded)
        assert h.command("threshold") == 0
    (h.directory / "dev/final.jsonl").write_text("")
    before = output_files(h.directory)
    assert h.command("threshold") == h.command("certify") == 1
    assert output_files(h.directory) == before



def test_sealed_threshold_rejected_without_writes(h):
    from jeveval.run import cmd_threshold
    h.run("dev")
    assert h.command("threshold") == 0
    h.run("test")
    before = output_files(h.directory)
    with pytest.raises(ValueError, match="^threshold is sealed$"):
        cmd_threshold.run(root=h.root, run_dir=h.directory)
    assert output_files(h.directory) == before


def test_recompute_records_actual_dev_hash_and_bytes(h):
    from hashlib import sha256
    from jeveval.run import cmd_threshold, context
    h.run("dev")
    ctx = context.restore(h.root, h.directory)
    before = output_files(h.directory)
    result = cmd_threshold.recompute(ctx, context.stage(ctx, "dev"))
    payload = (h.directory / "dev/final.jsonl").read_bytes()
    assert result.dev_input["sha256"] == sha256(payload).hexdigest()
    assert result.dev_input["nbytes"] == len(payload)
    assert result.dev_input["path"] == "dev/final.jsonl"
    assert output_files(h.directory) == before
