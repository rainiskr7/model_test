"""9-1a record assembly and late module lookup in the extracted wrapper."""

from copy import deepcopy
import json

import pytest

from shared.taubench.runner import tau2_cli_shim as shim


def test_record_payload_preserves_role_sorting_key_order_and_input_sets():
    removed = {"candidate": {"seed", "min_p"}, "user": {"temperature"}}
    adjusted = {"candidate": {"skip_special_tokens", "max_tokens"}, "user": set()}
    original = deepcopy((removed, adjusted))
    payload = shim._record_payload(
        True, "http://local.invalid/v1", "candidate",
        {"matched": 2, "unmatched": 1, "base_unknown": 1}, removed, adjusted,
    )
    assert json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") == b'''{
  "patched": true,
  "constrained_api_base": "http://local.invalid/v1",
  "candidate_model": "candidate",
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
    "temperature"
  ],
  "user_adjusted_params": []
}'''
    assert (removed, adjusted) == original


def test_record_payload_empty_identity_and_roles():
    assert shim._record_payload(
        False, "", "", {"matched": 0, "unmatched": 0, "base_unknown": 0},
        {"candidate": set(), "user": set()}, {"candidate": set(), "user": set()},
    ) == {
        "patched": False, "constrained_api_base": None, "candidate_model": None,
        "request_counts": {"matched": 0, "unmatched": 0, "base_unknown": 0},
        "removed_params": [], "adjusted_params": [],
        "user_removed_params": [], "user_adjusted_params": [],
    }


def test_wrapper_reaches_late_request_base_patch_and_records_before_upstream_failure(monkeypatch):
    removed = {"candidate": set(), "user": set()}
    adjusted = {"candidate": set(), "user": set()}
    counts = {"matched": 0, "unmatched": 0, "base_unknown": 0}
    calls = []
    failure = RuntimeError("patched completion")

    def apply(kwargs, *, sdk):
        calls.append(("apply", deepcopy(kwargs), sdk))
        del kwargs["seed"]

    def completion(*args, **kwargs):
        calls.append(("completion", args, kwargs))
        raise failure

    wrapped = shim._wrap_completion(
        completion, apply, "synthetic-base", "candidate", removed, adjusted, counts,
    )
    monkeypatch.setattr(shim, "_request_base", lambda kwargs: "synthetic-base")
    with pytest.raises(RuntimeError) as caught:
        wrapped("prompt", model="candidate", seed=7)
    assert caught.value is failure
    assert calls == [
        ("apply", {"model": "candidate", "seed": 7}, True),
        ("completion", ("prompt",), {"model": "candidate"}),
    ]
    assert removed == {"candidate": {"seed"}, "user": set()}
    assert adjusted == {"candidate": set(), "user": set()}
    assert counts == {"matched": 1, "unmatched": 0, "base_unknown": 0}
