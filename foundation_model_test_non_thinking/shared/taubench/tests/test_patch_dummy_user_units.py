"""9-0 patcher contracts on temporary source bytes; installed tau2 is never touched."""

import sys

import pytest

from shared.taubench import patch_dummy_user


ORIGINAL = '''# 합성 upstream
class UserSimulator(BaseUser):
    def __init__(self):
        super().__init__(llm="dummy")

class DummyUser(BaseUser):
    def __init__(self):
        super().__init__(llm="dummy")

class OtherUser(BaseUser):
    def __init__(self):
        super().__init__(llm="dummy")
'''.encode("utf-8")
PATCHED = '''# 합성 upstream
class UserSimulator(BaseUser):
    def __init__(self):
        super().__init__(llm="dummy")

class DummyUser(BaseUser):
    def __init__(self, **_ignored_upstream_kwargs):
        super().__init__(llm="dummy")

class OtherUser(BaseUser):
    def __init__(self):
        super().__init__(llm="dummy")
'''.encode("utf-8")


def test_first_patch_and_second_call_preserve_exact_bytes(monkeypatch, tmp_path, capsys):
    source = tmp_path / "user_simulator.py"
    source.write_bytes(ORIGINAL)
    monkeypatch.setattr(sys, "argv", ["patch_dummy_user.py", str(source)])
    assert patch_dummy_user.main() == 0
    assert source.read_bytes() == PATCHED
    assert capsys.readouterr() == (
        "[taubench/patch] DummyUser.__init__ now accepts and ignores upstream kwargs: "
        f"{source}\n", "",
    )
    assert patch_dummy_user.main() == 0
    assert source.read_bytes() == PATCHED
    assert capsys.readouterr() == (
        "[taubench/patch] DummyUser already patched (idempotent no-op)\n", "",
    )


@pytest.mark.parametrize("original,error", [
    (b"class UserSimulator(BaseUser):\n    pass\n",
     "ERROR: class DummyUser not found — upstream layout changed; re-verify the patch.\n"),
    (b"class DummyUser(BaseUser):\n    def __init__(self, tools):\n        pass\n",
     "ERROR: expected DummyUser.__init__ body not found — upstream may have fixed it. Re-verify.\n"),
])
def test_unsupported_source_is_not_written(monkeypatch, tmp_path, capsys, original, error):
    source = tmp_path / "user_simulator.py"
    source.write_bytes(original)
    monkeypatch.setattr(sys, "argv", ["patch_dummy_user.py", str(source)])
    assert patch_dummy_user.main() == 1
    assert source.read_bytes() == original
    assert capsys.readouterr() == ("", error)


def test_missing_source_returns_one_without_creating_file(monkeypatch, tmp_path, capsys):
    source = tmp_path / "missing.py"
    monkeypatch.setattr(sys, "argv", ["patch_dummy_user.py", str(source)])
    assert patch_dummy_user.main() == 1
    assert not source.exists()
    assert capsys.readouterr() == ("", f"ERROR: not found: {source}\n")


@pytest.mark.parametrize("argv", [["patch_dummy_user.py"], ["patch_dummy_user.py", "a", "b"]])
def test_bad_argument_count_returns_two(monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, "argv", argv)
    assert patch_dummy_user.main() == 2
    assert capsys.readouterr() == (
        "", "usage: patch_dummy_user.py <site-packages/tau2/user/user_simulator.py>\n",
    )
