"""R4 contracts captured by executing original blocks on synthetic inputs."""
import json
import shared.functionchat.scoring.repro as subject


def test_read_datasets_empty(tmp_path):
    actual = subject._read_run_datasets(tmp_path)
    assert actual == ({}, [], [], False)


def test_read_datasets_corruption_and_timeout(tmp_path):
    (tmp_path / 'singlecall.json').write_text(json.dumps({'metadata': {'native_tool_calling': True}, 'results': [{'item_id': 'x', 'error': 'timeout'}]}))
    (tmp_path / 'dialog.json').write_text('{')
    actual = subject._read_run_datasets(tmp_path)
    assert actual == ({}, ['dialog.json: JSONDecodeError'], [{'native_tool_calling': True}], True)


def test_removed_sampling_unknown():
    actual = subject._removed_sampling_controls([{}, {"decoding": {"available": False}}])
    assert actual == ([], [], None)


def test_removed_sampling_union():
    actual = subject._removed_sampling_controls([{'decoding': {'available': True, 'constraints': {'removed_parameters': params}}} for params in [['seed'], ['temperature', 'seed']]])
    assert actual == ([frozenset({'seed'}), frozenset({'temperature', 'seed'})], ['seed', 'temperature'], True)
