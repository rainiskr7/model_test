"""T0 정책의 닫힌 스키마, 수치 및 해시 경계."""

from copy import deepcopy

import pytest

from jeveval.contract.t0_policy import validate_t0_policy
from jeveval.types.t0_io import T0Policy

SHA = "a0" * 32


@pytest.fixture
def data(t0_policy):
    return dict(schema="t0_tolerance_policy/1", repeats=t0_policy.repeats,
                max_variation=t0_policy.max_variation, variants=deepcopy(t0_policy.variants))


def test_valid_t0_policy(data):
    result = validate_t0_policy(data, SHA)
    assert result == T0Policy(5, .02, data["variants"], SHA)
    data["variants"]["clef"].clear()
    assert result.variants["clef"] == ["batch_1", "batch_4", "batch_8"]


@pytest.mark.parametrize("change", ["schema", "missing", "extra", "not_mapping"])
def test_closed_t0_policy_schema(data, change):
    if change == "schema":
        data["schema"] = "t0_tolerance_policy/2"
    elif change == "missing":
        del data["repeats"]
    elif change == "extra":
        data["extra"] = 1
    else:
        data = []
    assert validate_t0_policy(data, SHA) == [
        "t0 policy requires schema t0_tolerance_policy/1 with repeats, max_variation, variants"]


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "5", None])
def test_invalid_repeats(data, value):
    data["repeats"] = value
    assert validate_t0_policy(data, SHA) == ["repeats must be a positive integer"]


@pytest.mark.parametrize("value", [-.01, True, "0.02", None, float("inf"), float("-inf"), float("nan")])
def test_invalid_variation_bound(data, value):
    data["max_variation"] = value
    assert validate_t0_policy(data, SHA) == ["max_variation must be a nonnegative finite number"]


@pytest.mark.parametrize("value", [None, [], {}, {"clef": ["batch_1"]}])
def test_variants_require_v11(data, value):
    data["variants"] = value
    assert validate_t0_policy(data, SHA) == [
        "variants must map model families (including pplx_v1_1) to variant lists"]


@pytest.mark.parametrize("family,names", [("clef", []), ("clef", "batch_1"), ("clef", [""]),
    ("clef", ["x", "x"]), ("clef", [True]), ("clef", [[]]), (1, ["x"])])
def test_invalid_variant_names(data, family, names):
    data["variants"][family] = names
    assert validate_t0_policy(data, SHA) == [
        f"variants[{family!r}] must be a non-empty list of unique names"]


@pytest.mark.parametrize("digest", [None, 64, "", "a" * 63, "a" * 65, "g" * 64])
def test_invalid_policy_sha256(data, digest):
    assert validate_t0_policy(data, digest) == ["policy sha256 must be a hex digest"]


def test_t0_policy_errors_accumulate(data):
    data.update(repeats=False, max_variation=-1, variants={})
    assert validate_t0_policy(data, "bad") == ["repeats must be a positive integer",
        "max_variation must be a nonnegative finite number",
        "variants must map model families (including pplx_v1_1) to variant lists",
        "policy sha256 must be a hex digest"]


def test_zero_bound_and_single_repeat_are_valid(data):
    data.update(repeats=1, max_variation=0)
    assert validate_t0_policy(data, SHA) == T0Policy(1, 0., data["variants"], SHA)
