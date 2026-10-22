"""무엇: 계약 지도와 원문 보존 검사 · 입력: 문서와 d41e8b9 · 출력: 차이 JSON · 계약 §9 서버 없는 수용."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from audits.publish_check.git_objects import git

PRESERVED = {
    'P1_CONTRACT.md': ((700, 828, '5d711f29274efcd36b3e67a4120b1e72fbb56d1f2425e3d29a5343379f6d154c'),
        (829, 905, '57c97ae3c2875111722ebddd4a7a4701d0e92ca16da17dcc2ed83e14c40e3a8f'),
        (906, 984, '57c894b3293f3b97043d84204532ec5740be04c2e7f9fa8cce3bb24c5026bb37')),
    'JEV_TEST_PLAN.md': ((421, 502, 'a2766d4e8ddd376837a8ac141c9849067661dcb55c3a870c9c8c52c1acafca4e'),
        (503, 541, 'f7cbec3695e5a945176e9698644ad31f10d5e8ab2d632bb12840854dfd6fc623'),
        (542, 567, '3ae784bcf20e8ac872f0a82c2966dc0bf44b8727fab1cc41bc111a2851946367'))}
AMENDMENTS = ('선택적 예측·조건부 통과 확률', 'family 의미', '복수 분석 선언·등록',
              '명시 감사 증거·독립 보조 보고', '수용 도구')
NOTES = ('3–15', '16', '17–29', '31–36, 125–129', '126, 136, 138', '145–153', '155–173, 403–447')
W2_HEADING = '## 판 5 보정 7 — kosgd2 W2 (2026-10-22)\n'
W2_PRESERVED = '### 원문 보존 — 판 5 보정 7 — kosgd2 W2 (2026-10-22) (기준 커밋 102a097)'
W2_SHA256 = '9698ecf1dfe9ead9db7eae8c2fbbcca8bb500c293e01ba6279c81b898c1ea9e5'


def extract_preserved_blocks(text):
    """fence payload의 LF·순서·중복을 그대로 보존한다."""
    blocks, fence, payload, preserved = [], None, [], False
    for line in text.splitlines(keepends=True):
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if fence is None and match:
            fence, payload = match[1], []
            preserved = line.rstrip() == "````markdown"
        elif fence is not None and re.fullmatch(r'\s*' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*', line):
            if preserved: blocks.append(''.join(payload))
            fence = None
        elif fence is not None:
            payload.append(line)
    if fence is not None:
        raise ValueError('unclosed fence')
    return blocks


def index_current_sections(text):
    """fence 내부의 옛 제목은 현행 절로 색인하지 않는다."""
    sections, fence = {}, None
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            if fence is None:
                fence = match[1]
            elif re.fullmatch(r'\s*' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*', line):
                fence = None
            continue
        heading = re.match(r'^#{1,6}\s+(?:§)?(\d+[a-z]?(?:-[\da-z]+)*)[.\s]', line)
        if fence is None and heading:
            key = heading[1]
            if key in sections:
                raise ValueError('duplicate current section')
            sections[key] = number
    if fence is not None:
        raise ValueError('unclosed fence')
    return sections


def verify_source_anchor(source, first, last, digest, preserved):
    """옛 지정 범위 첫 40 Unicode 문자와 실제 보존 payload를 각각 대조한다."""
    excerpt = ''.join(source.splitlines(keepends=True)[first - 1:last])
    return (first >= 1 and last >= first and len(excerpt) >= 40 and
            sha256(excerpt[:40].encode()).hexdigest() == digest and any(excerpt in block for block in preserved))


def table_rows(text):
    result = {'issues': [], 'amendments': [], 'notes': [], 'preserved': []}
    section = 'issues'
    for line in text.splitlines():
        if line.startswith('## 보정 5'): section = 'amendments'
        elif line.startswith('## 원문 블록'): section = 'preserved'
        elif line.startswith('## NOTES'): section = 'notes'
        if not line.startswith('| '): continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if cells[0] in ('번호·쟁점', '변경', '문서', 'd41e8b9 NOTES 범위'): continue
        result[section].append(cells)
    return result


def check_mapping_targets(rows, sections):
    """행 정체성과 현행 절 존재를 검사한다. 옛 식별자 포함을 의미 반영으로 간주하지 않는다."""
    errors = []
    keys = [re.match(r'(\d+)\.', r[0]) for r in rows['issues']]
    if [int(k[1]) if k else None for k in keys] != list(range(1, 22)):
        errors.append('issues: expected ordered unique 1..21')
    for kind, expected in (('amendments', AMENDMENTS), ('notes', NOTES)):
        if tuple(r[0] for r in rows[kind]) != expected:
            errors.append(f'{kind}: missing/duplicate/unexpected rows')
    for kind, column in (('issues', 4), ('amendments', 1), ('notes', 1)):
        for row in rows[kind]:
            target = row[column]
            for part in target.split(';'):
                document = 'JEV_TEST_PLAN.md' if '계획' in part else 'P1_CONTRACT.md'
                for section in re.findall(r'§(\d+[a-z]?(?:-[\da-z]+)*)', part):
                    if section not in sections[document]:
                        errors.append(f'{kind}/{row[0]}: missing {document} §{section}')
    return errors


def check(root):
    prefix = git(root, 'rev-parse', '--show-prefix').decode().strip()
    names = (*PRESERVED, 'jeveval/NOTES.md')
    old = {n: git(root, 'show', f'd41e8b9:{prefix}{n}').decode() for n in names}
    current = {n: (root / n).read_bytes().decode() for n in names}
    blocks = {n: extract_preserved_blocks(current[n]) if n in PRESERVED else [current[n]] for n in names}
    mapping = (root / 'CONTRACT_MAP.md').read_text()
    rows = table_rows(mapping)
    errors = check_mapping_targets(rows, {n: index_current_sections(current[n]) for n in PRESERVED})
    w2 = [b for b in blocks['JEV_TEST_PLAN.md'] if b.startswith(W2_HEADING)]
    if len(w2) != 1 or sha256(w2[0].encode()).hexdigest() != W2_SHA256:
        errors.append('JEV_TEST_PLAN.md: preserved W2 block')
    else:
        live = current['JEV_TEST_PLAN.md'].split(W2_PRESERVED, 1)[0]
        if W2_HEADING not in live or W2_HEADING + live.split(W2_HEADING, 1)[1].rstrip() + '\n' != w2[0]:
            errors.append('JEV_TEST_PLAN.md: current W2 differs from registered block')
    for name, expected in PRESERVED.items():
        # Keep all six d41e8b9 comparisons; W2 has its own exact-byte check above.
        found = [b for b in blocks[name] if len(b.encode()) > 1000 and not b.startswith(W2_HEADING)]
        if len(found) != len(expected): errors.append(f'{name}: block count')
        for i, (first, last, digest) in enumerate(expected):
            original = ''.join(old[name].splitlines(keepends=True)[first - 1:last])
            if i >= len(found) or found[i] != original or sha256(original.encode()).hexdigest() != digest:
                errors.append(f'{name}: preserved block {first}-{last}')
    for row in rows['issues']:
        name = re.search(r'(P1_CONTRACT.md|JEV_TEST_PLAN.md|jeveval/NOTES.md)', row[1])[1]
        first, last = map(int, re.findall(r'(\d+)–(\d+)행', row[1])[-1])
        digest = re.search(r'`([0-9a-f]{64})`', row[2])[1]
        if not verify_source_anchor(old[name], first, last, digest, [*blocks[name], current[name]]):
            errors.append(f'anchor: {row[0]}')
    expected_rows = [(n, f'{a}–{b}', len(''.join(old[n].splitlines(keepends=True)[a-1:b]).encode()), d)
                     for n, values in PRESERVED.items() for a, b, d in values]
    actual = [(r[0], r[1], int(r[2]), r[3].strip('`')) for r in rows['preserved']]
    if actual != expected_rows: errors.append('preserved: map rows differ')
    for row in rows['amendments']:
        if row[1].endswith('.md') and not (root / row[1]).is_file(): errors.append('missing tool documentation')
    return dict(ok=not errors, errors=errors, rows={k: len(v) for k, v in rows.items()}, blocks=6 + len(w2))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        result = check(args.root.resolve())
    except Exception:
        result = dict(ok=False, errors=['contract map inputs invalid'])
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
