"""Conservative statement scanner for literal uppercase shell assignments.

Recognizes assignment-only statements and local/export/readonly declarations at
statement boundaries (newline, semicolon, &&, ||, braces). Command-prefix env
assignments are excluded. Not a Bash parser: eval, indirect writes, read/printf -v,
arithmetic writes, and dynamically constructed names are outside this contract.
"""
import re
import shlex


def standalone_assignments(source):
    """Return literal destinations, excluding assignments attached to a command."""
    source = source.replace('\\\n', '')
    # Hide RHS groups before tokenization: their commands are not a command prefix
    # on the enclosing assignment. This supports the repository's literal syntax,
    # not arbitrary quoted parentheses, heredocs, or dynamically generated Bash.
    source = re.sub(r'\$\(\(.*?\)\)', 'ARITHMETIC', source, flags=re.S)
    while re.search(r'\$\([^()]*\)', source):
        source = re.sub(r'\$\([^()]*\)', 'SUBSTITUTION', source)
    source = re.sub(r'([A-Z][A-Z0-9_]*\+?=)\([^()]*\)', r'\1ARRAY', source, flags=re.S)
    statements, statement = [], []
    for line in source.splitlines():
        lexer = shlex.shlex(line, posix=True, punctuation_chars=';|&{}')
        lexer.whitespace_split = True
        for token in lexer:
            if token and all(char in ';|&{}' for char in token):
                statements.append(statement)
                statement = []
            else:
                statement.append(token)
        statements.append(statement)
        statement = []
    names = set()
    for words in statements:
        if words and words[0] in ('then', 'do', 'else'):
            words = words[1:]
        declaration = bool(words and words[0] in ('local', 'export', 'readonly'))
        if declaration:
            words = [word for word in words[1:] if not word.startswith('-')]
        matches = [re.match(r'^([A-Za-z_][A-Za-z0-9_]*)(?:\[[^]]*\])?\+?=', word) for word in words]
        if declaration or (matches and all(matches)):
            names.update(match[1] for match in matches if match and
                         re.fullmatch(r'[A-Z][A-Z0-9_]*', match[1]))
    return names
