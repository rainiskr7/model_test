"""R4 contracts captured by executing original blocks on synthetic inputs."""
import shared.agent.scoring.cache_diagnostics as subject


def test_reachable_unknown_identity():
    result = {'bucket': 'unclassified', 'fixture_key': None, 'cache_miss': True}
    actual = subject._classify_reachable('Unknown', {'x': 1}, [{'key': 'a', 'args': {'x': 2}}], result=result)
    assert actual == {'bucket': 'unclassified', 'fixture_key': None, 'cache_miss': True}


def test_reachable_semantic_order():
    result = {'bucket': 'unclassified', 'fixture_key': None, 'cache_miss': True}
    actual = subject._classify_reachable('StockPrice_kis', {'symbol': 'ABC', 'extra': 1}, [{'key': key, 'args': {'symbol': 'ABC', 'extra': 2}} for key in ['z', 'a']], result=result)
    assert actual == {'bucket': 'semantic_mismatch', 'fixture_key': 'a', 'cache_miss': True}
