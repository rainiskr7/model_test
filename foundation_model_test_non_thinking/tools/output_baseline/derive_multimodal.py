"""Derive only the pinned list; outputs are redirected outside the snapshot."""

import json
from pathlib import Path


def run(runner, entries):
    requests = []
    for item in entries:
        if item["kind"] == "multimodal":
            name = "multimodal/" + item["path"] + "/sidecar.json"
            requests.append({"name": name, "base": str(runner.snapshot),
                             "source": str(runner.snapshot / item["path"]),
                             "output": str(runner.output / "artifacts" / name)})
    runner.output.mkdir(parents=True, exist_ok=True)
    request_path = runner.output / "derive_requests.json"
    request_path.write_text(json.dumps(requests), encoding="utf-8")
    worker = Path(__file__).with_name("derive_worker.py").read_text()
    record = runner.run("multimodal/derive_source", ["-c", worker, str(request_path)])
    for item in requests:
        runner.artifact(item["name"], Path(item["output"]), record["rc"])
