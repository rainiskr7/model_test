"""Terminate and reap only a subprocess group created by the smoke invocation."""
import os
import signal
import subprocess


def terminate(proc):
    """Stop the owned session, escalating if a child keeps the output pipe open."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass  # The process may have exited between communicate and termination.
    try:
        return proc.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return proc.communicate()
