"""9-2a accuracy contracts and EXPECTED_COUNTS patch reach on synthetic sources."""

import json
from pathlib import Path

import pytest

from shared.multimodal.publish import adapters
from shared.multimodal.publish import adapters_accuracy as accuracy
from shared.multimodal.publish.schema import RecordClass


ROWS = [
    {"response": "B", "answer": "B", "pred_indexs": "A", "category": "z"},
    {"response": "???", "answer": "C", "pred_indexs": "D", "category": "z"},
    {"response": {"error": "timeout"}, "answer": "A", "category": "a"},
]


def test_score_classified_records_keeps_parser_disagreement_categories():
    classified = [(ROWS[0], RecordClass.MEASURED), (ROWS[1], RecordClass.MEASURED),
                  (ROWS[2], RecordClass.ERRORED)]
    value = accuracy._score_classified_records("kreta", classified, "response", True)
    assert (value[0], dict(value[1]), *value[2:]) == (1, {"z": [1, 2], "a": [0, 1]}, 2, 1, 1, 1)


def test_summarize_records_literal_complete_aggregation():
    assert accuracy.summarize_records("kreta", ROWS, expected_count=4) == SUMMARY


@pytest.mark.parametrize("value,expected", [(None, ""), ("**정답: B**", "B"),
                                            ("Answer: A\nAnswer: D", "D"), ("arbitrary prose", "")])
def test_parse_kreta_response(value, expected):
    assert accuracy.parse_kreta_response(value) == expected


@pytest.mark.parametrize("value,expected", [("", ""), ("Because...", "B"), ("정답은 (C)", "C")])
def test_choice_keeps_current_permissive_rules(value, expected):
    assert accuracy._choice(value) == expected


@pytest.mark.parametrize("value,expected", [("", ""), ("『ＡＢＣ!』", "abc"), ("  HELLO.  ", "hello")])
def test_normalize_answer(value, expected):
    assert accuracy._normalize_answer(value) == expected


@pytest.mark.parametrize("prediction,gold,expected", [("The 서울 city", "서울", True),
                                                      ("서울", "서울시청", True), ("", "서울", False)])
def test_mtvqa_match(prediction, gold, expected):
    assert accuracy._mtvqa_match(prediction, gold) is expected


@pytest.mark.parametrize("key,rows,expected", [
    ("mtvqa_kr", [{"row_idx": 2, "qa_idx": 3}], (["2\t3"], None)),
    ("mtvqa_kr", [{"row_idx": 2}], ([], "(row_idx, qa_idx)가 누락됨")),
    ("k_dtcbench", [{"index": "a"}, {"index": "a"}], (["a", "a"], "dataset item key가 중복됨")),
    ("k_dtcbench", [{}], ([], "index가 누락됨")),
])
def test_accuracy_item_keys(key, rows, expected):
    assert accuracy._accuracy_item_keys(key, rows) == expected


@pytest.mark.parametrize("key", ["k_dtcbench", "mtvqa_kr"])
def test_accuracy_protocol_literal_and_embedded_config_identity(tmp_path, key):
    config = {"dataset": {"revision": "revision"}, "decoding": {"max_tokens": 32},
              "extra": {"split": "test", "config": "Korean"}}
    protocol, selected = accuracy._accuracy_protocol(key, {"run_config": config}, tmp_path, "items")
    assert protocol == PROTOCOLS[key]
    assert selected is config


@pytest.mark.parametrize("stem,expected", [("model_DIRECT", ("model", "direct")), ("other", ("other", "unknown"))])
def test_kreta_mode(stem, expected):
    assert accuracy._kreta_mode(stem) == expected


def test_kreta_axes_skip_errors_and_sort_axis_names():
    rows = [dict(ROWS[0], topic_difficulty="s"), dict(ROWS[2], topic_difficulty="s")]
    assert accuracy._kreta_axes(rows) == (1, [
        {"name": "domain:z", "numerator": 1, "denominator": 1, "value": 1.0, "unit": "fraction"},
        {"name": "system:s", "numerator": 1, "denominator": 1, "value": 1.0, "unit": "fraction"},
    ], {"domain:z": (1, 1), "system:s": (1, 1)})


def test_read_kreta_rows_keeps_prefix_and_failure_order(tmp_path):
    source = tmp_path / "model_direct.jsonl"
    source.write_text('\n{"id": "a"}\n[]\n{"id": "b"}\n', encoding="utf-8")
    failures = ["existing"]
    assert accuracy._read_kreta_rows(source, failures) == [{"id": "a"}]
    assert failures == ["existing", "JSONL 읽기 실패: ValueError"]


def test_kreta_upstream_accuracy_missing_then_extra_source(tmp_path):
    source, summary = tmp_path / "model_direct.jsonl", tmp_path / "results.json"
    warnings = []
    assert accuracy._kreta_upstream_accuracy(source, summary, warnings) is None
    assert warnings == ["상류 results.json 비교값 없음 — raw 독립 재채점만 사용"]
    summary.write_text('{"model_direct": {"overall_accuracy": 0.25}, "other": {}}', encoding="utf-8")
    warnings = []
    assert accuracy._kreta_upstream_accuracy(source, summary, warnings) == 0.25
    assert warnings == ["상류 results.json에 다른 source key가 함께 있음 — 채점에는 사용하지 않음"]


def _source(tmp_path, key):
    source = tmp_path / "results/model/session/vision/multimodal" / key
    source.mkdir(parents=True)
    config = {"dataset": {"revision": "revision"}, "decoding": {"max_tokens": 32}, "extra": {"limit": None}}
    if key == "kreta":
        path = source / "model_direct.jsonl"
        path.write_text(json.dumps({"id": "a", "response": "A", "answer": "A", "pred_indexs": "A", "split": "test"}) + "\n")
        (source / "results.json").write_text('{"model_direct": {"overall_accuracy": 1.0}}')
        (source / "run_config.json").write_text(json.dumps(config))
        return path
    (source / "results.json").write_text('[{"index": "a", "response": "A", "answer": "A"}]')
    (source / "summary.json").write_text(json.dumps({"model": "model", "total": 1, "correct": 1, "run_config": config}))
    return source


@pytest.mark.parametrize("key", ["k_dtcbench", "kreta"])
def test_expected_counts_setitem_reaches_actual_adapt_result(tmp_path, monkeypatch, key):
    source = _source(tmp_path, key)
    monkeypatch.setitem(adapters.EXPECTED_COUNTS, key, 1)
    accepted = adapters.adapt_source(source)
    assert accepted["publishable"] is True
    assert accepted["failures"] == []
    assert accepted["counts"]["correct_measured"] == 1
    monkeypatch.setitem(adapters.EXPECTED_COUNTS, key, 987654)
    rejected = adapters.adapt_source(source)
    assert rejected["publishable"] is False
    assert rejected["failures"] == ["기대 건수 987654와 다름"]
    assert rejected["metrics"] == accepted["metrics"]


# Literal results captured before extraction; no fields omitted.
SUMMARY = {'counts': {'attempted': 3, 'measured': 2, 'errored': 1, 'unresolved': 0, 'correct_measured': 1},
 'correct': 1,
 'accuracy': 0.3333333333333333,
 'by_category': {'a': {'correct': 0, 'total': 1, 'accuracy': 0.0},
                 'z': {'correct': 1, 'total': 2, 'accuracy': 0.5}},
 'accuracy_strict': {'numerator': 1,
                     'denominator': 3,
                     'value': 0.3333333333333333,
                     'unit': 'fraction'},
 'accuracy_conditional': {'numerator': 1, 'denominator': 2, 'value': 0.5, 'unit': 'fraction'},
 'publish_status': {'publishable': False, 'failures': ['기대 건수 4와 다름', '오류 응답 1건 포함']},
 'warnings': ['상류 parser와 2행 불일치 (우리 무답 1, 다른 선택지 1) — 독립 재채점 점수임',
              '무답 1건 (33.3%) — 응답이 지시된 형식을 벗어나 절단됨. 점수를 능력 차이로만 해석하지 말 것'],
 'stored_prediction_mismatches': 2,
 'disagreement_ours_empty': 1,
 'disagreement_different_choice': 1,
 'no_answer': 1}

PROTOCOLS = {'k_dtcbench': {'fingerprint': 'sha256:3b77f5e3d84ed3a5c2e60b205956dba65f0d3b97b203c0bc96b387680f478464',
                'fingerprint_version': 2,
                'recorded': {'benchmark': 'K-DTCBench',
                             'dataset_provenance': {'revision': 'revision'},
                             'dataset_item_digest': 'items',
                             'limit': None,
                             'max_tokens': 32},
                'inferred': {'split': {'value': 'test',
                                       'basis': 'k_dtcbench.py fixed load_dataset split'}},
                'unknown': ['answer_parser_hash',
                            'image_preprocessing_version',
                            'prompt_template_hash',
                            'seed',
                            'temperature'],
                'complete': False},
 'mtvqa_kr': {'fingerprint': 'sha256:841590ced88ccc6ea236599e264d7a6f28bd1580524d9803ec26ca84a711af02',
              'fingerprint_version': 2,
              'recorded': {'benchmark': 'MTVQA-KR',
                           'dataset_provenance': {'revision': 'revision'},
                           'dataset_item_digest': 'items',
                           'split': 'test',
                           'category_filter': 'Korean rows',
                           'limit': None,
                           'config': 'Korean',
                           'max_tokens': 32},
              'inferred': {},
              'unknown': ['answer_parser_hash',
                          'image_preprocessing_version',
                          'prompt_template_hash',
                          'seed',
                          'temperature'],
              'complete': False}}

