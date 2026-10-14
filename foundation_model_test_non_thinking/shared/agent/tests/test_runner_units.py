"""Pure runner helper contracts from legacy synthetic task/results.

No variable fields: times and counters are explicit; no datasets or live results.
"""
import copy
import json
from types import SimpleNamespace

import pytest

from _agent_fakes import load_runner
from shared.multimodal.tests._runner_fakes import offline_guard


@pytest.fixture
def runner(monkeypatch, tmp_path):
    offline_guard(monkeypatch)
    return load_runner(monkeypatch, tmp_path)


def test_golden_tools_order_and_duplicates(runner):
    source = {'golden_action': [{'tool': 'B'}, {}, {'tool': 'A'}, {'tool': 'B'}]}
    before = copy.deepcopy(source)
    assert runner.golden_tools(source) == ['B', 'A']
    assert source == before
    assert runner.golden_tools({}) == []


def test_conversation_tools_action_forms_and_input_isolation(runner):
    tools = ['A']
    task = {'conversation_tracking': {'turns': [
        {'actions': [{'tool': 'B'}, {'tool': 'A'}], 'action': {'tool': 'C'}},
        {'action': {'tool': 'B'}}, {'actions': [{}]}]}}
    before = copy.deepcopy(task)
    assert list(runner.conversation_tools(task, tools)) == [('actions', 'B'), ('action', 'C')]
    assert task == before
    assert tools == ['A']


def test_conversation_tools_preserves_lazy_failure_and_debug_stdout(runner, capsys):
    source = {'task_id': 'bad', 'conversation_tracking': {
        'turns': [{'action': {'tool': 'A'}}, None]}}
    with pytest.raises(TypeError):
        runner.convert_dataset_to_tasks([source])
    assert capsys.readouterr().out == (
        '[DEBUG] Processing conversation_tracking for task: bad\n'
        '  [OK] Found tool in turn.action: A\n')


def test_exposed_tools_keeps_distractors_and_skips_invalid_fallbacks(runner):
    expected = ['A']
    task = {'available_tools': ['B', '', 'A'],
            'fallback_options': [None, 'invalid', {'tool': 'C'}, {'tool': 'B'}]}
    assert runner.exposed_tools_for_task(task, expected) == ['A', 'B', 'C']
    assert expected == ['A']
    assert runner.exposed_tools_for_task({}, []) == []


def test_convert_task_defaults_order_and_aliases(runner):
    expected, exposed = ['A'], ['A', 'B']
    task = runner.convert_task({}, expected, exposed)
    assert task == {
        'id': 'unknown', 'description': '', 'expected_output': {},
        'available_tools': ['A', 'B'], 'tools': ['A', 'B'], 'expected_tools': ['A'],
        'level': 0, 'category': 'unknown', 'golden_action': [], 'golden_fields': [],
        'context_tests': [], 'long_term_tests': [], 'conversation_tracking': None,
        'arg_schema': {}, 'minimum_steps': None, 'data_flow': [], 'error_injection': None,
        'fallback_options': []}
    assert list(task) == ['id', 'description', 'expected_output', 'available_tools', 'tools',
                          'expected_tools', 'level', 'category', 'golden_action', 'golden_fields',
                          'context_tests', 'long_term_tests', 'conversation_tracking', 'arg_schema',
                          'minimum_steps', 'data_flow', 'error_injection', 'fallback_options']
    assert task['available_tools'] is task['tools'] is exposed
    assert task['expected_tools'] is expected


def test_convert_task_retains_evaluation_context(runner):
    tracking = {'evaluation_context': {'context_tests': ['기억']}}
    assert runner.convert_task({'conversation_tracking': tracking}, [], [])['context_tests'] == ['기억']
    with pytest.raises(AttributeError):
        runner.convert_task({'conversation_tracking': ['invalid']}, [], [])


def test_required_tools_order_and_legacy_invalid_fallback(runner):
    assert runner.required_tools([
        {'available_tools': ['B', 'A', 'B'], 'fallback_options': [{'tool': 'C'}]},
        {'available_tools': ['C', 'D'], 'fallback_options': [{'tool': 'A'}, {}]}]) == ['B', 'A', 'C', 'D']
    with pytest.raises(AttributeError):
        runner.required_tools([{'fallback_options': [None]}])


def test_result_fields_defaults_and_insertion_order(runner):
    fields = runner.result_fields({})
    assert fields == {
        'task_id': 'unknown', 'instruction': '', 'level': 0, 'category': 'unknown',
        'success': False, 'execution_time': 0, 'steps_taken': 0, 'error': None,
        'expected_tools': [], 'exposed_tools': [], 'golden_action': [], 'golden_fields': [],
        'context_tests': [], 'long_term_tests': [], 'minimum_steps': None, 'data_flow': [],
        'error_injection': None, 'fallback_options': [], 'resp_schema': {}, 'arg_schema': {},
        'repetitions': 1, 'repetition_results': []}
    assert list(fields) == ['task_id', 'instruction', 'level', 'category', 'success',
                            'execution_time', 'steps_taken', 'error', 'expected_tools',
                            'exposed_tools', 'golden_action', 'golden_fields', 'context_tests',
                            'long_term_tests', 'minimum_steps', 'data_flow', 'error_injection',
                            'fallback_options', 'resp_schema', 'arg_schema', 'repetitions',
                            'repetition_results']


def test_token_usage_fields_defaults_and_explicit_none(runner):
    assert runner.token_usage_fields({}) == {
        'token_usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}}
    assert runner.token_usage_fields({'token_usage': None}) == {'token_usage': None}
    usage = {'total_tokens': 7}
    assert runner.token_usage_fields({'token_usage': usage})['token_usage'] is usage


def test_simplified_tool_calls_results_and_key_order(runner):
    calls = runner.simplified_tool_calls({'tool_calls': [
        {'success': True, 'result': {'답': 1}}, {'success': False, 'result': {'답': 2}},
        {'success': True, 'result': {}}]})
    assert calls == [
        {'step': None, 'tool_name': None, 'arguments': None, 'success': True,
         'error': None, 'result': {'답': 1}},
        {'step': None, 'tool_name': None, 'arguments': None, 'success': False, 'error': None},
        {'step': None, 'tool_name': None, 'arguments': None, 'success': True, 'error': None}]
    assert list(calls[0]) == ['step', 'tool_name', 'arguments', 'success', 'error', 'result']
    with pytest.raises(TypeError):
        runner.simplified_tool_calls({'tool_calls': None})


def test_format_message_tool_json_and_invalid_text(runner):
    from result_observability import format_message
    assert format_message({'role': 'tool', 'tool_call_id': 'c', 'content': '{"답": 1}'}) == {
        'role': 'tool', 'tool_call_id': 'c', 'content': {'답': 1}}
    assert format_message({'role': 'tool', 'content': '{bad'}) == {
        'role': 'tool', 'tool_call_id': None, 'content': '{bad'}
    assert format_message({}) == {'role': 'unknown', 'content': ''}


def test_conversation_fields_empty_and_error(runner):
    assert runner.conversation_fields({}) == {'conversation_log': {'total_messages': 0, 'messages': []}}
    assert runner.conversation_fields({'result': {'conversation': [None]}}) == {
        'conversation_log_error': "'NoneType' object has no attribute 'get'"}


def test_final_response_truthiness_and_type_error(runner):
    assert runner.final_response({'result': {'final_response': '답'}}) == '답'
    assert runner.final_response({'result': {'final_response': ''}}) is None
    with pytest.raises(AttributeError):
        runner.final_response({'result': ['invalid']})


def test_result_statistics_rounding_and_order(runner):
    results = [{'success': True, 'execution_time': 1.234, 'steps_taken': 2,
                'tool_calls': [{}, {}], 'token_usage': {
                    'prompt_tokens': 2, 'completion_tokens': 3, 'total_tokens': 5}},
               {'success': False, 'execution_time': 0, 'steps_taken': 1}]
    expected = dict(total_tasks=2, successful_tasks=1, failed_tasks=1, success_rate=50.0,
                    total_execution_time=1.23, average_execution_time=0.62, total_steps=3,
                    average_steps=1.5, total_tool_calls=2, average_tool_calls=1.0,
                    total_tokens=5, average_tokens_per_task=2.5, average_prompt_tokens=1.0,
                    average_completion_tokens=1.5, average_tps=4.05)
    before = copy.deepcopy(results)
    actual = runner.result_statistics(results)
    assert actual == expected
    assert list(actual) == list(expected)
    assert results == before


def test_result_statistics_empty_and_invalid_usage(runner):
    assert all(value == 0 for value in runner.result_statistics([]).values())
    with pytest.raises(AttributeError):
        runner.result_statistics([{'token_usage': None}])


def test_tool_usage_statistics_counts_and_order(runner):
    source = [{'tool_calls': [{'tool_name': 'B', 'success': True},
                              {'tool_name': 'A'}, {'tool_name': 'B', 'success': False}, {}]}]
    actual = runner.tool_usage_statistics(source)
    assert actual == {'B': {'count': 2, 'success': 1, 'failure': 1},
                      'A': {'count': 1, 'success': 0, 'failure': 1},
                      'unknown': {'count': 1, 'success': 0, 'failure': 1}}
    assert list(actual) == ['B', 'A', 'unknown']
    assert runner.tool_usage_statistics([]) == {}


def test_assemble_log_data_order_and_file_bytes(runner, tmp_path):
    metadata = {'model': '한글', 'level': 'L1'}
    results = [{'task_id': 'x'}]
    payload = runner.assemble_log_data(metadata, {'total_tasks': 1}, {'latency': 0}, {}, results)
    assert list(payload) == ['metadata', 'tool_usage_statistics', 'results']
    assert list(payload['metadata']) == ['model', 'level', 'total_tasks', 'latency']
    assert metadata == {'model': '한글', 'level': 'L1'}
    assert payload['results'] is results
    path = tmp_path / 'L1.json'
    assert runner.write_result_file(path, payload) == str(path)
    assert path.read_bytes() == json.dumps(payload, indent=2, ensure_ascii=False).encode('utf-8')
    assert not path.read_bytes().endswith(b'\n')


def test_provider_ready_credentials(runner):
    assert not runner._provider_ready('no-prefix', {})
    assert not runner._provider_ready('azure/model', {'AZURE_API_KEY': 'x'})
    assert runner._provider_ready('azure/model', dict(AZURE_API_KEY='x', AZURE_API_BASE='b', AZURE_API_VERSION='v'))
    assert runner._provider_ready('openai/model', {'OPENAI_API_KEY': 'x'})
    assert not runner._provider_ready('unknown/model', {'OPENAI_API_KEY': 'x'})


def test_runtime_config_order_and_local_options(runner):
    args = SimpleNamespace(request_timeout=None, use_local=True, device='cpu', dtype='fp16',
                           quantization='4bit', tensor_parallel_size=2, gpu_memory_utilization=0.5,
                           max_model_len=2048, effort='high', max_completion_tokens=32,
                           base_url='http://unused.invalid/v1', native_tool_calling=True, temperature=0.7)
    actual = runner._build_runtime_config(args, 'vllm/test')
    expected = dict(request_timeout=None, device='cpu', dtype='fp16', quantization='4bit', tensor_parallel_size=2,
                    gpu_memory_utilization=0.5, max_model_len=2048, effort='high',
                    max_completion_tokens=32, base_url='http://unused.invalid/v1',
                    native_tool_calling=True, max_tokens=16384, temperature=0.7)
    assert actual == expected
    assert list(actual) == list(expected)


def test_execution_preserves_result_before_summary_error(runner):
    task = runner.convert_task({}, [], [])
    result = {'success': True}  # Missing execution_time fails after append, as before.
    records = []
    runner._execute_task(task, 1, SimpleNamespace(), SimpleNamespace(run_task=lambda _: result),
                         records, print=lambda *args: None)
    assert records[0] is result
    assert records[1]['error'] == "'execution_time'"
    assert records[1]['repetition_results'] == [False]
