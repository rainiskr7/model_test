"""무엇: 두 소스 T0 바이트 비교 · 입력: base/current 트리·외부 scratch · 출력: 차이 JSON · 계약 §8-7."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from audits.stage2_20261021.compare_evidence import parse
from jeveval.io.hashes import code_sha256
from jeveval.io.run_files import json_bytes

FAMILIES = ('clef', 'pplx_v1', 'pplx_v1_1')
FILES = {'inputs.jsonl', 'fingerprint.json', 'reference.jsonl', 'server.jsonl',
         'variants.jsonl', 'tolerance.json', 't0.json'}


def normalized_outputs(folder, expected_code):
    """실제 파일 연결을 확인한 다음 두 명시 경로만 정규화한다."""
    result = {}
    for family in FAMILIES:
        directory = folder / family / 'results/_t0' / family / 'r1'
        payloads = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
        if payloads.keys() != FILES:
            raise ValueError('T0 artifact inventory')
        fp, record = (parse(payloads[n]) for n in ('fingerprint.json', 't0.json'))
        if json_bytes(fp) != payloads['fingerprint.json'] or json_bytes(record) != payloads['t0.json']:
            raise ValueError('noncanonical T0 evidence bytes')
        if fp['code_sha256'] != expected_code:
            raise ValueError('T0 source code fingerprint')
        if record['fingerprint_sha256'] != sha256(payloads['fingerprint.json']).hexdigest():
            raise ValueError('T0 fingerprint link')
        if record['status'] != 'PASS':
            raise ValueError('synthetic T0 did not pass')
        fp['code_sha256'] = '<code>'
        record['fingerprint_sha256'] = '<verified fingerprint>'
        payloads.update({'fingerprint.json': json_bytes(fp), 't0.json': json_bytes(record)})
        result.update({f'{family}/{name}': data for name, data in payloads.items()})
    for name in ('inputs', 'reference', 'server', 'tolerance', 'judge'):
        result[f'{name}.help.txt'] = (folder / f'{name}.help.txt').read_bytes()
    return result


def compare(base_tree, current_tree, scratch):
    """프로세스마다 한 소스만 import한다. 실패한 worker 출력은 원문 없이 표시한다."""
    trees = [Path(t).resolve() for t in (base_tree, current_tree)]
    scratch = Path(scratch).resolve()
    if scratch.exists() or any(scratch.is_relative_to(t) for t in (*trees, ROOT)):
        raise ValueError('new external scratch required')
    scratch.mkdir(parents=True)
    folders = [scratch / name for name in ('base', 'current')]
    for tree, folder in zip(trees, folders):
        proc = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).with_name('t0_worker.py')),
            '--tree', str(tree), '--scratch', str(folder)], cwd=scratch, capture_output=True, timeout=180)
        if proc.returncode:
            return dict(ok=False, error='T0 worker failed', side=folder.name)
    left, right = [normalized_outputs(folder, code_sha256(tree)) for tree, folder in zip(trees, folders)]
    differences = [p for p in sorted(left.keys() | right.keys()) if left.get(p) != right.get(p)]
    return dict(ok=not differences, differences=differences, artifacts=21, help=5, independent_processes=2)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-tree', type=Path, required=True)
    parser.add_argument('--current-tree', type=Path, default=ROOT)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = compare(args.base_tree, args.current_tree, args.scratch)
    except Exception:
        result = dict(ok=False, error='T0 comparison inputs or evidence invalid')
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
