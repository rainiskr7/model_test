"""무엇: 실제 run oracle 대조 CLI · 입력: 명시 run 폴더 · 출력: 원문 없는 차이 · 계약 §9 C3."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from audits.stage2_20261021 import oracle
from jeveval.io import history, run_files
from jeveval.run import history_check, history_stage


def check(root, directory):
    """동결 요청 복원만 공유한다. selective/power 계산 구현은 import하지 않는다."""
    saved = history.read(root, directory)
    if history_check.check(saved).status != 'verified_complete':
        raise ValueError('complete history required')
    data = history_stage.restore(root, saved, 'test')
    value = run_files.read_json(saved.directory / 'selective.json')
    expected = dict(**oracle.selective(data.outcomes), power=oracle.power(saved.artifacts['risk.json']))
    actual = {k: value[k] for k in expected}
    return oracle.differences(expected, actual)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--run-dir', action='append', required=True)
    args = parser.parse_args(argv)
    try:
        results = [dict(index=i, differences=check(args.root, p)) for i, p in enumerate(args.run_dir)]
        value = dict(ok=all(not r['differences'] for r in results), runs=results)
    except Exception:
        value = dict(ok=False, error='oracle inputs or reconstruction unavailable')
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0 if value['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
