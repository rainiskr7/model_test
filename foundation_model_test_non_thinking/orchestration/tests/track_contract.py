"""Small static checker for documented track globals, not a general Bash parser."""
import re
import shlex


BUILTINS = {"BASH_REMATCH"}


def documented_inputs(document):
    """Read only the canonical input-variable table, not examples elsewhere."""
    table = document.split('<!-- input-variables:start -->', 1)[1].split('<!-- input-variables:end -->', 1)[0]
    return set(re.findall(r'`([A-Z][A-Z0-9_]*)`', table))


def variable_usage(source):
    """Collect parameter/arithmetic reads and assignment tokens in track syntax."""
    lexer = shlex.shlex(source, posix=False, punctuation_chars='();&|')
    lexer.whitespace_split = True
    tokens = list(lexer)
    reads, writes = set(), set()
    for token in tokens:
        # A quoted NAME=value argument or log message is not a shell assignment.
        assigned = re.match(r'^([A-Z][A-Z0-9_]*)(?:\[[^]]*\])?\+?=', token)
        if assigned:
            writes.add(assigned[1])
        if token.startswith("'"):
            continue
        reads.update(re.findall(r'\$(?:\{[!#]?)?([A-Z][A-Z0-9_]*)', token))
    # shlex separates arithmetic parentheses; inspect those expressions separately.
    for expression in re.findall(r'\$\(\((.*?)\)\)', source, flags=re.S):
        reads.update(re.findall(r'\b[A-Z][A-Z0-9_]*\b', expression))
    return reads, writes


def unknown_inputs(source, allowed):
    """Return external uppercase reads missing from the documented contract."""
    reads, writes = variable_usage(source)
    return reads - writes - BUILTINS - allowed
