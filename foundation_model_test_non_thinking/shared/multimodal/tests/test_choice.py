"""Expected answers captured by executing the original extractor before moving."""
import pytest

from shared.multimodal.benches.choice import extract_choice


@pytest.mark.parametrize('response,expected', [
    ('  B', 'B'),
    ('(C)', 'C'),
    ('d', 'D'),
    ('설명 속 B 선택지', 'B'),
    ('', ''),
    ('(A) 또는 정답: C', 'C'),
])
def test_extract_choice(response, expected):
    assert extract_choice(response) == expected
