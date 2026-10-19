"""Temporary BASE and process groups; no sockets, live credentials, or process scans."""

import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.02)
    raise AssertionError('fixture deadline expired')


def gone(pid):
    try:
        os.kill(pid, 0)  # Only a PID explicitly recorded by this fixture.
    except ProcessLookupError:
        return True
    return False


class Fixture:
    def __init__(self, base):
        self.base, self.processes = base, []
        for directory in ('bin', '.venv/bin', 'shared/harness', 'orchestration/lanes', 'records', 'home'):
            (base / directory).mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / 'orchestration/run_lane.sh', base / 'orchestration/run_lane.sh')
        # 5a: keep sourced track definitions inside the isolated fixture BASE.
        shutil.copytree(REPO / 'orchestration/tracks', base / 'orchestration/tracks')
        shutil.copy2(REPO / 'shared/harness/harness_lib.sh', base / 'shared/harness/harness_lib.sh')
        shutil.copy2(REPO / 'shared/results_dir.sh', base / 'shared/results_dir.sh')
        shutil.copy2(Path(__file__).with_name('host_lock_worker.py'), base / 'worker.py')
        python = shlex.quote(sys.executable) + ' -B ' + shlex.quote(str(base / 'worker.py'))
        self.put('bin/python', '#!/bin/bash\nexec ' + python + ' "$@"\n', True)
        self.put('bin/curl', '#!/bin/bash\nexec ' + python + ' --curl "$@"\n', True)
        flock = shutil.which('flock')
        self.tool = 'flock' if flock else 'lockf' if os.access('/usr/bin/lockf', os.X_OK) else None
        if flock:
            (base / 'bin/flock').symlink_to(flock)
        self.put('.venv/bin/activate', 'export PATH=' + shlex.quote(str(base / 'bin') + ':/usr/bin:/bin') + '\n')
        self.put('.env', 'FIXTURE_KEY=synthetic-key\nTAUBENCH_USER_API_KEY=synthetic-judge\n')
        for stage in ('harness', 'taubench', 'nlu', 'functionchat', 'multimodal'):
            name = 'run_all.sh' if stage == 'multimodal' else 'run_' + stage + '.sh'
            self.put('vsm/' + stage + '/' + name, '#!/bin/bash\nexec ' + python + ' --evaluate ' + stage + ' "$@"\n')
        self.env = dict(PATH=str(base / 'bin') + ':/usr/bin:/bin', HOME=str(base / 'home'),
                        LC_ALL='C', PYTHONDONTWRITEBYTECODE='1')

    def put(self, relative, text, executable=False):
        path = self.base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if executable:
            path.chmod(0o755)
        return path

    def lane(self, name, track, host='fixture.invalid:18023'):
        self.put('orchestration/models/' + name + '.conf', '\n'.join([
            'CONFIG=fixture', 'HOST_ENV=FIXTURE_HOST', 'HOST_DEFAULT=' + host, 'KEYVAR=FIXTURE_KEY',
            'SESSION_' + track.upper() + '=' + name, 'DISPLAY=fixture', 'REPS=1', 'REQUIRE_NOTHINK=0', 'LANE_TOKENIZER=unused',
        ]) + '\n')
        path = self.base / 'orchestration/lanes' / (track + '.sh')
        if not path.is_symlink():
            path.symlink_to('../run_lane.sh')
        return path

    def start(self, name, track, host='fixture.invalid:18023', dry=False):
        path = self.lane(name, track, host)
        env = dict(self.env, LANE_DRY_RUN='1' if dry else '0')
        with (self.base / (name + '.stdout')).open('wb') as log:
            proc = subprocess.Popen(['/bin/bash', str(path), name], cwd=self.base, env=env,
                                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        session = name + '_r1' if track != 'taubench_std4' else name
        self.processes.append((proc, session))
        return proc

    def records(self, session, suffix='ready'):
        return [json.loads(path.read_text()) for path in sorted((self.base / 'records').glob(session + '.*.' + suffix))]

    def ready(self, name, track, proc):
        session = name + '_r1' if track != 'taubench_std4' else name
        def read():
            assert proc.poll() is None, self.output(name)
            return self.records(session)
        records = wait_for(read)
        assert all(record['fd9'] == 'closed' and record['pgid'] == proc.pid for record in records)
        assert '[harness] lock acquired' not in self.output(name)
        return session, records[0]

    def output(self, name):
        return (self.base / (name + '.stdout')).read_text()

    def release(self, session):
        (self.base / ('release.' + session)).touch()

    def close(self):
        for proc, session in self.processes:
            self.release(session)
        for proc, session in self.processes:
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                # Only the group created with start_new_session by this fixture.
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=5)
