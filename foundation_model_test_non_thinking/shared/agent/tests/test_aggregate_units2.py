"""R4 contracts captured by executing original blocks on synthetic inputs."""
import shared.agent.scoring.aggregate as subject


def test_retry_class_empty():
    actual = subject._l3_retry_class({'tool_calls': None, 'golden_action': {}})
    assert actual == ([], [{}], [], 'no_tool_calls_emitted')


def test_retry_class_final_and_middle():
    actual = [subject._l3_retry_class({'tool_calls': calls, 'golden_action': [1]}) for calls in [
        [{'error': 'Pseudo-API(read): cache miss'}, {}], [{}, {'error': 'Pseudo-API(read): cache miss'}], [{}, {}]]]
    assert actual == [([{'error': 'Pseudo-API(read): cache miss'}, {}], [1], [0], 'cache_miss_before_final_call'),
     ([{}, {'error': 'Pseudo-API(read): cache miss'}], [1], [1], 'cache_miss_only_at_final_call'),
     ([{}, {}], [1], [], 'no_cache_miss')]


def test_following_calls_final_miss():
    counters = dict.fromkeys(['misses_with_following_call', 'same_tool_identical_arguments', 'same_tool_different_arguments', 'different_tool'], 0)
    subject._count_following_calls([{}], [0], after_non_final_miss=counters)
    actual = counters
    assert actual == {'misses_with_following_call': 0,
     'same_tool_identical_arguments': 0,
     'same_tool_different_arguments': 0,
     'different_tool': 0}


def test_following_calls_transitions():
    counters = dict.fromkeys(['misses_with_following_call', 'same_tool_identical_arguments', 'same_tool_different_arguments', 'different_tool'], 0)
    calls = [{'tool': 'a', 'arguments': {'x': n}} for n in [1, 1, 2]] + [None, {'tool': 'b'}]
    subject._count_following_calls(calls, [0, 1, 2, 3, 4], after_non_final_miss=counters)
    actual = counters
    assert actual == {'misses_with_following_call': 4,
     'same_tool_identical_arguments': 1,
     'same_tool_different_arguments': 1,
     'different_tool': 2}
