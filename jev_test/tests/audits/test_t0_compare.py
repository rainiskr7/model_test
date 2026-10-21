"""무엇: T0 비교의 허용 경로 시험 · 입력: 합성 파일·SHA 손상 · 출력: 제한 정규화 · 계약 §8-7."""

from hashlib import sha256
import pytest
from audits.serverless_20261021 import t0_compare
from jeveval.io.run_files import write_json


def artifacts(folder, code):
    for family in t0_compare.FAMILIES:
        directory = folder / family / 'results/_t0' / family / 'r1'
        directory.mkdir(parents=True)
        for name in t0_compare.FILES:
            (directory / name).write_bytes(b'{}\n')
        write_json(directory / 'fingerprint.json', dict(code_sha256=code))
        digest = sha256((directory / 'fingerprint.json').read_bytes()).hexdigest()
        write_json(directory / 't0.json', dict(status='PASS', fingerprint_sha256=digest, score=1))
    for name in ('inputs', 'reference', 'server', 'tolerance', 'judge'):
        (folder / f'{name}.help.txt').write_text(name + '\n')


def test_only_two_fields_normalized_after_actual_link_validation(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    artifacts(a, 'a'*64); artifacts(b, 'b'*64)
    left = t0_compare.normalized_outputs(a, 'a'*64)
    assert left == t0_compare.normalized_outputs(b, 'b'*64)
    path = b / 'clef/results/_t0/clef/r1/server.jsonl'; path.write_bytes(b'{"latency_ms":2}\n')
    assert left != t0_compare.normalized_outputs(b, 'b'*64)
    with pytest.raises(ValueError, match='source code'):
        t0_compare.normalized_outputs(a, 'wrong')
    path = a / 'clef/results/_t0/clef/r1/t0.json'
    write_json(path, dict(status='PASS', fingerprint_sha256='bad'))
    with pytest.raises(ValueError, match='fingerprint link'):
        t0_compare.normalized_outputs(a, 'a'*64)


def test_scratch_cannot_be_existing_or_inside_source(tmp_path):
    with pytest.raises(ValueError, match='scratch'):
        t0_compare.compare(tmp_path, tmp_path, tmp_path / 'new')
