"""Adapter helper expectations recorded by executing the original adapters."""
import hashlib
import json
from shared.multimodal.publish import adapters


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()


def test_kreta_protocol_known_and_unknown_modes():
    assert _digest(adapters._kreta_protocol({}, 'direct', None, [])) == EXPECTED_DIRECT_HASH
    assert _digest(adapters._kreta_protocol({}, 'unknown', None, [])) == EXPECTED_UNKNOWN_HASH


def test_judge_protocol_end_to_end_and_rejudge():
    summary = {'judge_model': 'judge', 'judge_prompt_version': 'v1', 'judge_prompt_template_sha256': 'prompt'}
    for rejudge, expected in [(False, EXPECTED_JUDGE_HASH), (True, EXPECTED_REJUDGE_HASH)]:
        protocol = adapters._judge_protocol(summary, {}, 'sha', None, rejudge, None)
        assert _digest(protocol) == expected


def test_aggregate_judge_rows_rejects_bool_and_preserves_failure_order():
    failures = ['existing']
    counts, scores, item_digest, average = adapters._aggregate_judge_rows(
        [{'dataset_item_id': 'a', 'score': 8}, {'score': True}, {'dataset_item_id': 'a', 'error': 'failed'}],
        {'scored': 1, 'avg_score': 8}, failures,
    )
    assert counts == {'attempted': 3, 'measured': 1, 'errored': 1, 'unresolved': 1, 'correct_measured': 1}
    assert (scores, item_digest, average) == ([8], None, 8.0)
    assert failures == EXPECTED_JUDGE_FAILURES


def test_read_kreta_keeps_rows_before_parse_error(tmp_path):
    path = tmp_path / 'model_direct.jsonl'
    path.write_text('{"id": 1}\n[]\n{"id": 2}\n')
    failures = []
    assert adapters._read_kreta_rows(path, failures) == [{'id': 1}]
    assert failures == ['JSONL 읽기 실패: ValueError']


def test_upstream_comparison_warns_for_multiple_sources(tmp_path):
    path = tmp_path / 'model_direct.jsonl'
    summary = tmp_path / 'summary.json'
    summary.write_text(json.dumps({'model_direct': {'overall_accuracy': 0.5}, 'other': {}}))
    warnings = []
    assert adapters._kreta_upstream_accuracy(path, summary, warnings) == 0.5
    assert warnings == ['상류 results.json에 다른 source key가 함께 있음 — 채점에는 사용하지 않음']


# Captured from the unmodified A2 input using the synthetic cases above.
EXPECTED_DIRECT_HASH = '8bba056105a541dbb647fb0cfcfdbc23233dcae8f282288d537ea93bd8ed0e9d'
EXPECTED_UNKNOWN_HASH = '5ddacc1f07d8159537a1857f473e3c5000570a2610afa8e17c4320378473f491'
EXPECTED_JUDGE_HASH = 'd5aaa4b3c491daa5271051d6f1b8580a030bc93b244b39f16275bbfcd192abc7'
EXPECTED_REJUDGE_HASH = '06f8f3ce7134c07cf5b58c55a7b0a539eb4b3fe266d563962b4c091d2d0f59ac'
EXPECTED_JUDGE_FAILURES = ['existing',
 'judge row dataset_item_id가 누락됨',
 '기대 건수 275와 다름',
 'judge 오류가 포함됨',
 '0~10 정수 아닌 judge 점수가 포함됨',
 'judge dataset item key가 누락되었거나 중복됨']
