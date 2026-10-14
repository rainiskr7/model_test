"""Agent whole-runner request and persistence anchors, with no live services.

Variable keys: L1.json metadata.timestamp (ISO datetime); execution_time and
metadata total_execution_time/average_execution_time/average_tps are elapsed-time
fields, but this fixture supplies fixed durations and asserts them as well.
All other values, including completion latency, are fixed. No real .env is loaded.
"""
import ast
import copy
from datetime import datetime
import importlib.util
import os
from pathlib import Path
import shlex
import sys
from types import ModuleType, SimpleNamespace

import pytest

from shared.agent.tests._agent_fakes import CUSTOM, load_runner
from shared.multimodal.tests._runner_fakes import CONSTRAINTS, offline_guard, read_json

MODEL = 'test/model-a:1'
BASE_URL = 'http://unused.invalid/v1/chat/completions'
DATASET = [
    {'task_id': 'ok', 'instruction': '서울 검색', 'task_level': 1, 'task_category': '검색',
     'golden_action': [{'tool': 'Search', 'arguments': {'query': '서울'}}],
     'available_tools': ['Distractor', 'Search'], 'fallback_options': [{'tool': 'Fallback'}],
     'resp_schema': {'answer': 'str'}, 'arg_schema': {'query': 'str'},
     'golden_fields': ['answer'], 'minimum_steps': 1, 'data_flow': [{'from': 'Search'}],
     'error_injection': {'once': True}, 'long_term_tests': ['기억']},
    {'task_id': 'false', 'instruction': '실패 결과', 'task_level': 2,
     'conversation_tracking': {'turns': [{'role': 'user', 'content': '질문',
                                         'actions': [{'tool': 'Search'}]}],
                               'evaluation_context': {'context_tests': ['문맥']}}},
    {'task_id': 'raises', 'instruction': '두 번째 반복 예외'},
]
EXPECTED_TASKS = [
    {'id': 'ok', 'description': '서울 검색', 'expected_output': {'answer': 'str'},
     'available_tools': ['Search', 'Distractor', 'Fallback'],
     'tools': ['Search', 'Distractor', 'Fallback'], 'expected_tools': ['Search'],
     'level': 1, 'category': '검색',
     'golden_action': [{'tool': 'Search', 'arguments': {'query': '서울'}}],
     'golden_fields': ['answer'], 'context_tests': [], 'long_term_tests': ['기억'],
     'conversation_tracking': None, 'arg_schema': {'query': 'str'}, 'minimum_steps': 1,
     'data_flow': [{'from': 'Search'}], 'error_injection': {'once': True},
     'fallback_options': [{'tool': 'Fallback'}]},
    {'id': 'false', 'description': '실패 결과', 'expected_output': {},
     'available_tools': ['Search'], 'tools': ['Search'], 'expected_tools': ['Search'],
     'level': 2, 'category': 'unknown', 'golden_action': [], 'golden_fields': [],
     'context_tests': ['문맥'], 'long_term_tests': [],
     'conversation_tracking': {'turns': [{'role': 'user', 'content': '질문',
                                         'actions': [{'tool': 'Search'}]}],
                               'evaluation_context': {'context_tests': ['문맥']}},
     'arg_schema': {}, 'minimum_steps': None, 'data_flow': [], 'error_injection': None,
     'fallback_options': []},
    {'id': 'raises', 'description': '두 번째 반복 예외', 'expected_output': {},
     'available_tools': [], 'tools': [], 'expected_tools': [], 'level': 0,
     'category': 'unknown', 'golden_action': [], 'golden_fields': [], 'context_tests': [],
     'long_term_tests': [], 'conversation_tracking': None, 'arg_schema': {},
     'minimum_steps': None, 'data_flow': [], 'error_injection': None, 'fallback_options': []},
]


@pytest.fixture
def runner(monkeypatch, tmp_path):
    offline_guard(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('MODEL_TEST_BASE', str(tmp_path))
    monkeypatch.setenv('EVAL_TIMESTAMP', 's1-session')
    for key in tuple(os.environ):
        if key.startswith('SERVING_') or key in ('AGENT_NATIVE_TOOL_CALLING', 'OPENAI_API_KEY'):
            monkeypatch.delenv(key)
    # main may write this key; track restoration even when initially absent.
    monkeypatch.setenv('OPENAI_API_KEY', 'fixture-key')
    return load_runner(monkeypatch, tmp_path)


def test_conversion_contract(runner):
    source = copy.deepcopy(DATASET)
    assert runner.convert_dataset_to_tasks(source) == EXPECTED_TASKS
    assert source == DATASET


def task_result(task, rep):
    return {
        'success': task['id'] == 'ok' and rep == 0,
        'execution_time': 2, 'steps_taken': 1,
        'error': None if task['id'] == 'ok' else 'synthetic unsuccessful result',
        'tool_invocations': [],
        'token_usage': {'prompt_tokens': 3, 'completion_tokens': 5, 'total_tokens': 8},
        'ttft_stats': {'average': 0.5, 'min': 0.25, 'max': 0.75, 'count': 2},
        'tool_calls': [{'step': 1, 'tool_name': 'Search', 'arguments': {'query': '서울'},
                        'success': True, 'result': {'answer': '서울'}, 'discard_me': True}],
        'result': {'final_response': '첫 응답' if rep == 0 else '둘째 응답',
                   'conversation': [{'role': 'user', 'content': task['description']},
                                    {'role': 'tool', 'tool_call_id': 'call-1', 'content': '{"값": 1}'}],
                   'steps': [{'llm_response': {'finish_reason': 'length'}}]},
    }


def install_execution_fakes(monkeypatch, runner):
    state = SimpleNamespace(adapters=[], adapter_calls=[], runner_calls=[], calls=[], seed_writes=[], returned=[])

    class Adapter:
        def __init__(self, model, **kwargs):
            state.adapter_calls.append((model, copy.deepcopy(kwargs)))
            self.__dict__.update(seed=kwargs.get('seed'), temperature=kwargs.get('temperature', 0),
                                 timeout=kwargs['timeout'], max_tokens=kwargs['max_tokens'],
                                 unparsed_tool_call_candidates=3, openai_sdk_version='fixture', sdk_max_retries=0)
            state.adapters.append(self)

        def __setattr__(self, name, value):
            if name == 'seed':
                state.seed_writes.append(value)
            super().__setattr__(name, value)

    class Runner:
        def __init__(self, adapter, registry, **kwargs):
            state.runner_calls.append((adapter, registry, kwargs))
            self.adapter = adapter
            self.timeout = kwargs['timeout']
            self.max_retries = kwargs['max_retries']
            self.reps = {}

        def run_task(self, task):
            rep = self.reps.get(task['id'], 0)
            self.reps[task['id']] = rep + 1
            state.calls.append((copy.deepcopy(task), self.adapter.seed))
            if task['id'] == 'raises' and rep == 1:
                raise RuntimeError('synthetic task failure')
            result = task_result(task, rep)
            state.returned.append(result)  # main must mutate the original dict.
            return result

    monkeypatch.setattr(runner, 'OpenAICompatAdapter', Adapter)
    monkeypatch.setattr(runner, 'BenchmarkRunner', Runner)
    return state


def expected_saved_task(index):
    task = EXPECTED_TASKS[index]
    failed = index == 2
    return {
        'task_id': task['id'], 'instruction': task['description'], 'level': task['level'],
        'category': task['category'], 'success': index == 0,
        'execution_time': 0 if failed else 2, 'steps_taken': 0 if failed else 1,
        'error': [None, 'synthetic unsuccessful result', 'synthetic task failure'][index],
        'expected_tools': task['expected_tools'], 'exposed_tools': task['available_tools'],
        'golden_action': task['golden_action'], 'golden_fields': task['golden_fields'],
        'context_tests': task['context_tests'], 'long_term_tests': task['long_term_tests'],
        'minimum_steps': task['minimum_steps'], 'data_flow': task['data_flow'],
        'error_injection': task['error_injection'], 'fallback_options': task['fallback_options'],
        'resp_schema': task['expected_output'], 'arg_schema': task['arg_schema'],
        'repetitions': 2, 'repetition_results': [index == 0, False],
        'token_usage': {'prompt_tokens': 0 if failed else 3, 'completion_tokens': 0 if failed else 5,
                        'total_tokens': 0 if failed else 8},
        'completion_latency': {'average': 0 if failed else 0.5, 'min': 0 if failed else 0.25,
                               'max': 0 if failed else 0.75, 'count': 0 if failed else 2, 'unit': 'seconds'},
        'last_finish_reason': None if failed else 'length', 'length_finish_reason_count': 0 if failed else 1,
        'tool_calls': [] if failed else [
            {'step': 1, 'tool_name': 'Search', 'arguments': {'query': '서울'}, 'success': True,
             'error': None, 'result': {'answer': '서울'}}],
        'final_response': None if failed else '첫 응답',
        'conversation_log': {'total_messages': 0 if failed else 2, 'messages': [] if failed else [
            {'role': 'user', 'content': task['description']},
            {'role': 'tool', 'tool_call_id': 'call-1', 'content': {'값': 1}}]},
    }


@pytest.mark.parametrize('temperature', [0.0, 0.7])
def test_main_requests_repetitions_storage_stdout_and_rc(runner, monkeypatch, tmp_path, capsys, temperature):
    state = install_execution_fakes(monkeypatch, runner)
    loads, cache_modes, resolutions = [], [], []

    def load(path):
        loads.append(path)
        return {'L1': copy.deepcopy(DATASET)}

    monkeypatch.setattr(runner, 'load_benchmark_datasets', load)
    monkeypatch.setattr(runner, 'set_cache_mode', cache_modes.append)
    monkeypatch.setattr(runner, 'resolve_tool_classes', lambda names: resolutions.append(names) or [])
    monkeypatch.setattr(sys, 'argv', [runner.__file__, '--model', MODEL, '--base_url', BASE_URL,
                                    '--timeout', '20', '--request-timeout', '4', '--max-retries', '3',
                                    '--max-steps', '5', '--repetitions', '2', '--temperature', str(temperature),
                                    '--native-tool-calling', '--full-rollout'])
    # No integer return at end of main: sys.exit(None) is process rc 0, even on failed tasks.
    rc = runner.main()
    assert rc is None
    with pytest.raises(SystemExit) as exited:
        sys.exit(rc)
    assert exited.value.code is None
    assert loads == ['bench/tasks']
    assert cache_modes == ['read']
    assert resolutions == [['Search', 'Distractor', 'Fallback']]
    assert state.adapter_calls == [(MODEL, {
        'effort': 'low', 'max_completion_tokens': 1024, 'base_url': BASE_URL,
        'native_tool_calling': True, 'max_tokens': 16384, 'temperature': temperature, 'timeout': 4,
    })]  # main does not pass seed, api_key, or local-inference options.
    assert len(state.runner_calls) == 1
    adapter, registry, kwargs = state.runner_calls[0]
    assert adapter is state.adapters[0]
    assert registry.get_available_tools() == []
    assert kwargs == dict(max_steps=5, timeout=20, max_retries=3, multiturn_mode='full_rollout')
    seeds = [1000, 1001] * 3 if temperature > 0 else [None] * 6
    assert state.calls == [(task, seeds[i * 2 + rep]) for i, task in enumerate(EXPECTED_TASKS) for rep in range(2)]
    assert state.seed_writes == ([1000, 1001] * 3 if temperature > 0 else [])
    assert adapter.seed == (1001 if temperature > 0 else None)
    assert state.returned[0]['task_id'] == 'ok'
    assert state.returned[0]['repetition_results'] == [True, False]
    assert 'task_id' not in state.returned[1]
    assert 'task_id' not in state.returned[-1]  # exception on rep 2 discards rep 1.
    output = tmp_path / 'results/test_model_a_1/s1-session/language/agent/L1.json'
    assert [p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob('*') if p.is_file()] == [
        'results/test_model_a_1/s1-session/language/agent/L1.json',
    ]
    saved = read_json(output)
    stamp = saved['metadata'].pop('timestamp')
    assert isinstance(datetime.fromisoformat(stamp), datetime)
    decoding = dict(temperature=0.0, max_tokens=16384, seed=None)
    assert saved == {
        'metadata': {
            'model': MODEL, 'level': 'L1', 'native_tool_calling': True, 'unparsed_tool_call_candidates': 3,
            'request_timeout': 4, 'task_timeout': 20, 'max_tokens': 16384,
            # Current provenance always defaults temperature to 0, even when request is 0.7.
            'decoding': dict(available=True, requested=decoding, effective=decoding,
                             constraints=CONSTRAINTS, sampling_controls_removed=False),
            'max_retries': 3, 'openai_sdk_version': 'fixture', 'sdk_max_retries': 0,
            'total_tasks': 3, 'successful_tasks': 1, 'failed_tasks': 2, 'success_rate': 33.33,
            'total_execution_time': 4, 'average_execution_time': 1.33, 'total_steps': 2,
            'average_steps': 0.67, 'total_tool_calls': 2, 'average_tool_calls': 0.67,
            'total_tokens': 16, 'average_tokens_per_task': 5.33, 'average_prompt_tokens': 2.0,
            'average_completion_tokens': 3.33, 'average_tps': 4.0,
            'completion_latency': dict(average=0.5, min=0.5, max=0.5, unit='seconds'),
            'tasks_with_length_finish_reason': 2,
        },
        'tool_usage_statistics': {'Search': dict(count=2, success=2, failure=0)},
        'results': [expected_saved_task(i) for i in range(3)],
    }
    captured = capsys.readouterr()
    assert captured.err == ''
    lines = captured.out.splitlines()
    for line in ('Cache mode: read', 'Multi-turn mode: full_rollout', f'Selected model: {MODEL}',
                 'Running Benchmark: L1 (3 tasks)', 'Task 1/3: ok', 'Task 2/3: false', 'Task 3/3: raises',
                 '[RESULT] Success: True', '[RESULT] Success: False', '  Pass@2: 1/2 (50.0%)',
                 '  Pass@2: 0/2 (0.0%)', '[ERROR] Execution failed: synthetic task failure',
                 f'Results saved to: {output}', 'OVERALL SUMMARY', 'L1: 1/3 tasks successful (33.3%)'):
        assert line in lines
    assert lines.count('[Repetition 1/2]') == 3
    assert lines.count('[Repetition 2/2]') == 3
    assert '[ERROR] Failed to save results:' not in captured.out


def test_explicit_seed_with_zero_temperature_is_unchanged(runner, monkeypatch, tmp_path):
    state = install_execution_fakes(monkeypatch, runner)
    results = runner.run_benchmark_on_dataset(
        'L1', DATASET[:1], MODEL, timeout=20, repetitions=2, save_logs=False,
        request_timeout=4, max_tokens=37, base_url=BASE_URL, temperature=0.0, seed=19,
    )
    assert state.adapter_calls == [(MODEL, dict(max_tokens=37, base_url=BASE_URL, temperature=0.0, seed=19, timeout=4))]
    assert state.calls == [(EXPECTED_TASKS[0], 19), (EXPECTED_TASKS[0], 19)]
    assert state.seed_writes == []
    assert results[0]['repetition_results'] == [True, False]
    assert not list(tmp_path.rglob('*.json'))


def copied_python_modules(script):
    modules = set()
    for line in script.read_text().replace('\\\n', ' ').splitlines():
        words = shlex.split(line, comments=True)
        if words and words[0] == 'cp':
            for word in words[1:]:
                if '/gpustack_custom/' in word and word.endswith('.py'):
                    modules.add(Path(word).stem)
    return modules


def local_imports(path):
    imports = set()
    for node in ast.walk(ast.parse(path.read_text())):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or '', *(alias.name for alias in node.names)]
        for name in names:
            # Both top-level runner imports and relative adapter imports are copied.
            candidate = name.rsplit('.', 1)[-1]
            if (CUSTOM / f'{candidate}.py').is_file():
                imports.add(candidate)
    return imports


@pytest.mark.parametrize('script', ['run_gpustack_custom.sh', 'run_gpustack_passk.sh'])
def test_shell_copy_lists_cover_local_import_closure(script):
    required = {'run_gpustack_benchmark_with_logging', 'openai_compat_adapter'}
    pending = list(required)
    while pending:
        for dependency in local_imports(CUSTOM / f'{pending.pop()}.py') - required:
            required.add(dependency)
            pending.append(dependency)
    assert {'runner_timeout_config', 'result_observability', 'tool_call_parser'} <= required
    copied = copied_python_modules(CUSTOM.parent / script)
    assert required <= copied, f'{script}: missing copied modules {sorted(required - copied)}'


def fresh_adapter(monkeypatch):
    """Import the whole adapter under an isolated package, retaining its local parser."""
    def install(name, **attrs):
        module = ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    install('s1_bench', __path__=[])
    install('s1_bench.adapters', __path__=[str(CUSTOM)])
    install('s1_bench.adapters.base_adapter', BaseAdapter=object)
    install('s1_bench.observability', observe=lambda **_: lambda function: function)
    parser_name = 's1_bench.adapters.tool_call_parser'
    parser_spec = importlib.util.spec_from_file_location(parser_name, CUSTOM / 'tool_call_parser.py')
    parser = importlib.util.module_from_spec(parser_spec)
    monkeypatch.setitem(sys.modules, parser_name, parser)
    parser_spec.loader.exec_module(parser)
    name = 's1_bench.adapters.openai_compat_adapter'
    spec = importlib.util.spec_from_file_location(name, CUSTOM / 'openai_compat_adapter.py')
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('fake_base,serving_env', [(True, True), (False, False), (False, True)])
def test_adapter_import_selects_constraints(monkeypatch, tmp_path, capsys, fake_base, serving_env):
    offline_guard(monkeypatch)
    for key in tuple(os.environ):
        if key.startswith('SERVING_') or key == 'MODEL_TEST_BASE':
            monkeypatch.delenv(key)
    # Restore both sys.path and cached package attributes when this isolated import ends.
    monkeypatch.syspath_prepend(str(tmp_path))
    for name in tuple(sys.modules):
        if name == 'serving' or name.startswith('serving.') or name.startswith('s1_bench.'):
            monkeypatch.delitem(sys.modules, name)
    for name in ('serving', 'serving.constraints'):
        # Track initially absent entries too: imports below must not leak fake apply.
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
        monkeypatch.delitem(sys.modules, name)
    if serving_env:
        monkeypatch.setenv('SERVING_MAX_OUTPUT_TOKENS', '3')
    if fake_base:
        directory = tmp_path / 'shared/serving'
        directory.mkdir(parents=True)
        (directory / '__init__.py').write_text('')
        (directory / 'constraints.py').write_text(
            'calls = []\ndef apply(payload, *, sdk=False):\n'
            '    calls.append((dict(payload), sdk))\n'
            '    payload["selected_fixture"] = True\n    return payload\n')
        monkeypatch.setenv('MODEL_TEST_BASE', str(tmp_path))
    module = fresh_adapter(monkeypatch)
    payload = {'temperature': 0.7, 'max_tokens': 37}
    assert module.apply_serving_constraints(payload, sdk=True) is payload
    if fake_base:
        chosen = sys.modules['serving.constraints']
        assert module.apply_serving_constraints is chosen.apply
        assert Path(chosen.__file__) == tmp_path / 'shared/serving/constraints.py'
        assert chosen.calls == [({'temperature': 0.7, 'max_tokens': 37}, True)]
        assert payload == {'temperature': 0.7, 'max_tokens': 37, 'selected_fixture': True}
    else:
        assert module.apply_serving_constraints.__name__ == '_noop'
        assert payload == {'temperature': 0.7, 'max_tokens': 37}
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == (
        '[adapter] 경고: SERVING_* env 가 설정됐는데 shared/serving 을 못 찾음 '
        '(MODEL_TEST_BASE=None). 서빙 제약이 적용되지 않는다.\n'
        if serving_env and not fake_base else '')
