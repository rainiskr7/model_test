"""길이 경계·실제 변조·분모 누락 검사."""

from copy import deepcopy

from audits.audit_v4 import checks
from audits.audit_v4.selftest import fixture


def test_length_boundaries_and_interpolated_percentiles():
    assert checks.lengths([8192], 16384)["status"] == "PASS"
    x = checks.lengths([8193], 8192)
    assert x["status"] == "FAIL" and x["over_model_limit"] == 1
    assert checks.lengths([], 8192)["status"] == "INCOMPLETE"
    assert checks.lengths([1, 3], 8192)["p50"] == 2


def test_identity_gold_type_and_envelope_parameter_failures():
    requests, gold = fixture("kosgd2")
    assert checks.r4({}, requests) == "FAIL"
    changed = deepcopy(gold)
    changed["id"]["act_inform"]["gold"] = True
    assert checks.r7(changed, gold) == "FAIL"
    assert checks.hashes(b'a', b'b', b'a', None, None) == "FAIL"
    assert checks.combine(["FAIL", "INCOMPLETE"]) == "FAIL"
