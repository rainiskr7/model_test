"""B4 request/storage characterization, entirely offline.

Variable keys: none. perf_counter has an exhausted-checked script; metadata time,
platform, package versions and code hash are pinned. Temporary paths are explicit.
"""
import base64
import copy
from datetime import datetime, timezone
import io
import hashlib
import os
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

from _runner_fakes import (
    BASE_URL, CONSTRAINTS, MODEL, load_runner, offline_guard, read_json,
)


class ScriptClock:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return next(self.values)

    def assert_exhausted(self, calls):
        assert self.calls == calls
        assert list(self.values) == []


class StreamClient:
    def __init__(self, streams, clock=None):
        self.clock = clock
        self.clock_calls_after_chunk = []
        self.streams = iter(streams)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        entries = next(self.streams)

        def stream():
            for entry in entries:
                if isinstance(entry, Exception):
                    raise entry
                yield entry
                if self.clock is not None:
                    self.clock_calls_after_chunk.append(self.clock.calls)
        return stream()


def chunk(content=None, *, tokens=None, usage_only=False, role=None):
    return SimpleNamespace(
        choices=[] if usage_only else [SimpleNamespace(delta=SimpleNamespace(content=content, role=role))],
        usage=None if tokens is None else SimpleNamespace(completion_tokens=tokens),
    )


@pytest.fixture
def b4(monkeypatch, tmp_path):
    offline_guard(monkeypatch)
    monkeypatch.setenv('MODEL_TEST_BASE', str(tmp_path))
    monkeypatch.setenv('EVAL_TIMESTAMP', 's1-session')
    monkeypatch.chdir(tmp_path)
    for key in tuple(os.environ):
        if key.startswith('SERVING_'):
            monkeypatch.delenv(key)
    return load_runner(monkeypatch, 'b4_latency_profile')


def request(messages, *, optional=True):
    return dict(model=MODEL, messages=messages, max_tokens=37, temperature=0.25,
                stream=True, stream_options={'include_usage': True},
                **({'seed': 7, 'timeout': 4.0} if optional else {}))


def stats(value, n=1):
    return dict(p50=value, p95=value, p99=value, mean=value, n=n)


@pytest.mark.parametrize('kind,stream,record,effective', [
    ('role-first', [chunk(role='assistant'), chunk('가나')],
     dict(ttft=0.25, total=2.0, chunks=1, text_len=2, completion_tokens=None), 1),
    ('content', [chunk('가'), chunk('나다'), chunk('라')],
     dict(ttft=0.25, total=2.0, chunks=3, text_len=4, completion_tokens=None), 3),
    ('usage-only-tail', [chunk('가'), chunk('나'), chunk(tokens=8, usage_only=True)],
     dict(ttft=0.25, total=2.0, chunks=2, text_len=2, completion_tokens=8), 8),
    ('zero-usage-falls-back', [chunk('가'), chunk('나'), chunk(tokens=0, usage_only=True)],
     dict(ttft=0.25, total=2.0, chunks=2, text_len=2, completion_tokens=0), 2),
], ids=lambda value: value if isinstance(value, str) else None)
def test_chunk_timing_and_usage(b4, monkeypatch, kind, stream, record, effective):
    clock = ScriptClock([10, 10.25, 12])
    monkeypatch.setattr(b4.time, 'perf_counter', clock)
    client = StreamClient([stream], clock)
    messages = [{'role': 'user', 'content': [{'type': 'text', 'text': '요약'}]}]
    summary, runs = b4.run_condition(client, MODEL, kind, messages, 1, 37, 0.25, seed=7, timeout=4)
    assert client.calls == [request(messages)]
    assert runs == [dict(record, error=None)]
    # TTFT must be read before the next chunk is requested, including role-only.
    # A bare scripted clock alone would miss moving the read to the content chunk.
    assert client.clock_calls_after_chunk == [2] * len(stream)
    assert summary == dict(condition=kind, reps=1, successful=1, failed=0,
                           ttft=stats(0.25), total=stats(2.0),
                           completion_tokens=stats(effective), tokens_per_sec=stats(effective / 2))
    clock.assert_exhausted(3)


def test_optional_fields_absent_and_serving_noop(b4, monkeypatch):
    from client import apply_serving_constraints
    from serving.constraints import apply
    assert b4.apply_serving_constraints is apply_serving_constraints is apply
    clock = ScriptClock([10, 11, 12])
    monkeypatch.setattr(b4.time, 'perf_counter', clock)
    client = StreamClient([[chunk('답')]])
    messages = [{'role': 'user', 'content': '질문'}]
    assert b4.time_chat_stream(client, MODEL, messages, 37, 0.25) == {
        'ttft': 1, 'total': 2, 'chunks': 1, 'text_len': 1, 'completion_tokens': None,
    }
    assert client.calls == [request(messages, optional=False)]
    clock.assert_exhausted(3)


def test_percentiles_use_scripted_measurements(b4, monkeypatch):
    clock = ScriptClock([10, 11, 12, 20, 23, 26, 30, 35, 40])
    monkeypatch.setattr(b4.time, 'perf_counter', clock)
    client = StreamClient([[chunk('가', tokens=n)] for n in (4, 6, 5)])
    summary, runs = b4.run_condition(client, MODEL, 'text', [], 3, 37, 0.25)
    assert runs == [
        dict(ttft=1, total=2, chunks=1, text_len=1, completion_tokens=4, error=None),
        dict(ttft=3, total=6, chunks=1, text_len=1, completion_tokens=6, error=None),
        dict(ttft=5, total=10, chunks=1, text_len=1, completion_tokens=5, error=None),
    ]
    assert summary == {
        'condition': 'text', 'reps': 3, 'successful': 3, 'failed': 0,
        'ttft': dict(p50=3.0, p95=4.800000000000001, p99=4.960000000000001, mean=3.0, n=3),
        'total': dict(p50=6.0, p95=9.600000000000001, p99=9.920000000000002, mean=6.0, n=3),
        'completion_tokens': dict(p50=5.0, p95=5.9, p99=5.98, mean=5.0, n=3),
        'tokens_per_sec': dict(p50=1.0, p95=1.9, p99=1.98, mean=1.1666666666666667, n=3),
    }
    assert b4.percentiles([None]) == stats(None, 0)
    clock.assert_exhausted(9)


class FixedDateTime:
    @staticmethod
    def now(tz=None):
        return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


@pytest.mark.parametrize('stream_error', [False, True])
def test_main_requests_storage_stdout_and_rc(b4, monkeypatch, tmp_path, capsys, stream_error):
    metadata = sys.modules[b4.build_run_config.__module__]
    monkeypatch.setattr(metadata, 'datetime', FixedDateTime)
    monkeypatch.setattr(metadata, 'get_package_version', lambda _: 'fixture')
    monkeypatch.setattr(metadata.platform, 'platform', lambda: 'fixture-platform')
    monkeypatch.setattr(metadata, 'get_eval_script_hash', lambda _: 'a' * 32)
    names = ['text_only', 'image_256px', 'image_1024px', 'multi_image_3x512px']
    streams = [[chunk('가나'), chunk(tokens=8, usage_only=True)] for _ in names]
    values = [10, 10.25, 12] * 4
    if stream_error:
        streams[0] = [chunk('부분'), RuntimeError('synthetic stream failure')]
        values = [10, 10.25] + values[3:]
    clock = ScriptClock(values)
    monkeypatch.setattr(b4.time, 'perf_counter', clock)
    client = StreamClient(streams)
    constructors = []

    def constructor(**kwargs):
        constructors.append(kwargs)
        return client

    monkeypatch.setattr(sys.modules[b4.make_client.__module__], 'OpenAI', constructor)
    monkeypatch.setattr(sys, 'argv', [b4.__file__, '--model', MODEL, '--base-url', BASE_URL,
                                    '--api-key', 'fixture-key', '--reps', '1', '--prompt', '요약',
                                    '--max-tokens', '37', '--temperature', '0.25', '--seed', '7',
                                    '--timeout', '4'])
    assert b4.main() == (1 if stream_error else 0)
    clock.assert_exhausted(11 if stream_error else 12)
    assert constructors == [dict(base_url='http://unused.invalid/v1', api_key='fixture-key')]
    assert len(client.calls) == 4
    image_specs = [[], [(256, (128, 128, 128))], [(1024, (128, 128, 128))],
                   [(512, (200, 100, 100)), (512, (100, 200, 100)), (512, (100, 100, 200))]]
    for call, specs in zip(client.calls, image_specs):
        content = call['messages'][0]['content']
        assert content[0] == {'type': 'text', 'text': '요약'}
        assert len(content) == 1 + len(specs)
        for part, (size, color) in zip(content[1:], specs):
            assert set(part) == {'type', 'image_url'}
            assert part['type'] == 'image_url'
            assert set(part['image_url']) == {'url'}
            prefix, raw = part['image_url']['url'].split(',', 1)
            assert prefix == 'data:image/png;base64'
            with Image.open(io.BytesIO(base64.b64decode(raw, validate=True))) as img:
                assert (img.format, img.mode, img.size) == ('PNG', 'RGB', (size, size))
                assert img.getextrema() == tuple((c, c) for c in color)
        assert call == request([{'role': 'user', 'content': content}])
    output = tmp_path / 'results/test_model_a_1/s1-session/vision/customB/b4_latency_profile'
    assert {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob('*') if p.is_file()} == {
        f'{output.relative_to(tmp_path)}/{name}' for name in
        ('runs.json', 'summary.json', '_derived/publish.json', '_derived/.publish.json.lock')
    }
    assert (output / '_derived/.publish.json.lock').read_bytes() == b''
    good = dict(ttft=0.25, total=2, chunks=1, text_len=2, completion_tokens=8, error=None)
    bad = dict(ttft=None, total=None, chunks=0, text_len=0, completion_tokens=None,
               error='synthetic stream failure')
    assert read_json(output / 'runs.json') == {
        name: [bad if stream_error and i == 0 else good] for i, name in enumerate(names)
    }
    summary = read_json(output / 'summary.json')
    config = summary.pop('run_config')
    decoding = dict(temperature=0.25, max_tokens=37, seed=7)
    assert config == {
        'benchmark': 'B-4 Latency Profile', 'timestamp_utc': '2026-01-02T03:04:05+00:00',
        'model': dict(name=MODEL, safe_name='test_model_a_1'), 'endpoint': dict(base_url=BASE_URL),
        'decoding': decoding, 'decoding_requested': decoding, 'serving_constraints': CONSTRAINTS,
        'request_policy': dict(timeout=4.0, retry_max=None, retry_backoff=None),
        'dataset': dict(huggingface_id=None, revision=None, revision_source=None, git_repo=None, git_commit=None),
        'judge': dict(model=None, prompt_version=None),
        'eval_framework': dict(script_path=b4.__file__, script_hash_sha256_16='a' * 32),
        'environment': dict(python=sys.version.split()[0], platform='fixture-platform',
                            **{k: 'fixture' for k in ('openai_pkg', 'datasets_pkg', 'pillow_pkg', 'huggingface_hub_pkg')}),
        'env_vars': dict(MODEL_TEST_BASE=str(tmp_path), EVAL_TIMESTAMP='s1-session'),
        'extra': dict(reps_per_condition=1, prompt='요약', skip_multi_image=False),
    }
    conditions = []
    for i, name in enumerate(names):
        failed = stream_error and i == 0
        conditions.append(dict(condition=name, reps=1, successful=int(not failed), failed=int(failed),
                               ttft=stats(None, 0) if failed else stats(0.25),
                               total=stats(None, 0) if failed else stats(2),
                               completion_tokens=stats(0 if failed else 8),
                               tokens_per_sec=stats(None, 0) if failed else stats(4)))
    assert summary == dict(benchmark='B-4 Latency Profile', model=MODEL, conditions=conditions,
                           publish_status=dict(publishable=not stream_error,
                                               failures=['text_only: 실패 호출 포함'] if stream_error else []))
    sidecar = read_json(output / '_derived/publish.json', sidecar=True)
    axes = [
        dict(name=f'{name}:{metric}:{percentile}', unit=unit, value=value)
        for name in sorted(names) if not (stream_error and name == 'text_only')
        for metric, unit, value in [('ttft', 'seconds', 0.25), ('total', 'seconds', 2.0),
                                     ('tokens_per_sec', 'tokens/second', 4.0)]
        for percentile in ('p50', 'p95', 'p99')
    ]
    assert sidecar == {
        'aggregation_allowed': False, 'benchmark_id': 'B4-latency-profile',
        'benchmark_key': 'b4_latency_profile', 'completed_at_source': 'artifact',
        'completed_at_utc': '2026-01-02T03:04:05+00:00',
        'counts': dict(attempted=4, measured=3 if stream_error else 4,
                       correct_measured=3 if stream_error else 4, errored=int(stream_error), unresolved=0),
        'failures': ['latency 호출 실패 또는 미해결 값이 포함됨'] if stream_error else [],
        'metrics': {'axes': axes}, 'model': MODEL,
        'model_identity': dict(canonical_id=MODEL, mapped=False, serving_name=MODEL),
        'protocol': {
            'complete': False,
            'fingerprint': 'sha256:83587447f650c307e2424470f3eb86bb8ee5c9e5e7b2d4344ea2571cc67dafaa',
            'fingerprint_version': 2, 'inferred': {},
            'recorded': dict(benchmark='B4', conditions=sorted(names), max_tokens=37, prompt='요약',
                             reps_per_condition=1, seed=7, serving_constraints=CONSTRAINTS, temperature=0.25),
            'unknown': ['answer_parser_hash', 'image_preprocessing_version', 'prompt_template_hash'],
        },
        'provisional': False, 'publishable': not stream_error, 'schema_version': 1,
        'session': 's1-session', 'status': 'REJECTED' if stream_error else 'NATIVE', 'variant': 'latency',
        'source': {
            'unit': output.relative_to(tmp_path).as_posix(),
            'artifacts': [dict(path=(output / name).relative_to(tmp_path).as_posix(),
                               sha256='sha256:' + hashlib.sha256((output / name).read_bytes()).hexdigest())
                          for name in ('runs.json', 'summary.json')],
        },
        'warnings': ([] if stream_error else [
            '비교 비핵심 provenance 미기록: answer_parser_hash, image_preprocessing_version, prompt_template_hash'
        ]) + ['모델 정체성 미매핑: test/model-a:1 — 자기 이름을 canonical id로 사용'],
    }
    captured = capsys.readouterr()
    assert captured.err == ''
    assert [line for line in captured.out.splitlines() if line.startswith('[b4]')] == [
        f'[b4] model={MODEL}', f'[b4] base={tmp_path}', f'[b4] out={output}',
        *[f'[b4] === {name} (1 reps) ===' for name in names], '[b4] FINAL',
    ]
    assert captured.out.count('TTFT  P50=0.250s P95=0.250s P99=0.250s') == (3 if stream_error else 4)
    assert captured.out.count('Total P50=2.000s P95=2.000s P99=2.000s') == (3 if stream_error else 4)
    assert captured.out.count('Tok/s P50=4.0 P95=4.0') == (3 if stream_error else 4)
    assert ('(모든 호출 실패 — runs.json error 확인)' in captured.out) is stream_error
