"""Offline lane substitutes; all processes and marker files belong to the fixture."""

import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time


def write_record(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


def evaluate(base, stage):
    session = os.environ['EVAL_TIMESTAMP']
    prefix = base / 'records' / (session + '.' + stage)
    stop = prefix.with_suffix(prefix.suffix + '.stop')
    release = base / ('release.' + session)
    try:
        os.fstat(9)
        fd9 = 'open'
    except OSError:
        fd9 = 'closed'
    child = subprocess.Popen([sys.executable, '-B', __file__, '--leaf', str(stop)])
    record = dict(pid=os.getpid(), child=child.pid, pgid=os.getpgrp(), fd9=fd9, stage=stage)
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    try:
        write_record(Path(str(prefix) + '.ready'), record)
        deadline = time.monotonic() + 60
        while not release.exists() and time.monotonic() < deadline:
            time.sleep(.02)
    finally:
        stop.touch()
        record['child_rc'] = child.wait(timeout=5)
        record['child_reaped'] = True
        write_record(Path(str(prefix) + '.done'), record)


def main():
    if sys.argv[1] == '--leaf':
        deadline = time.monotonic() + 65
        while not Path(sys.argv[2]).exists() and time.monotonic() < deadline:
            time.sleep(.02)
        return 0
    base = Path(os.environ['MODEL_TEST_BASE'])
    if sys.argv[1].endswith('/configs/load_model_config.py'):
        for name, value in [('MODEL', 'fixture_model'), ('BASE_URL_CHAT', os.environ['BASE_URL_CHAT_OVERRIDE']),
                            ('BASE_URL_V1', os.environ['BASE_URL_V1_OVERRIDE'])]:
            print('export ' + name + '=' + shlex.quote(value))
    elif sys.argv[1] == '--curl':
        Path(sys.argv[sys.argv.index('-o') + 1]).write_text('{"data":[{"id":"fixture_model"}]}')
        with (base / 'preflights').open('a') as stream:
            stream.write(sys.argv[-1] + '\n')
        print('200', end='')
    elif sys.argv[1] == '--evaluate':
        evaluate(base, sys.argv[2])
    else:
        raise ValueError('unexpected fixture command: ' + repr(sys.argv[1:]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
