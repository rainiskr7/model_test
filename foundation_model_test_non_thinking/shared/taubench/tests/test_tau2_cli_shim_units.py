"""9-0 shim contracts with synthetic tau2 modules and real serving constraints.

No time fields are omitted. Temporary paths occur only in the environment, not
the literal record bytes. Module caches, environment and sockets are restored.
"""

from copy import deepcopy
import json
from pathlib import Path
import socket
import sys
from types import ModuleType, SimpleNamespace

import pytest

from shared.taubench.runner import tau2_cli_shim as shim


ACTIVE_STDERR = (
    "[tau2-shim] http://local.invalid/v1 로 가는 요청에 서빙 프로파일을 적용한다"
    " (후보 모델=openai/candidate)\n"
)
MIXED_RECORD = b'''{
  "patched": true,
  "constrained_api_base": "http://local.invalid/v1",
  "candidate_model": "openai/candidate",
  "request_counts": {
    "matched": 2,
    "unmatched": 1,
    "base_unknown": 1
  },
  "removed_params": [
    "min_p",
    "seed"
  ],
  "adjusted_params": [
    "max_tokens",
    "skip_special_tokens"
  ],
  "user_removed_params": [
    "seed",
    "temperature"
  ],
  "user_adjusted_params": [
    "skip_special_tokens"
  ]
}'''
CANDIDATE_RECORD = b'''{
  "patched": true,
  "constrained_api_base": "http://local.invalid/v1",
  "candidate_model": "openai/candidate",
  "request_counts": {
    "matched": 1,
    "unmatched": 0,
    "base_unknown": 0
  },
  "removed_params": [
    "seed"
  ],
  "adjusted_params": [
    "max_tokens",
    "skip_special_tokens"
  ],
  "user_removed_params": [],
  "user_adjusted_params": []
}'''
SECOND_RECORD = b'''{
  "patched": true,
  "constrained_api_base": "http://local.invalid/v1",
  "candidate_model": "openai/candidate",
  "request_counts": {
    "matched": 1,
    "unmatched": 0,
    "base_unknown": 0
  },
  "removed_params": [],
  "adjusted_params": [],
  "user_removed_params": [
    "temperature"
  ],
  "user_adjusted_params": [
    "skip_special_tokens"
  ]
}'''


@pytest.fixture
def upstream(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("synthetic shim tests must not use the network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    record = tmp_path / "record.json"
    for key, value in {
        "TAUBENCH_CONSTRAINED_API_BASE": " http://local.invalid/v1/// ",
        "TAUBENCH_CANDIDATE_MODEL": " openai/candidate ",
        "TAUBENCH_REMOVED_PARAMS_OUT": str(record),
        "SERVING_UNSUPPORTED_SAMPLING_PARAMS": "temperature, seed, min_p",
        "SERVING_MAX_OUTPUT_TOKENS": "32",
        "SERVING_FORCE_SKIP_SPECIAL_TOKENS": "false",
    }.items():
        monkeypatch.setenv(key, value)
    modules = {name: ModuleType(name) for name in (
        "tau2", "tau2.utils", "tau2.utils.llm_utils", "tau2.cli",
    )}
    modules["tau2"].__path__ = []
    modules["tau2.utils"].__path__ = []
    modules["tau2"].utils = modules["tau2.utils"]
    modules["tau2"].cli = modules["tau2.cli"]
    modules["tau2.utils"].llm_utils = modules["tau2.utils.llm_utils"]
    calls = []

    def completion(*args, **kwargs):
        calls.append((args, deepcopy(kwargs)))
        return f"reply-{len(calls)}"

    modules["tau2.utils.llm_utils"].completion = completion
    modules["tau2.cli"].main = lambda: 23
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    return SimpleNamespace(llm=modules["tau2.utils.llm_utils"], cli=modules["tau2.cli"],
                           calls=calls, record=record)


def _candidate(upstream):
    return upstream.llm.completion(model="openai/candidate", api_base="http://local.invalid/v1",
                                   seed=7, max_tokens=128)


def test_matching_roles_request_precedence_and_exact_record_bytes(upstream, capsys):
    replies = []

    def run():
        replies.append(upstream.llm.completion(
            "prompt", model="openai/candidate", api_base=" http://local.invalid/v1/// ",
            seed=7, max_tokens=128,
            extra_body={"min_p": 0.1, "skip_special_tokens": True, "keep": "한글"},
        ))
        replies.append(upstream.llm.completion(
            model="openai/user", base_url="http://local.invalid/v1/",
            api_base="http://other.invalid/v1", temperature=0.0, max_tokens=16,
            extra_body={"seed": 11},
        ))
        replies.append(upstream.llm.completion(
            model="openai/candidate", base_url="http://other.invalid/v1",
            api_base="http://local.invalid/v1", seed=7, max_tokens=128,
        ))
        replies.append(upstream.llm.completion(
            model="openai/candidate", seed=5, extra_body={"skip_special_tokens": True},
        ))
        return 23

    upstream.cli.main = run
    assert shim.main() is None  # The upstream return value is intentionally ignored.
    assert replies == ["reply-1", "reply-2", "reply-3", "reply-4"]
    assert upstream.calls == [
        (("prompt",), {"model": "openai/candidate", "api_base": " http://local.invalid/v1/// ",
                       "max_tokens": 32, "extra_body": {"skip_special_tokens": False, "keep": "한글"}}),
        ((), {"model": "openai/user", "base_url": "http://local.invalid/v1/",
              "api_base": "http://other.invalid/v1", "max_tokens": 16,
              "extra_body": {"skip_special_tokens": False}}),
        ((), {"model": "openai/candidate", "base_url": "http://other.invalid/v1",
              "api_base": "http://local.invalid/v1", "seed": 7, "max_tokens": 128}),
        ((), {"model": "openai/candidate", "seed": 5, "extra_body": {"skip_special_tokens": True}}),
    ]
    assert upstream.record.read_bytes() == MIXED_RECORD
    assert not upstream.record.with_suffix(".json.tmp").exists()
    assert capsys.readouterr() == ("", ACTIVE_STDERR)


def test_consecutive_main_calls_start_with_fresh_role_sets_and_counts(upstream, monkeypatch, capsys):
    upstream.cli.main = lambda: _candidate(upstream)
    assert shim.main() is None
    assert upstream.record.read_bytes() == CANDIDATE_RECORD
    second = upstream.record.with_name("second.json")
    monkeypatch.setenv("TAUBENCH_REMOVED_PARAMS_OUT", str(second))
    # Keep the same imported shim and llm_utils object, including its first wrapper.
    upstream.cli.main = lambda: upstream.llm.completion(
        model="openai/user", api_base="http://local.invalid/v1", temperature=0.0,
    )
    assert shim.main() is None
    assert second.read_bytes() == SECOND_RECORD
    assert upstream.record.read_bytes() == CANDIDATE_RECORD
    assert upstream.calls == [
        ((), {"model": "openai/candidate", "api_base": "http://local.invalid/v1",
              "max_tokens": 32, "extra_body": {"skip_special_tokens": False}}),
        ((), {"model": "openai/user", "api_base": "http://local.invalid/v1",
              "extra_body": {"skip_special_tokens": False}}),
    ]
    assert capsys.readouterr() == ("", ACTIVE_STDERR + ACTIVE_STDERR)


@pytest.mark.parametrize("failure", [RuntimeError("upstream failed"), SystemExit(7)])
def test_finally_writes_record_and_propagates_original_exception(upstream, capsys, failure):
    def run():
        _candidate(upstream)
        raise failure

    upstream.cli.main = run
    with pytest.raises(type(failure)) as caught:
        shim.main()
    assert caught.value is failure
    assert upstream.record.read_bytes() == CANDIDATE_RECORD
    assert capsys.readouterr() == ("", ACTIVE_STDERR)


@pytest.mark.parametrize("failure", [None, RuntimeError("upstream failed"), SystemExit(9)])
def test_record_replace_failure_is_logged_without_masking_upstream(upstream, monkeypatch, capsys, failure):
    upstream.record.write_bytes(b"previous record\n")
    original_replace = Path.replace

    def fail_record_replace(path, target):
        if path == upstream.record.with_suffix(".json.tmp"):
            raise OSError("synthetic record failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_record_replace)

    def run():
        _candidate(upstream)
        if failure is not None:
            raise failure

    upstream.cli.main = run
    if failure is None:
        assert shim.main() is None
    else:
        with pytest.raises(type(failure)) as caught:
            shim.main()
        assert caught.value is failure
    assert upstream.record.read_bytes() == b"previous record\n"
    assert upstream.record.with_suffix(".json.tmp").read_bytes() == CANDIDATE_RECORD
    assert capsys.readouterr() == (
        "", ACTIVE_STDERR + "[tau2-shim] 제거 기록 실패: synthetic record failure\n",
    )


@pytest.mark.parametrize("inactive", ["base", "profile"])
def test_inactive_shim_does_not_wrap_completion(upstream, monkeypatch, capsys, inactive):
    if inactive == "base":
        monkeypatch.delenv("TAUBENCH_CONSTRAINED_API_BASE")
    else:
        for key in ("SERVING_UNSUPPORTED_SAMPLING_PARAMS", "SERVING_MAX_OUTPUT_TOKENS",
                    "SERVING_FORCE_SKIP_SPECIAL_TOKENS"):
            monkeypatch.delenv(key)
    original = upstream.llm.completion
    upstream.cli.main = lambda: _candidate(upstream)
    assert shim.main() is None
    assert upstream.llm.completion is original
    assert upstream.calls == [((), {
        "model": "openai/candidate", "api_base": "http://local.invalid/v1",
        "seed": 7, "max_tokens": 128,
    })]
    assert json.loads(upstream.record.read_bytes()) == {
        "patched": False,
        "constrained_api_base": None if inactive == "base" else "http://local.invalid/v1",
        "candidate_model": "openai/candidate",
        "request_counts": {"matched": 0, "unmatched": 0, "base_unknown": 0},
        "removed_params": [], "adjusted_params": [],
        "user_removed_params": [], "user_adjusted_params": [],
    }
    assert capsys.readouterr() == ("", "")


def test_unspecified_candidate_model_is_recorded_as_user(upstream, monkeypatch, capsys):
    monkeypatch.delenv("TAUBENCH_CANDIDATE_MODEL")
    upstream.cli.main = lambda: _candidate(upstream)
    assert shim.main() is None
    assert json.loads(upstream.record.read_bytes()) == {
        "patched": True, "constrained_api_base": "http://local.invalid/v1",
        "candidate_model": None,
        "request_counts": {"matched": 1, "unmatched": 0, "base_unknown": 0},
        "removed_params": [], "adjusted_params": [], "user_removed_params": ["seed"],
        "user_adjusted_params": ["max_tokens", "skip_special_tokens"],
    }
    assert capsys.readouterr() == (
        "", "[tau2-shim] http://local.invalid/v1 로 가는 요청에 서빙 프로파일을 적용한다"
        " (후보 모델=미지정)\n",
    )


def test_missing_record_destination_is_a_noop(upstream, monkeypatch, capsys):
    monkeypatch.delenv("TAUBENCH_REMOVED_PARAMS_OUT")
    assert shim.main() is None
    assert list(upstream.record.parent.iterdir()) == []
    assert capsys.readouterr() == ("", ACTIVE_STDERR)


def test_record_writer_preserves_utf8_key_order_and_no_final_lf(tmp_path):
    target = tmp_path / "nested/record.json"
    shim._write_record(str(target), {"message": "한글", "removed_params": []})
    assert target.read_bytes() == '{\n  "message": "한글",\n  "removed_params": []\n}'.encode("utf-8")
    assert not target.with_suffix(".json.tmp").exists()
