"""9-0 parser contracts; prog and terminal width are fixed for literal stderr."""

import pytest

from shared.multimodal.benches import cli


USAGE = """usage: bench [-h] --model MODEL [--base-url BASE_URL] [--api-key API_KEY]
             [--limit LIMIT] [--max-tokens MAX_TOKENS]
             [--temperature TEMPERATURE] [--seed SEED] [--timeout TIMEOUT]
             [--retry-max RETRY_MAX] [--retry-backoff RETRY_BACKOFF]
             [--revision REVISION]
"""


@pytest.fixture
def parser(monkeypatch):
    monkeypatch.setenv("COLUMNS", "80")
    result = cli.standard_argparser()
    result.prog = "bench"
    return result


def test_required_model_and_all_defaults(parser, capsys):
    assert vars(parser.parse_args(["--model", "fixture"])) == {
        "model": "fixture", "base_url": "http://172.16.1.81:18090/v1",
        "api_key": None, "limit": None, "max_tokens": 512, "temperature": 0.0,
        "seed": None, "timeout": 60.0, "retry_max": 3, "retry_backoff": 1.0,
        "revision": None,
    }
    assert capsys.readouterr() == ("", "")


def test_custom_endpoint_default_and_explicit_values():
    parser = cli.standard_argparser(default_endpoint="http://unused.invalid/v1")
    assert parser.parse_args(["--model", "fixture"]).base_url == "http://unused.invalid/v1"
    assert vars(parser.parse_args([
        "--model", "vendor/model", "--base-url", "http://other.invalid/v1",
        "--api-key", "synthetic", "--limit", "2", "--max-tokens", "17",
        "--temperature", "0.25", "--seed", "9", "--timeout", "1.5",
        "--retry-max", "0", "--retry-backoff", "0.5", "--revision", "pinned",
    ])) == {
        "model": "vendor/model", "base_url": "http://other.invalid/v1",
        "api_key": "synthetic", "limit": 2, "max_tokens": 17, "temperature": 0.25,
        "seed": 9, "timeout": 1.5, "retry_max": 0, "retry_backoff": 0.5,
        "revision": "pinned",
    }


@pytest.mark.parametrize("argv,error", [
    ([], "bench: error: the following arguments are required: --model\n"),
    (["--model", "fixture", "--limit", "many"],
     "bench: error: argument --limit: invalid int value: 'many'\n"),
    (["--model", "fixture", "--unknown"],
     "bench: error: unrecognized arguments: --unknown\n"),
])
def test_parser_errors_preserve_stderr_and_exit_code(parser, capsys, argv, error):
    with pytest.raises(SystemExit) as caught:
        parser.parse_args(argv)
    assert caught.value.code == 2
    assert capsys.readouterr() == ("", USAGE + error)
