"""Return fixture preflight responses without sockets or production endpoints."""

import json
import os
from pathlib import Path
import sys


def main():
    args = sys.argv[1:]
    if not args or args[-1] != 'http://fixture.invalid:18023/v1/models':
        return 22
    state = json.loads((Path(os.environ['MODEL_TEST_BASE']) / 'preflight.json').read_text())
    body = {'data': [{'id': state['model']}]}
    Path(args[args.index('-o') + 1]).write_text(json.dumps(body, separators=(',', ':')))
    print(state['status'], end='')
    return 0


if __name__ == '__main__':
    sys.exit(main())
