"""Serving success requires the actual runner artifacts, not just its rc."""
import json


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def result_dir(ctx, suffix):
    model = ctx.model.replace("/", "_").replace("-", "_").replace(":", "_")
    return ctx.base / "results" / model / ctx.stamp / suffix


def nlu(ctx, rc):
    require(rc == 0, f"nlu runner rc={rc}")
    directory = result_dir(ctx, "language/nlu")
    paths = [directory / "carwash.json", directory / "run.json"]
    raw, manifest = map(read, paths)
    require(raw["model"] == ctx.model and bool(raw["response"].strip()), "nlu response")
    for key in ("prompt_file", "answer_contract", "request"):
        require(bool(raw[key]), f"nlu missing {key}")
    require(manifest["status"] == "complete" and manifest["failure"] is None,
            "nlu incomplete manifest")
    require(manifest["expected_prompts"] == manifest["completed_prompts"] == ["carwash"],
            "nlu prompt count")
    return paths


def functionchat(ctx, rc):
    require(rc == 0, f"functionchat runner rc={rc}")
    directory = result_dir(ctx, "language/functionchat")
    paths = [directory / (name + ".json") for name in ("singlecall", "call_decision", "dialog")]
    for path in paths:
        raw = read(path)
        require(raw["metadata"]["subset_limit"] == 1, "functionchat subset_limit")
        require(len(raw["results"]) == 1, "functionchat result count")
        item = raw["results"][0]
        require(item["error"] is None and bool(item["raw_response"]), "functionchat item error")
        output = item["model_output"]
        content, calls = output.get("content"), output.get("tool_calls") or []
        require((isinstance(content, str) and bool(content.strip())) or bool(calls), "functionchat empty response")
        for call in calls:
            require(bool(call["function"]["name"]), "functionchat tool name missing")
            arguments = call["function"]["arguments"]
            require(isinstance(json.loads(arguments) if isinstance(arguments, str) else arguments, dict),
                    "functionchat tool arguments invalid")
        require(item["raw_response"]["model"] == ctx.model, "functionchat response model")
    coverage = directory / "coverage.json"
    value = read(coverage)
    require(all(k in value for k in ("source", "datasets", "not_measured")), "functionchat coverage")
    return paths + [coverage]


def multimodal(ctx, rc):
    require(rc == 1, f"K-DTCBench subset expected runner rc=1, got {rc}")
    directory = result_dir(ctx, "vision/multimodal/k_dtcbench")
    paths = [directory / p for p in ("results.json", "summary.json", "_derived/publish.json")]
    raw, summary, sidecar = map(read, paths)
    require(len(raw) == 1, "K-DTCBench result count")
    item = raw[0]
    require(item["error"] is None and bool(item["response"].strip()), "K-DTCBench response")
    require(item["predicted"] in ("A", "B", "C", "D"), "K-DTCBench unresolved choice")
    require(summary["model"] == ctx.model and summary["total"] == 1, "K-DTCBench identity/count")
    require(summary["run_config"]["extra"]["limit"] == 1, "K-DTCBench limit")
    for value, status in ((summary, summary["publish_status"]), (sidecar, sidecar)):
        require(status["publishable"] is False, "subset cannot be publishable")
        require(status["failures"] == ["기대 건수 240와 다름"], "unexpected publication failure")
        for key, count in (("attempted", 1), ("measured", 1), ("errored", 0), ("unresolved", 0)):
            require(value["counts"][key] == count, f"K-DTCBench {key}")
    return paths
