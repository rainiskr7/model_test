"""무엇: seal 존재 관측 시험 · 입력: 합성 run·유효하지 않은 seal · 출력: 존재만 표시 · 계약 §9c."""

from ops import status
from tests.run.analysis_support import prepared
from tests.run.file_support import output_files


def test_registration_columns_observe_presence_without_claiming_validity(tmp_path, monkeypatch, capsys):
    h = prepared(tmp_path, monkeypatch)
    test = h.directory / 'test'; test.mkdir()
    for name in ('question_seal.json', 'variant_seal.json'):
        (test / name).write_text('invalid synthetic seal')
    monkeypatch.setattr(status, 'VARIANTS', (('kosgd2', 'full'),))
    monkeypatch.setattr('sys.argv', ['status', 'synthetic', 'r1'])
    before = output_files(h.directory)
    capsys.readouterr()
    assert status.main() == 0
    header, *rows = capsys.readouterr().out.splitlines()
    assert header.endswith('question_seal_present\tvariant_seal_present')
    assert all(row.endswith('True\tTrue') for row in rows)
    assert 'registered' not in header
    assert output_files(h.directory) == before
