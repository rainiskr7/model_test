"""Stdlib HTTP fixture. Only binds loopback; never forwards a request."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, value, status=200):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def record(self, kind):
        server = self.server
        server.calls.append((server.track, kind))
        if self.headers.get("Authorization") != "Bearer " + server.key:
            raise AssertionError("fixture authorization mismatch")
        return server.fault == (server.track, kind)

    def do_GET(self):
        broken = self.record("models")
        if self.path != "/v1/models":
            return self.send_json({"error": "unknown path"}, 404)
        name = "wrong-model" if broken else self.server.model
        self.send_json({"object": "list", "data": [
            {"id": name, "object": "model", "created": 0, "owned_by": "fixture"}]})

    def do_POST(self):
        broken = self.record("chat")
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if payload.get("model") != self.server.model:
            return self.send_json({"error": "unexpected model"}, 400)
        choice = {"index": 0, "finish_reason": "stop",
                  "message": {"role": "assistant", "content": "A"}}
        if self.path == "/v1/completions":
            choice = {"index": 0, "finish_reason": "stop", "text": "A"}
        elif self.path != "/v1/chat/completions":
            return self.send_json({"error": "unknown path"}, 404)
        self.send_json({"id": "smoke-fixture", "object": "chat.completion", "created": 0,
                        "model": self.server.model, "choices": [] if broken else [choice],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})


def start(model, key):
    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.model, server.key = model, key
    server.track, server.fault, server.calls = "", None, []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
