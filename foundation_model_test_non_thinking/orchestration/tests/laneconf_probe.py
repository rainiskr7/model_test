"""Read a copied smoke configuration without invoking any serving track."""
import json
import os
from pathlib import Path
import sys

from orchestration.smoke.configuration import configuration


def main():
    root = Path(sys.argv[1])
    ctx = configuration(root, root, dict(os.environ), "fixture", sys.argv[2])
    print(json.dumps(dict(host=ctx.endpoint.removeprefix("http://").removesuffix("/v1"),
                          config=getattr(ctx, "config", None), keyvar=getattr(ctx, "keyvar", None),
                          tokenizer=str(ctx.tokenizer))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
