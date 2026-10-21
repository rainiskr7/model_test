"""무엇: 새 중복 판정 시험 · 입력: Python/shell·합성 Git base · 출력: 추가 그룹만 실패 · 계약 §9."""

import subprocess
from audits.serverless_20261021 import dup_check

BODY = 'def f(value):\n x = value + 1\n y = x * 2\n return y\n'


def test_groups_and_existing_duplicate_growth():
    old = dup_check.groups([('jeveval/a.py', BODY), ('jeveval/b.py', BODY.replace('value', 'other'))])
    assert len(old) == 1 and not dup_check.new_groups(old, old)
    new = dup_check.groups([('jeveval/a.py', BODY), ('jeveval/b.py', BODY), ('jeveval/c.py', BODY)])
    assert len(dup_check.new_groups(new, old)) == 1
    shell = dup_check.groups([('ops/a.sh', 'work() { :; }\n'), ('ops/b.sh', 'work() { true; }\n')])
    assert shell[0]['language'] == 'shell'


def test_protected_paths_and_scope():
    assert dup_check.selected('tests/run/analysis_support.py')
    assert dup_check.selected('ops/status.py')
    for path in ('dataset/x.py', '.work/a.py', 'results/a.py', 'audits/a/out/x.py', 'tests/run/test_cli.py'):
        assert not dup_check.selected(path)


def test_base_is_read_without_checkout_and_new_copy_fails(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args], text=True).strip()
    git('init', '-q'); git('config', 'user.email', 'synthetic@example.invalid'); git('config', 'user.name', 'Synthetic')
    folder = tmp_path / 'jeveval'; folder.mkdir(); (folder / 'a.py').write_text(BODY)
    git('add', '.'); git('commit', '-qm', 'synthetic baseline'); head = git('rev-parse', 'HEAD')
    assert dup_check.check(tmp_path, head)['ok']
    (folder / 'b.py').write_text(BODY)
    assert not dup_check.check(tmp_path, head)['ok']
    assert git('rev-parse', 'HEAD') == head


def test_repeated_same_name_growth_and_bash_function_syntax():
    old = dup_check.groups([('ops/a.sh', 'function same { :; }\nsame() { :; }\n')])
    new = dup_check.groups([('ops/a.sh', 'function same { :; }\nsame() { :; }\nfunction same() { :; }\n')])
    assert len(old) == 1 and len(new[0]['members']) == 3
    assert dup_check.new_groups(new, old)
