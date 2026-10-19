"""보호 파일의 삭제/변경과 신규 출력 허용 범위를 검사한다."""

import pytest
from audits.audit_v4.preservation import snapshot, verify


def test_protected_bytes_and_new_outputs(tmp_path):
    p = tmp_path / "results/m/r/A/s/v/final.json"
    p.parent.mkdir(parents=True)
    p.write_text("old")
    before = snapshot(tmp_path)
    out = tmp_path / "results/_report/new.md"
    out.parent.mkdir()
    out.write_text("new")
    verify(before, snapshot(tmp_path))
    p.write_text("changed")
    with pytest.raises(ValueError): verify(before, snapshot(tmp_path))
    with pytest.raises(ValueError): verify({}, {"results/m/new.json": "hash"})


def test_new_output_inventory_rejects_work_or_root_reports(tmp_path):
    from audits.audit_v4.preservation import inventory, verify_outputs
    before = inventory(tmp_path)
    (tmp_path / "unauthorized.md").write_text("new")
    with pytest.raises(ValueError): verify_outputs(before, inventory(tmp_path))
    verify_outputs(set(), {"audits/kosgd2_pilot/pilot_selection.json"})
