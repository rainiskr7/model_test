"""Executed as -c source in each code root; no dependency on this new package."""

import json
import sys
from pathlib import Path

from shared.multimodal.publish.derive import derive_source
from shared.multimodal.publish.schema import sidecar_json


def main():
    requests = json.loads(Path(sys.argv[1]).read_text())
    failures = 0
    for item in requests:
        try:
            _, sidecar = derive_source(Path(item["source"]), Path(item["base"]))
            target = Path(item["output"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(sidecar_json(sidecar), encoding="utf-8")
        except Exception as exc:
            failures += 1
            print(f"{item['source']}: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
