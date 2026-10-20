"""Record runner_requests tests before accepting stored-output evidence."""

import xml.etree.ElementTree as ET

from tools.output_baseline.execution import command


def counts(path):
    cases = ET.parse(path).getroot().iter("testcase")
    result = dict(passed=0, failed=0, error=0, skipped=0)
    for case in cases:
        key = next((key for tag, key in (("failure", "failed"), ("error", "error"), ("skipped", "skipped"))
                    if case.find(tag) is not None), "passed")
        result[key] += 1
    return result


def run(base, evidence):
    junit = evidence / "runner_requests.xml"
    record = command(["bash", "tests/run_pytests.sh", "-k", "runner_requests", "--junitxml", str(junit)],
                     base, base, evidence / "prerequisite")
    record["counts"] = counts(junit) if junit.is_file() else {}
    record["ok"] = (record["rc"] == 0 and record["counts"].get("passed", 0) > 0
                    and not record["counts"].get("failed") and not record["counts"].get("error"))
    return record
