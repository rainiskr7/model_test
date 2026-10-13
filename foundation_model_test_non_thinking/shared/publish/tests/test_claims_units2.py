"""R4 contracts captured by executing original blocks on synthetic inputs."""
import shared.publish.claims as subject


def test_instability_identical():
    actual = subject._instability_budget({'a', 'b'}, [{'a'}, {'a'}, {'a'}], [1, 1, 1], 3)
    assert actual == ({'a'}, [], 1, [1, 1])


def test_instability_same_count_different_items():
    actual = subject._instability_budget({'a', 'b'}, [{'a'}, {'b'}, {'a'}], [1, 1, 1], 3)
    assert actual == (set(), ['a', 'b'], 1, [-1, 3])
