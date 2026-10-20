"""무엇: 형태 순수 AST 규칙 · 입력: 경로/소스 · 출력: 위반 목록 · 계약 §9 C1·C4."""

import ast
from importlib.util import resolve_name

ALLOWED = {
    'types': {'types'}, 'score': {'score', 'types'}, 'contract': {'contract', 'types'},
    'data': {'data', 'score', 'types'}, 'io': {'io', 'data', 'contract', 'score', 'types', 't0'},
    'client': {'client', 'contract', 'types'}, 't0': {'t0', 'contract', 'types'},
    'reference': {'reference', 'io', 'types'},
    'run': {'run', 'io', 'data', 'score', 'contract', 'types', 'client', 't0', 'reference'},
}
# README의 일반 방향보다 좁은 기존 파일 단위 예외. 새로운 역방향 import는 허용하지 않는다.
EXCEPTIONS = {('jeveval/data/split.py', 'jeveval.contract.stages'),
              ('jeveval/data/items/kosgd_requests.py', 'jeveval.contract.render'),
              ('jeveval/data/t0_fixture.py', 'jeveval.t0.request')}
SETS = {'kosgd', 'kosgd2', 'fc_call_decision', 'korfin_asc', 'klue_mrc_answerable', 'kmhas', 'kote_escalation'}
EFFECTS = {'open', 'read_text', 'read_bytes', 'write_text', 'write_bytes', 'mkdir', 'unlink',
           'now', 'utcnow', 'time', 'monotonic', 'perf_counter', 'sleep', 'connect', 'urlopen'}


def imports(tree, path):
    package = path[:-3].replace('/', '.').rsplit('.', 1)[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            if node.level:
                module = resolve_name('.' * node.level + module, package)
            if module == 'jeveval':
                for alias in node.names:
                    yield node.lineno, module + '.' + alias.name
            else:
                yield node.lineno, module


def violations(path, source):
    tree, errors = ast.parse(source), []
    if len(source.splitlines()) > 200:
        errors.append('file exceeds 200 lines')
    doc = ast.get_docstring(tree) or ''
    if not all(word in doc for word in ('무엇', '입력', '출력', '계약', '§')):
        errors.append('module contract docstring')
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.end_lineno - node.lineno + 1 > 50:
            errors.append(f'{node.lineno}: function exceeds 50 lines')
    if not path.startswith('jeveval/'):
        return errors
    layer = path.split('/')[1]
    for line, module in imports(tree, path):
        if module.startswith('jeveval.') and module.split('.')[1] not in ALLOWED.get(layer, set()):
            if (path, module) not in EXCEPTIONS:
                errors.append(f'{line}: forbidden dependency {module}')
    for node in ast.walk(tree):
        if layer in ('score', 'contract', 'types') and isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
            if name in EFFECTS:
                errors.append(f'{node.lineno}: effect in pure layer {name}')
            if layer == 'score' and name == 'metric_spec' and path != 'jeveval/score/set_metrics.py':
                errors.append(f'{node.lineno}: registry lookup inside calculation')
        scoped = layer == 'score' or path in ('jeveval/run/cmd_report.py', 'jeveval/run/cmd_compare.py')
        if scoped and isinstance(node, (ast.Compare, ast.MatchValue)):
            if any(isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in SETS for n in ast.walk(node)):
                errors.append(f'{node.lineno}: set name condition')
    return errors
