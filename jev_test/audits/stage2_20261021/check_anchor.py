"""무엇: 생산 위험 고정점 대조 · 입력: 현재 run/시험 관측 · 출력: 차이 경로 JSON · 계약 §9 C7."""

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from audits.stage2_20261021 import oracle
from jeveval.io import run_files
from jeveval.run import context


def risk_differences(rows, risk):
    """dev에서 고른 t_star로 test 수락 집합을 직접 세며 관측 점수와의 일치는 요구하지 않는다."""
    eligible = [r for r in rows if r.valid and not r.mask_empty]
    denom = sum(not r.mask_empty for r in rows)
    differences = []
    for tau in ('0.01', '0.02', '0.05'):
        cell = risk['cells'][tau]
        trial, cutoff = cell['test'], cell['t_star']
        path = ('risk.json', 'cells', tau)
        expected = dict(n_denom=denom)
        if cutoff is None:
            expected['n_accepted'] = None
        elif type(cutoff) not in (int, float) or not math.isfinite(cutoff):
            differences.append('.'.join((*path, 't_star')))
        else:
            accepted = [r for r in eligible if r.s >= cutoff]
            expected.update(n_accepted=len(accepted), k_errors=sum(bool(r.wrong) for r in accepted))
        differences += oracle.differences(expected, {k: trial[k] for k in expected}, (*path, 'test'))
    return differences


def check(root, directory):
    """현재 완료 입력을 복원하므로 파생 actions_only도 같은 대조를 수행한다."""
    ctx, stages, _ = context.completed(root, directory)
    rows = stages['test'].outcomes
    risk = run_files.read_json(ctx.directory / 'risk.json')
    selective = run_files.read_json(ctx.directory / 'selective.json')
    differences = risk_differences(rows, risk)
    expected = dict(**oracle.selective(rows), power=oracle.power(risk))
    differences += oracle.differences(expected, {k: selective[k] for k in expected}, ('selective.json',))
    return differences


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--run-dir', action='append', required=True)
    args = parser.parse_args(argv)
    results = []
    for index, directory in enumerate(args.run_dir):
        try:
            differences = check(args.root, directory)
        except Exception:
            # 입력 오류도 해당 run에만 귀속시키며 예외·원문·사용자 문자열은 출력하지 않는다.
            differences = ['inputs']
        results.append(dict(index=index, differences=differences))
    value = dict(ok=all(not r['differences'] for r in results), runs=results)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0 if value['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
