"""무엇: T0 기록 파일 읽기 · 입력: 로컬 모델 YAML · 출력: 통과/미존재 거부 · 계약 T-i."""

from pathlib import Path

import pytest
import yaml

from jeveval.io.t0 import verify_for_run
from tests.run.t0_support import passed_record


def test_nonpassed_does_not_open_record_then_passed_requires_it(tmp_path):
    cfg = yaml.safe_load((Path(__file__).parents[2] / "configs/models/clef.yaml").read_text())
    path = tmp_path / "clef.yaml"
    cfg["t0"]["record"] = {"path":"missing.json", "sha256":"a" * 64}
    path.write_text(yaml.safe_dump(cfg))
    assert verify_for_run(tmp_path, path) is None
    record = passed_record(tmp_path, cfg)
    path.write_text(yaml.safe_dump(cfg))
    assert verify_for_run(tmp_path, path) is None
    record.unlink()
    with pytest.raises(ValueError, match="T0 record unavailable"):
        verify_for_run(tmp_path, path)
