"""v3 여섯+신규 일곱 오류가 지정 규칙에서 검출되는지 확인한다."""

from audits.audit_v4.selftest import run


def test_all_thirteen_designated_failures():
    value = run("kosgd2")
    assert value["status"] == "PASS" and len(value["tests"]) == 13
    assert all(t["observed"] == "FAIL" and t["changed"] and t["baseline_passed"] for t in value["tests"])


def test_old_profile_marks_only_ongoing_two_not_applicable():
    value = run("kosgd")
    assert value["status"] == "PASS"
    assert [t["number"] for t in value["tests"] if t["status"] == "NOT_APPLICABLE"] == [12]
