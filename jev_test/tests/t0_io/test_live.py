"""무엇: T0 실제 loopback·CLI 경계 · 입력: 가짜 HTTP 서버 · 출력: 요청 보존·판정 · 계약 §8-7."""

import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread

import pytest

from jeveval.run.cli import main
from jeveval.run import cmd_t0
from . import fakes


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        assert self.path == "/v1/systemone"
        assert self.headers["Authorization"] == "Bearer secret_auth_canary"
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.calls.append(body)
        response = fakes.response(body)
        if self.server.mode == "flip":
            answer = response["answers"]["choice_two"]
            a, b = answer["probabilities"]
            answer.update(choice=b, probabilities={a:.3, b:.7})
        raw = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.mark.parametrize("family", ["clef", "pplx_v1", "pplx_v1_1"])
@pytest.mark.parametrize("mode, expected", [("same", "PASS"), ("flip", "FAIL")])
def test_cli_all_stages_with_loopback(setup, monkeypatch, capsys, family, mode, expected):
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    except OSError as exc:
        if exc.errno in (errno.EACCES, errno.EPERM):
            pytest.skip("loopback bind blocked")
        raise
    server.mode, server.calls = mode, []
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval":.01}, daemon=True)
    thread.start()
    try:
        ctx = setup(family)
        monkeypatch.chdir(ctx.root)
        monkeypatch.setattr(cmd_t0.t0_inputs, "read_sources", lambda *a: ctx.sources)
        monkeypatch.setattr(cmd_t0.t0_runner, "load", lambda *a, **k: ctx.runtime)
        assert main(["t0", "inputs", "--model", f"{family}.yaml", "--run-id", "r1", "--fixture", "fixture.json"]) == 0
        run_args = ["--run-dir", str(ctx.directory)]
        assert main(["t0", "reference", *run_args, "--checkpoint", "checkpoint"]) == 0
        assert main(["t0", "server", *run_args, "--base-url", f"http://127.0.0.1:{server.server_port}"]) == 0
        assert main(["t0", "tolerance", *run_args, "--rounding", "reference=4"]) == 0
        assert main(["t0", "judge", *run_args, "--rounding", "reference=4,server=4"]) == 0
        assert json.loads(capsys.readouterr().out.splitlines()[-1])["status"] == expected
        assert len(server.calls) == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_cli_requires_checkpoint_and_base_url(capsys):
    for stage_name in ("reference", "server"):
        with pytest.raises(SystemExit) as error:
            main(["t0", stage_name, "--run-dir", "results/example"])
        assert error.value.code == 2


def test_cli_error_never_prints_exception_state(monkeypatch, capsys):
    def fail(**kwargs):
        raise ValueError("PRIVATE_ERROR_CANARY")
    monkeypatch.setattr(cmd_t0, "run_judge", fail)
    assert main(["t0", "judge", "--run-dir", "missing"]) == 1
    assert "PRIVATE_ERROR_CANARY" not in capsys.readouterr().out


def test_cli_pipeline_without_socket(setup, monkeypatch, capsys):
    from jeveval.client.systemone import send_t0
    from .support import fake_post
    ctx = setup("pplx_v1_1")
    monkeypatch.chdir(ctx.root)
    monkeypatch.setattr(cmd_t0.t0_inputs, "read_sources", lambda *a: ctx.sources)
    monkeypatch.setattr(cmd_t0.t0_runner, "load", lambda *a, **k: ctx.runtime)
    post = fake_post()
    def send(*args, **kwargs):
        return send_t0(*args, **dict(kwargs, post=post))
    monkeypatch.setattr(cmd_t0.t0_server, "send_t0", send)
    assert main(["t0", "inputs", "--model", "pplx_v1_1.yaml", "--run-id", "r1", "--fixture", "fixture.json"]) == 0
    args = ["--run-dir", str(ctx.directory)]
    assert main(["t0", "reference", *args, "--checkpoint", "checkpoint"]) == 0
    assert main(["t0", "server", *args, "--base-url", "http://127.0.0.1:1"]) == 0
    assert main(["t0", "tolerance", *args, "--rounding", "reference=4"]) == 0
    assert main(["t0", "judge", *args, "--rounding", "reference=4,server=4"]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["status"] == "PASS"
    assert len(post.calls) == 2
