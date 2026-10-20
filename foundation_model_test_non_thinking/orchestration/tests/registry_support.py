"""Bundle B comparisons retain A's separate defect-reproduction baseline."""
import hashlib
from pathlib import Path

from orchestration.tests.laneconf_support import Comparison, REPO, head_bytes

REGISTRY_BASELINE = '587919d3ff568a08c94a59bd7c341506c0bd9bbe'


def with_completion_check(output):
    """C7 intentionally adds one follow-up per derive; retain every older byte."""
    stdout, stderr, rc = output
    lines = []
    for line in stdout.splitlines(keepends=True):
        lines.append(line)
        if line.startswith(b"COMMAND[if-exists]=python derive_multimodal_publish.py "):
            source = line.split(b" --source ", 1)[1]
            lines.append(b"COMMAND[if-derive-rc=0]=python -m "
                         b"shared.multimodal.benches.koffvqa_judge_complete " + source)
    return b"".join(lines), stderr, rc


class RegistryComparison(Comparison):
    revision = REGISTRY_BASELINE

    def install(self, side):
        # The shared fixture's source-only copy excludes pre-existing bytecode.
        super().install('working')
        paths = [Path('orchestration/run_lane.sh'), Path('orchestration/lane_guard.sh')]
        for package, suffix in (('tracks', '*.sh'), ('laneconf', '*.py')):
            paths.extend(path.relative_to(REPO) for path in (REPO / 'orchestration' / package).glob(suffix))
        for path in paths:
            data = head_bytes(path, self.revision) if side == 'HEAD' else (REPO / path).read_bytes()
            (self.base / path).write_bytes(data)
        self.display_keys(side)


def common_hashes(orch):
    """Hash the exact common-file inventory, deliberately excluding generated pyc."""
    paths = [orch / 'run_lane.sh', orch / 'lane_guard.sh', *sorted((orch / 'laneconf').glob('*.py'))]
    return {str(path.relative_to(orch)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
