"""무엇: 함수 AST 정규화 · 입력: Python 소스 · 출력: 위치와 본문 해시 · 계약 §9 서버 없는 수용."""

import ast
from copy import deepcopy
from hashlib import sha256


def without_docstring(body):
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            return body[1:]
    return body


class Bindings(ast.NodeVisitor):
    """현재 함수의 인자·지역 바인딩만 수집한다. 외부 이름·속성 이름은 유지한다."""
    def __init__(self, args, depth=0):
        ordered = [*args.posonlyargs, *args.args, *args.kwonlyargs]
        ordered += [a for a in (args.vararg, args.kwarg) if a is not None]
        self.depth = depth
        self.names = {arg.arg: f'd{depth}_arg{i}' for i, arg in enumerate(ordered)}
        self.external = set()
        self.nonlocal_names = set()

    def bind(self, name):
        if name is not None and name not in self.names:
            self.names[name] = f'd{self.depth}_local{len(self.names)}'

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bind(node.id)

    def visit_FunctionDef(self, node):
        self.bind(node.name)

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef

    def visit_Lambda(self, node):
        pass

    def visit_Global(self, node):
        self.external.update(node.names)

    def visit_Nonlocal(self, node):
        self.nonlocal_names.update(node.names)

    def visit_ListComp(self, node):
        pass

    visit_SetComp = visit_ListComp
    visit_DictComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp

    def visit_ExceptHandler(self, node):
        self.bind(node.name)
        self.generic_visit(node)

    def visit_alias(self, node):
        self.bind(node.asname or node.name.split('.')[0])

    def visit_MatchAs(self, node):
        self.bind(node.name)
        self.generic_visit(node)

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node):
        self.bind(node.rest)
        self.generic_visit(node)


def scope_names(body, args, outer, depth):
    bindings = Bindings(args, depth)
    for statement in body:
        bindings.visit(statement)
    names = {k: v for k, v in outer.items() if k not in bindings.external}
    names.update({k: v for k, v in bindings.names.items() if k not in bindings.external | bindings.nonlocal_names})
    return names


class Normalize(ast.NodeTransformer):
    def __init__(self, names, depth=0):
        self.names = names
        self.depth = depth

    def visit_Name(self, node):
        node.id = self.names.get(node.id, node.id)
        return node

    def visit_arg(self, node):
        node.arg = self.names.get(node.arg, node.arg)
        return node

    def visit_ExceptHandler(self, node):
        node.name = self.names.get(node.name, node.name)
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.name = self.names.get(node.name, node.name)
        node.body = without_docstring(node.body)
        inner = Normalize(scope_names(node.body, node.args, self.names, self.depth + 1), self.depth + 1)
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.args.defaults = [self.visit(d) for d in node.args.defaults]
        node.args.kw_defaults = [self.visit(d) if d is not None else None for d in node.args.kw_defaults]
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs, node.args.vararg, node.args.kwarg):
            if arg is not None: inner.visit_arg(arg)
        node.body = [inner.visit(s) for s in node.body]
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        inner = Normalize(scope_names([node.body], node.args, self.names, self.depth + 1), self.depth + 1)
        node.args = inner.visit(node.args)
        node.body = inner.visit(node.body)
        return node

    def visit_alias(self, node):
        name = node.asname or node.name.split('.')[0]
        if name in self.names: node.asname = self.names[name]
        return node

    def visit_Nonlocal(self, node):
        node.names = [self.names.get(n, n) for n in node.names]
        return node

    def visit_ListComp(self, node):
        bindings = Bindings(ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), self.depth + 1)
        for generator in node.generators: bindings.visit(generator.target)
        inner = Normalize({**self.names, **bindings.names}, self.depth + 1)
        first = self.visit(node.generators[0].iter)
        node = inner.generic_visit(node)
        node.generators[0].iter = first
        return node

    visit_SetComp = visit_ListComp
    visit_DictComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp

    def visit_MatchAs(self, node):
        node.name = self.names.get(node.name, node.name)
        return self.generic_visit(node)

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node):
        node.rest = self.names.get(node.rest, node.rest)
        return self.generic_visit(node)


def body_hash(node):
    body = without_docstring(deepcopy(node.body))
    if len(body) < 3:
        return None
    names = scope_names(body, node.args, {}, 0)
    tree = Normalize(names).visit(ast.Module(body=body, type_ignores=[]))
    return sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()


def functions(source):
    """같은 이름의 메서드도 한정 이름으로 구별하고 줄은 진단에만 사용한다."""
    result = []
    def walk(node, parents):
        for child in ast.iter_child_nodes(node):
            scoped = isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            name = parents + [child.name] if scoped else parents
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                digest = body_hash(child)
                if digest is not None:
                    result.append(dict(name='.'.join(name), line=child.lineno, digest=digest))
            walk(child, name)
    walk(ast.parse(source), [])
    return result
