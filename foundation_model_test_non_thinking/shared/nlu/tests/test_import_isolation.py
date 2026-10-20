"""Import purity and credential precedence, using synthetic .env files only."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest


CODE_ROOT = Path(__file__).resolve().parents[3]
RUNNER = Path(__file__).resolve().parents[1] / "nlu_gpustack.py"


@pytest.mark.parametrize("dotenv_available", [False, True])
@pytest.mark.parametrize("existing_key", [None, "already-set"])
def test_import_preserves_environment_and_path(tmp_path, dotenv_available, existing_key):
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=fake-import-key\nR0_IMPORT_SENTINEL=must-not-appear\n",
        encoding="utf-8",
    )
    env = dict(os.environ, PYTHONPATH=str(CODE_ROOT))
    env.pop("OPENAI_API_KEY", None)
    env.pop("R0_IMPORT_SENTINEL", None)
    if existing_key is not None:
        env["OPENAI_API_KEY"] = existing_key
    source = f'''
import os
import sys
from unittest.mock import Mock

sys.dont_write_bytecode = True
if {dotenv_available!r}:
    import dotenv
    # A regression must never open the real repository's .env.
    dotenv.load_dotenv = Mock(side_effect=AssertionError("import called dotenv"))
else:
    sys.modules["dotenv"] = None
before_env = dict(os.environ)
before_path = list(sys.path)
import shared.nlu.nlu_gpustack as module
assert set(os.environ) == set(before_env)
assert dict(os.environ) == before_env
assert sys.path == before_path
assert os.environ.get("OPENAI_API_KEY") == {existing_key!r}
assert "R0_IMPORT_SENTINEL" not in os.environ
assert module.api_key is None
if {dotenv_available!r}:
    dotenv.load_dotenv.assert_not_called()
'''
    result = subprocess.run(
        [sys.executable, "-c", source], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("existing_key", [None, "environment-wins", ""])
def test_load_api_key_preserves_precedence(runner, monkeypatch, tmp_path, fallback, existing_key):
    fake_env = tmp_path / ".env"
    fake_env.write_text(
        "# synthetic only\nOPENAI_API_KEY='file-key'\nR0_OTHER_SETTING=file-value\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("R0_OTHER_SETTING", raising=False)
    if existing_key is not None:
        monkeypatch.setenv("OPENAI_API_KEY", existing_key)
    with patch.dict(os.environ):
        if fallback:
            with patch.object(runner.importlib, "import_module", side_effect=ImportError("dotenv")):
                actual = runner.load_api_key()
        else:
            dotenv = pytest.importorskip("dotenv")
            original = dotenv.load_dotenv
            with patch.object(dotenv, "load_dotenv", wraps=lambda: original(fake_env)):
                actual = runner.load_api_key()
        assert actual == ("file-key" if existing_key is None else existing_key)
        assert os.environ["R0_OTHER_SETTING"] == "file-value"


def test_fallback_stops_at_first_env_and_searches_parents(runner, monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=parent-key\n", encoding="utf-8")
    child = tmp_path / "child"
    child.mkdir()
    monkeypatch.chdir(child)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch.dict(os.environ), patch.object(runner.importlib, "import_module", side_effect=ImportError):
        assert runner.load_api_key() == "parent-key"
    (child / ".env").write_text("R0_LOCAL=yes\n", encoding="utf-8")
    with patch.dict(os.environ), patch.object(runner.importlib, "import_module", side_effect=ImportError):
        assert runner.load_api_key() is None


@pytest.mark.parametrize("arguments,rc,expected", [
    ([], 1, "[nlu] OPENAI_API_KEY 가 없다 — 환경변수나 <BASE>/.env 에 설정하라."),
    (["--help"], 0, "--overwrite"),
    (["--model"], 2, "expected one argument"),
])
def test_cli_without_key_keeps_exit_contract(tmp_path, arguments, rc, expected):
    # A copied CLI keeps dotenv's __file__-based search inside a synthetic root.
    shared = tmp_path / "shared"
    nlu = shared / "nlu"
    nlu.mkdir(parents=True)
    shutil.copy2(RUNNER, nlu / RUNNER.name)
    shutil.copy2(CODE_ROOT / "shared/__init__.py", shared / "__init__.py")
    shutil.copy2(RUNNER.parent / "__init__.py", nlu / "__init__.py")
    for source in (RUNNER.parent / "scoring", RUNNER.parent.parent / "serving"):
        destination = nlu / "scoring" if source.name == "scoring" else shared / "serving"
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    shutil.copytree(CODE_ROOT / "shared/resultspath", shared / "resultspath",
                    ignore=shutil.ignore_patterns("__pycache__", "tests"))
    (tmp_path / ".env").write_text("# deliberately no API key\n", encoding="utf-8")
    env = dict(os.environ, MODEL_TEST_BASE=str(tmp_path), EVAL_TIMESTAMP="synthetic",
               PYTHONPATH=str(tmp_path))
    env.pop("OPENAI_API_KEY", None)
    result = subprocess.run(
        [sys.executable, "-m", "shared.nlu.nlu_gpustack", *arguments], cwd=tmp_path,
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == rc
    assert expected in (result.stdout if rc == 0 else result.stderr)
    if not arguments:
        assert result.stderr == expected + "\n"


def test_request_keeps_authorization_header(runner, monkeypatch):
    monkeypatch.setattr(runner, "api_key", "synthetic-key")
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"choices": [{"message": {"content": " answer "}}]},
    )
    with patch.object(runner.requests, "post", return_value=response) as post:
        assert runner.get_response("prompt", "model", "https://unused") == ("answer", {})
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer synthetic-key"
    assert json.loads(post.call_args.kwargs["data"])["model"] == "model"
