"""무엇: C2 run/compare/보고 회귀 CLI · 입력: 명시 옛/새 경로 · 출력: 차이 경로 · 계약 §9 C2."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from audits.stage2_20261021 import compare_evidence as evidence, normalize


def compare_variant(old, new):
    left, right = evidence.variant(old), evidence.variant(new)
    a, b = left[0], right[0]
    if any(a[k] != b[k] for k in ('model', 'set', 'variant')) or left[3] != right[3]:
        return ['identity']
    differences = []
    for stage in left[2]:
        x = [normalize.final(r, a) for r in left[2][stage]]
        y = [normalize.final(r, b) for r in right[2][stage]]
        if evidence.record_bytes(x) != evidence.record_bytes(y):
            differences.append(stage + '/final.jsonl')
        elif not left[3][stage] and (old / stage / 'final.jsonl').read_bytes() != (new / stage / 'final.jsonl').read_bytes():
            differences.append(stage + '/final.jsonl')
    for name in sorted(left[1].keys() | right[1].keys()):
        if name not in left[1] or name not in right[1]:
            differences.append(name)
            continue
        x = normalize.artifact(name, left[1][name], a, left[3]['dev'])
        y = normalize.artifact(name, right[1][name], b, right[3]['dev'])
        if canonical(x) != canonical(y):
            differences.append(name)
    return differences


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()


def compare_runs(old, new):
    """모델별 run 루트의 변형 합집합을 비교하여 누락도 실패시킨다."""
    inventories = [{p.parent.relative_to(root) for p in root.glob('A/*/*/fingerprint.json')} for root in (old, new)]
    if not all(inventories):
        raise ValueError('run inventory empty')
    result = []
    for relative in sorted(inventories[0] | inventories[1]):
        if relative not in inventories[0] & inventories[1]:
            result.append(str(relative / 'missing'))
        else:
            result += [str(relative / name) for name in compare_variant(old / relative, new / relative)]
    return result


def compare_tables(old, new, expected=7):
    inventories = [{p.relative_to(root) for p in root.glob('A/*/*/compare.json')} for root in (old, new)]
    if inventories[0] != inventories[1] or len(inventories[0]) != expected:
        return ['compare inventory']
    return [str(p) for p in sorted(inventories[0]) if (old / p).read_bytes() != (new / p).read_bytes()]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--old-run', type=Path, action='append', required=True)
    parser.add_argument('--new-run', type=Path, action='append', required=True)
    for name in ('old-compare', 'new-compare', 'old-report', 'new-report'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args(argv)
    try:
        if len(args.old_run) != len(args.new_run):
            raise ValueError('run pairs differ')
        differences = [f'model[{i}]/{p}' for i, (old, new) in enumerate(zip(args.old_run, args.new_run))
                       for p in compare_runs(old, new)]
        if bool(args.old_compare) != bool(args.new_compare) or bool(args.old_report) != bool(args.new_report):
            raise ValueError('paired optional paths required')
        if args.old_compare:
            differences += compare_tables(args.old_compare, args.new_compare)
        if args.old_report and normalize.report(args.old_report.read_text(), args.old_run[0].name) != normalize.report(
                args.new_report.read_text(), args.new_run[0].name):
            differences.append('report existing sections')
        result = dict(ok=not differences, differences=differences, compare_checked=bool(args.old_compare),
                      report_checked=bool(args.old_report))
    except Exception:
        result = dict(ok=False, error='comparison inputs or evidence invalid')
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
