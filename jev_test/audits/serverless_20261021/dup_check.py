"""무엇: 새 중복 함수 검사 · 입력: 작업 트리와 선택 base · 출력: 중복 그룹 JSON · 계약 §9 서버 없는 수용."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from audits.publish_check.git_objects import git, resolve
from audits.serverless_20261021.function_shapes import functions


def selected(name):
    """코드 경로만 허용한다. 자료·실행 산출물의 내용은 열지 않는다."""
    path = PurePosixPath(name)
    if any(p in ('dataset', '.work', 'results', 'out', 'AI-Hub') for p in path.parts):
        return False
    if path.suffix == '.sh':
        return len(path.parts) == 2 and path.parts[0] == 'ops'
    if path.suffix != '.py':
        return False
    return (path.parts[0] in ('jeveval', 'audits') or
            (len(path.parts) == 2 and path.parts[0] == 'ops') or
            (path.parts[0] == 'tests' and ('support' in path.name or path.name == 'conftest.py')))


def sources(root, revision=None):
    """Git object에서 base 코드를 읽는다. 작업 트리는 추적/새 코드만 읽는다."""
    prefix = git(root, 'rev-parse', '--show-prefix').decode().strip()
    if revision is None:
        names = git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')
        for name in sorted(set(names)):
            path = root / name
            if selected(name) and path.is_file():
                yield name, path.read_text()
    else:
        revision = resolve(root, revision)
        names = git(root, 'ls-tree', '-r', '--name-only', '-z', '--full-tree', revision).decode().split('\0')
        for name in names:
            relative = name[len(prefix):] if name.startswith(prefix) else ''
            if relative and selected(relative):
                yield relative, git(root, 'show', f'{revision}:{name}').decode()


def groups(entries):
    """Python 본문 해시와 shell 함수 이름별 중복을 독립적으로 묶는다."""
    indexed = defaultdict(list)
    for path, source in entries:
        if path.endswith('.py'):
            for row in functions(source):
                indexed[('python', row['digest'])].append(dict(path=path, **row))
        else:
            pattern = r'^\s*(?:function\s+(\w+)(?:\s*\(\s*\))?|(\w+)\s*\(\s*\))\s*(?:\{|$)'
            for number, line in enumerate(source.splitlines(), 1):
                match = re.match(pattern, line)
                if match:
                    name = match[1] or match[2]
                    indexed[('shell', name)].append(dict(path=path, name=name, line=number))
    return [dict(language=kind, key=key, members=members)
            for (kind, key), members in sorted(indexed.items()) if len(members) > 1]


def new_groups(current, baseline):
    """줄 이동은 무시하되 기존 그룹에 추가된 함수도 새 중복으로 보고한다."""
    old = {(g['language'], g['key']): Counter((m['path'], m['name']) for m in g['members']) for g in baseline}
    return [g for g in current if not Counter((m['path'], m['name']) for m in g['members']) <=
            old.get((g['language'], g['key']), Counter())]


def check(root, base=None):
    current = groups(sources(root))
    added = current if base is None else new_groups(current, groups(sources(root, base)))
    return dict(ok=not added, base=base, groups=current, new_groups=added)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--base')
    args = parser.parse_args(argv)
    try:
        result = check(args.root.resolve(), args.base)
    except Exception:
        result = dict(ok=False, error='duplicate check inputs invalid')
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
