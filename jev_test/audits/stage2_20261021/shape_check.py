"""무엇: 형태·짝 시험·nodeid 검사 · 입력: 저장소/manifest · 출력: 위반 목록 · 계약 §9 C1."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from audits.stage2_20261021.shape_rules import violations


def changed(root):
    """코드 경로만 git에 질의하며 실결과·데이터 트리는 열거하지 않는다."""
    scopes = ['jeveval', 'tests', 'audits/stage2_20261021', 'ops/status.py']
    commands = [['git', 'diff', '--relative', '--name-only', 'HEAD', '--', *scopes],
                ['git', 'ls-files', '--others', '--exclude-standard', '--', *scopes]]
    return {p for cmd in commands for p in subprocess.check_output(cmd, cwd=root, text=True).splitlines()
            if p.endswith('.py')}


def check(root):
    paths = {p.relative_to(root).as_posix() for p in (root / 'jeveval').rglob('*.py')}
    paths |= {p.relative_to(root).as_posix() for p in (root / 'audits/stage2_20261021').glob('*.py')}
    edits = changed(root)
    paths |= edits
    errors = [f'{name}: {e}' for name in sorted(paths) for e in violations(name, (root / name).read_text())]
    for name in sorted(edits):
        path = Path(name)
        if path.parts[0] == 'jeveval' and path.name != '__init__.py':
            paired = root / 'tests' / path.relative_to('jeveval').parent / ('test_' + path.name)
        elif path.parts[:2] == ('audits', 'stage2_20261021'):
            paired = root / 'tests/audits' / ('test_' + path.name)
        else:
            continue
        if not paired.is_file():
            errors.append(f'{name}: missing paired test')
    return errors


def nodeids(old, new):
    errors = [f'deleted nodeid: {key}' for key in old.keys() - new.keys()]
    for key, marks in new.items():
        if set(marks) - set(old.get(key, [])):
            errors.append(f'new skip/xfail: {key}')
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--before', type=Path)
    parser.add_argument('--after', type=Path)
    args = parser.parse_args(argv)
    errors = check(args.root)
    if bool(args.before) != bool(args.after):
        errors.append('both nodeid manifests required')
    elif args.before:
        errors += nodeids(json.loads(args.before.read_text()), json.loads(args.after.read_text()))
    print(json.dumps(dict(ok=not errors, violations=errors), ensure_ascii=False, indent=1))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
