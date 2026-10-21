"""무엇: 독립 T0 worker 시험 · 입력: 현재 트리·외부 합성 scratch · 출력: 세 모델 PASS/help · 계약 §8-7."""

from pathlib import Path
import subprocess
import sys
from audits.serverless_20261021 import t0_compare
from jeveval.io.hashes import code_sha256


def test_worker_uses_existing_fake_runtime_without_network(tmp_path):
    root = Path(__file__).resolve().parents[2]
    worker = root / 'audits/serverless_20261021/t0_worker.py'
    scratch = tmp_path / 'worker'
    result = subprocess.run([sys.executable, '-I', '-B', str(worker), '--tree', str(root),
        '--scratch', str(scratch)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    outputs = t0_compare.normalized_outputs(scratch, code_sha256(root))
    assert len(outputs) == 26
    assert b'--run-dir' in outputs['server.help.txt']
