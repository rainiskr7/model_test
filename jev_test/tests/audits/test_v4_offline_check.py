"""수용 wrapper가 script 종료에도 보존 확인을 수행한다."""

import sys
from audits.audit_v4.offline_check import main


def test_wrapper_preserves_exit_and_blocks_network(tmp_path, monkeypatch, capsys):
    p = tmp_path / "synthetic.py"
    p.write_text('import socket\ntry:\n socket.create_connection(("127.0.0.1", 1))\nexcept RuntimeError:\n raise SystemExit(2)\n')
    monkeypatch.setattr(sys, "argv", ["check", "--root", str(tmp_path), "--", "synthetic.py"])
    assert main() == 2
    assert '"real_model_calls":0' in capsys.readouterr().out
