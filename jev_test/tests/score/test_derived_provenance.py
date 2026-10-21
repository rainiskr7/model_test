"""무엇: 파생 출처 순수 검사 시험 · 입력: 합성 marker/final/원천 · 출력: 연결/거부 · 계약 §7-6·9c."""

from dataclasses import replace
import pytest

from jeveval.score import derived_provenance as provenance
from jeveval.types import FinalRecord
from tests.types.samples import call


@pytest.mark.parametrize('origin', ['results/m/r/A/kosgd/full', '../m/r/A/kosgd/full',
                                  'results/other/r/A/kosgd/full', None])
def test_marker_and_final_origin_match_identity(origin):
    fp = dict(model='m', run_id='r', set='kosgd')
    final = FinalRecord('s:g:i', 'ok', None, False, [], [call()], origin)
    marker = None if origin is None else dict(derived_from=origin)
    if origin is None or origin == 'results/m/r/A/kosgd/full':
        assert provenance.check_derived_origin([final], marker, fp) == origin
    else:
        with pytest.raises(ValueError): provenance.check_derived_origin([final], marker, fp)
    with pytest.raises(ValueError, match='derived provenance differs'):
        provenance.check_derived_origin([replace(final, derived_from='different')], marker, fp)


@pytest.mark.parametrize('attack', ['none', 'hash', 'duplicate_final', 'duplicate_call', 'empty', 'derived_source'])
def test_source_calls_are_matching_unique_subset(attack):
    original = FinalRecord('s:g:i', 'ok', None, False, [], [call()])
    final = replace(original, derived_from='results/m/r/A/kosgd/full')
    if attack == 'hash': final = replace(final, calls=[replace(call(), request_sha256='b'*64)])
    elif attack == 'duplicate_call': final = replace(final, calls=[call(), call()])
    elif attack == 'empty': final = replace(final, calls=[])
    elif attack == 'derived_source': original = replace(original, derived_from='other')
    finals = [final, final] if attack == 'duplicate_final' else [final]
    assert provenance.source_calls_match(finals, [original]) == (attack == 'none')


@pytest.mark.parametrize('field', ['model', 'set', 'run_id', 'variant'])
def test_full_source_identity_must_match(field):
    fp = dict(model='m', run_id='r', set='kosgd', variant='actions_only')
    source = dict(fp, variant='full')
    assert provenance.source_identity_matches(fp, source)
    source[field] = 'other'
    assert not provenance.source_identity_matches(fp, source)
