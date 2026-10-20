from tools.output_baseline.prerequisite import counts


def test_junit_counts_nested_suites(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text('<testsuites><testsuite><testcase/><testcase><failure/></testcase>'
                      '<testcase><skipped/></testcase><testcase><error/></testcase></testsuite></testsuites>')
    assert counts(report) == {"passed": 1, "failed": 1, "skipped": 1, "error": 1}
