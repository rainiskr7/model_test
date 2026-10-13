"""R4 contracts captured by executing original blocks on synthetic inputs."""
import shared.multimodal.publish.report as subject


def test_spread_fraction_boundary():
    actual = subject._repro_spread([{'numerator': 100}, {'numerator': 102}], 'fraction', 101)
    assert actual == ([100.0, 102.0], 2.0, 2, True, 1.9801980198019802)


def test_spread_judge_rounding():
    actual = subject._repro_spread([{'value': 8.0}, {'value': 8.1}], 'score_0_10', 10)
    assert actual == ([8.0, 8.1], 0.09999999999999964, 0.1, True, 0.9999999999999964)


def test_render_ambiguities_empty():
    actual = ['existing']
    subject._render_ambiguities([], out=actual)
    assert actual == ['existing']


def test_render_ambiguities_folded():
    actual = ['existing']
    subject._render_ambiguities([{'key': ('K|x', 'v', 'fp', 'm'), 'reason': 'tie', 'candidates': [{'source': {'unit': 'u'}}], 'folded_duplicates': [{'kept': 'u', 'folded': ['copy']}]}], out=actual)
    assert actual == ['existing',
     '',
     '## 대표 런 자동 선정 불가 — 수치 비노출',
     '',
     '- **K\\|x / v / m** — tie',
     '  - `u`',
     '  - 동일 artifact role/SHA-256·측정 payload 복사본 접음; 유지: `u`',
     '    - 접음: `copy`']
