"""Bounded, direct HTTP preflight; no redirects, proxies or retries."""
import json
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .artifacts import require


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("unexpected serving redirect")


def request(ctx, path, payload=None):
    headers = {"Authorization": "Bearer " + ctx.env["OPENAI_API_KEY"]}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    req = Request(ctx.endpoint + path, data=data, headers=headers)
    with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=10 if data is None else 60) as response:
        require(response.status == 200, "preflight HTTP status")
        return json.load(response)


def models(ctx):
    value = request(ctx, "/models")
    require(ctx.model in [entry["id"] for entry in value["data"]], "model absent from /models")


def chat(ctx):
    value = request(ctx, "/chat/completions", {
        "model": ctx.model, "messages": [{"role": "user", "content": "1"}], "max_tokens": 1})
    message = value["choices"][0]["message"]
    require(message["role"] == "assistant" and isinstance(message["content"], str)
            and bool(message["content"].strip()), "invalid preflight chat response")
