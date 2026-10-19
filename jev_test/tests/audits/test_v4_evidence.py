"""감사 소스 해시에서 out/cache 제외 및 역사 호출 부재를 보존한다."""

from audits.audit_v4.evidence import code, historical


def test_code_hash_excludes_generated_output(tmp_path):
    source = tmp_path / "audits/audit_v4"
    source.mkdir(parents=True)
    (source / "run.py").write_text("pass\n")
    before = code(tmp_path)
    (source / "out").mkdir()
    (source / "out/output.py").write_text("ignored")
    assert code(tmp_path) == before
    assert historical(tmp_path, [], {}, {})["status"] == "INCOMPLETE"
