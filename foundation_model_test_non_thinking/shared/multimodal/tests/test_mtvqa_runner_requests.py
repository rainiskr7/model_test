"""MTVQA main: Korean filtering and string/list qa_pairs expansion.

Excluded variable fields: run_config.timestamp_utc; sidecar completion timestamps
and artifact hashes. Environment probes are fixed in _runner_fakes.
"""

import pytest

pytest.register_assert_rewrite("_runner_fakes")

from _runner_fakes import assert_requests, assert_storage, load_runner, offline_guard, png, prepare

PROMPTS = [
    "도시는?\n\n이미지를 보고 위 질문에 한 단어 또는 짧은 구로 정확히 답하세요. 설명·머리말 없이 답만 출력하세요.",
    "색은?\n\n이미지를 보고 위 질문에 한 단어 또는 짧은 구로 정확히 답하세요. 설명·머리말 없이 답만 출력하세요.",
]


@pytest.mark.parametrize("error,pairs_as_list", [(False, False), (False, True), (True, False)])
def test_main_requests_and_files(monkeypatch, tmp_path, capsys, error, pairs_as_list):
    offline_guard(monkeypatch)
    runner = load_runner(monkeypatch, "mtvqa_kr")
    rows = [
        {"id": "skip-en", "language": "English", "image": png("green"), "qa_pairs": [{"Q": "skip", "A": "skip"}]},
        {"id": "ko-0", "language": " Korean ", "image": png("red"),
         "qa_pairs": "[{'question': '도시는?', 'answers': ['서울', '서울시']}, {'Q': '색은?', 'A': '파랑'}, {'Q': 'skip'}]"},
        {"id": "ko-1", "language": "KR", "image": png("blue"), "qa_pairs": "malformed"},
    ]
    if pairs_as_list:
        import ast
        rows[1]["qa_pairs"] = ast.literal_eval(rows[1]["qa_pairs"])
    responses = ["  서울! ", TimeoutError("synthetic timeout"), TimeoutError("synthetic timeout")] if error else ["  서울! ", "빨강"]
    state = prepare(monkeypatch, tmp_path, runner, rows, responses,
                    extra=["--split", "test", "--config", "synthetic-ko", "--limit", "2"])
    assert runner.main() == 1  # 558 expected QA pairs, not two source images.
    assert capsys.readouterr().err == ""
    assert_requests(state, PROMPTS + ([PROMPTS[1]] if error else []), [(255, 0, 0)] * (3 if error else 2))
    assert state.sleeps == ([0.0] if error else [])
    records = assert_storage(
        state, runner, tmp_path, benchmark="MTVQA-KR", dataset_id="ByteDance/MTVQA",
        split="test", load_extra={"name": "synthetic-ko"},
        extra={"split": "test", "config": "synthetic-ko", "limit": 2}, expected_count=558, error=error,
    )
    assert records == [
        {"row_idx": 0, "qa_idx": 0, "id": "ko-0", "question": "도시는?", "gold": ["서울", "서울시"],
         "response": "  서울! ", "correct": True, "error": None},
        {"row_idx": 0, "qa_idx": 1, "id": "ko-0", "question": "색은?", "gold": ["파랑"],
         "response": {"error": "synthetic timeout"} if error else "빨강", "correct": False,
         "error": "synthetic timeout" if error else None},
    ]
