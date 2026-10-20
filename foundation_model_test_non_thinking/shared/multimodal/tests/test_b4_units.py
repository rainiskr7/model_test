"""Extracted B4 helpers; fixed expectations, no variable metadata or live I/O."""
from types import SimpleNamespace

import pytest

from shared.multimodal.tests._runner_fakes import load_runner, offline_guard


@pytest.fixture
def b4(monkeypatch, fresh_import):
    offline_guard(monkeypatch)
    return load_runner(fresh_import, 'b4_latency_profile')


@pytest.mark.parametrize('skip', [False, True])
def test_build_conditions_keeps_image_order_and_eager_creation(b4, monkeypatch, skip):
    created = []

    def image(size, color=(128, 128, 128)):
        created.append((size, color))
        return (size, color)

    monkeypatch.setattr(b4, 'make_solid_image', image)
    monkeypatch.setattr(b4, 'make_messages', lambda prompt, images: (prompt, images))
    expected_images = [(256, (128, 128, 128)), (1024, (128, 128, 128)),
                       (512, (200, 100, 100)), (512, (100, 200, 100)),
                       (512, (100, 100, 200))]
    expected = [('text_only', ('요약', [])),
                ('image_256px', ('요약', [expected_images[0]])),
                ('image_1024px', ('요약', [expected_images[1]]))]
    if not skip:
        expected.append(('multi_image_3x512px', ('요약', expected_images[2:])))
    assert b4._build_conditions(SimpleNamespace(prompt='요약', skip_multi_image=skip)) == expected
    assert created == expected_images


def test_condition_failures_complete_and_zero_repetitions(b4):
    conditions = [('text_only', [])]
    good = [dict(condition='text_only', successful=1, failed=0)]
    assert b4._condition_failures(1, conditions, good, {'text_only': [{}]}) == []
    assert b4._condition_failures(0, [], [], {}) == ['condition rep 기대 건수가 0 이하']


def test_condition_failures_missing_and_unsuccessful(b4):
    conditions = [('text_only', [])]
    assert b4._condition_failures(1, conditions, [], {}) == [
        'condition 집합 미완주', 'text_only: rep 미완주']
    assert b4._condition_failures(1, conditions, [], {'text_only': [{}]}) == [
        'text_only: 실패 호출 포함']
