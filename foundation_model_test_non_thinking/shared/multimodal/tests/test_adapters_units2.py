"""R4 contracts captured by executing original blocks on synthetic inputs."""
import shared.multimodal.publish.adapters as subject


def test_score_classified_kreta_disagreements():
    rows = [{'response': text, 'answer': answer, 'pred_indexs': stored, 'category': 'z'} for text, answer, stored in [('B', 'B', 'A'), ('???', 'C', 'D')]]
    values = subject._score_classified_records('kreta', [(row, subject.RecordClass.MEASURED) for row in rows], 'response', True)
    actual = (values[0], dict(values[1]), *values[2:])
    assert actual == (1, {'z': [1, 2]}, 2, 1, 1, 1)


def test_score_classified_koffvqa_no_accuracy():
    values = subject._score_classified_records('koffvqa', [({'response': 'x'}, subject.RecordClass.MEASURED), ({'category': 'a'}, subject.RecordClass.ERRORED)], 'response', False)
    actual = (values[0], dict(values[1]), *values[2:])
    assert actual == (0, {'overall': [0, 1], 'a': [0, 1]}, 0, 0, 0, 0)


def test_latency_missing_conditions():
    failures = ['existing']
    counts, raw = subject._aggregate_latency_conditions({}, {}, {'text_only'}, 2, failures=failures)
    actual = (counts, raw, failures)
    assert actual == ({'attempted': 0, 'measured': 0, 'errored': 0, 'unresolved': 0, 'correct_measured': 0},
     {},
     ['existing',
      'condition/rep 완주 조건을 충족하지 않음',
      'condition 집합이 run_config와 일치하지 않음',
      'summary condition 집합이 일치하지 않음'])


def test_latency_raw_reaggregation():
    failures = []
    rows = [{'ttft': 1.0, 'total': 2.0, 'completion_tokens': 4}, {'error': 'timeout'}]
    counts, raw = subject._aggregate_latency_conditions({'text_only': rows}, {'conditions': [{'condition': 'text_only'}]}, {'text_only'}, 2, failures=failures)
    actual = (counts, raw, failures)
    assert actual == ({'attempted': 2, 'measured': 1, 'errored': 1, 'unresolved': 0, 'correct_measured': 1},
     {'text_only': {'condition': 'text_only',
                    'reps': 2,
                    'successful': 1,
                    'failed': 1,
                    'ttft': {'p50': 1.0, 'p95': 1.0, 'p99': 1.0, 'mean': 1.0, 'n': 1},
                    'total': {'p50': 2.0, 'p95': 2.0, 'p99': 2.0, 'mean': 2.0, 'n': 1},
                    'completion_tokens': {'p50': 4.0, 'p95': 4.0, 'p99': 4.0, 'mean': 4.0, 'n': 1},
                    'tokens_per_sec': {'p50': 2.0, 'p95': 2.0, 'p99': 2.0, 'mean': 2.0, 'n': 1}}},
     ['latency 호출 실패 또는 미해결 값이 포함됨', 'runs.json 재집계와 summary condition 수치가 일치하지 않음'])
