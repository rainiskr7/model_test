"""Identity expectations captured by running the original judge with fake responses."""

import argparse
import json
from types import SimpleNamespace
import sys

import pandas as pd

from shared.multimodal.benches import koffvqa_api_judge as judge


def test_identity_snapshot_matches_original_values_and_key_order():
    identity = judge.ServedIdentity()
    assert judge.served_identity_snapshot(identity) == {}
    for values in (
        {"model": "z", "provider": "p", "system_fingerprint": "fp2"},
        {"model": "a", "system_fingerprint": "fp1"},
        {"model": "z", "provider": "p"},
        {"model": "", "provider": None, "system_fingerprint": 0},
        {"provider": 7},
    ):
        judge._record_served_identity(identity, SimpleNamespace(**values))
    snapshot = judge.served_identity_snapshot(identity)
    assert json.dumps(snapshot) == (
        '{"model": ["a", "z"], "system_fingerprint": ["fp1", "fp2"], "provider": ["7", "p"]}'
    )
    snapshot["model"].append("detached")
    assert judge.served_identity_snapshot(identity)["model"] == ["a", "z"]


def test_two_identities_do_not_share_accumulation():
    first, second = judge.ServedIdentity(), judge.ServedIdentity()
    judge._record_served_identity(first, SimpleNamespace(model="first"))
    assert judge.served_identity_snapshot(second) == {}
    judge._record_served_identity(second, SimpleNamespace(provider="second"))
    assert judge.served_identity_snapshot(first) == {"model": ["first"]}
    assert judge.served_identity_snapshot(second) == {"provider": ["second"]}


def _client(model):
    response = SimpleNamespace(
        model=model,
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"score": 8, "reason": "ok"}'))],
    )
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: response)))


def test_judge_one_records_only_in_supplied_identity():
    first, second = judge.ServedIdentity(), judge.ServedIdentity()
    outcome = judge.judge_one(_client("served"), "alias", "q", "a", "rubric", identity=first)
    assert outcome == (8, "ok", None, '{"score": 8, "reason": "ok"}')
    assert judge.served_identity_snapshot(first) == {"model": ["served"]}
    assert judge.served_identity_snapshot(second) == {}
    assert judge.judge_one(_client("untracked"), "alias", "q", "a", "rubric") == outcome
    from unittest.mock import Mock
    client = _client("profile")
    client.chat.completions.create = Mock(wraps=client.chat.completions.create)
    assert judge.judge_one(client, "alias", "q", "a", "rubric", max_tokens=2000,
                           provider="deepinfra/bf16", reasoning_effort="medium") == outcome
    sent = client.chat.completions.create.call_args.kwargs
    assert sent["max_tokens"] == 2000
    assert sent["extra_body"] == {
        "provider": {"order": ["deepinfra/bf16"], "allow_fallbacks": False, "require_parameters": True},
        "reasoning": {"effort": "medium"},
    }
    # C2: fixed upstream template hash, independent of an installed data tree.
    assert judge._prompt_template_hash("original") == "sha256:812c0c23a231e471163a42f7bf6aeb6b68ba52e6a491f4579e0c45d5712c18f2"
    for text, expected in (
        ("", None), ("근거만", None), ("최종 점수: 10점 만점에 11점", None),
        ("최종 점수: 10점 만점에 -1점", None), ("최종 점수: 10점 만점에 8.5점", None),
        ("최종 점수: 10점 만점에 8점\n추가 문장", None),
        ("**최종 점수: 10점 만점에 8점*", None), ("최종 점수: 10점 만점에 8점..", None),
        ("**최종 점수: 10점 만점에 8점.**.", None), ("최종 점수: 10점 만점에 08점", None),
        ("최종 점수: 10점 만점에 0점", 0), ("최종 점수: 10점 만점에 10점", 10),
        ("근거\n  **최종 점수: 10점 만점에 8점**.  \n\n", 8),
        ("*최종 점수: 10점 만점에 8점.*", 8), ("최종 점수: 10점 만점에 8점.", 8),
        ("- **최종 점수: 10점 만점에 10점**", 10),
        ("* 최종 점수: 10점 만점에 7점", 7),
        ("1. 최종 점수: 10점 만점에 3점.", 3),
        ("• 최종 점수: 10점 만점에 4점", 4),
        ("-- 최종 점수: 10점 만점에 3점", None),
        ("- 최종 점수: 10점 만점에 8.5점", None),
        ("- * 최종 점수: 10점 만점에 3점", None),
        ('{"score": 8, "reason": "JSON only"}', None),
    ):
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
        client.chat.completions.create = Mock(return_value=response)
        outcome = judge.judge_one(client, "alias", "q{question}", "응답", {"기준": 1}, prompt_profile="original")
        assert outcome[0] == expected and outcome[1] == outcome[3] == text
        assert bool(outcome[2]) is (expected is None)
        sent = client.chat.completions.create.call_args.kwargs
        assert sent["messages"] == [{"role": "user", "content": judge.ORIGINAL_JUDGE_PROMPT.format(
            "q{question}", "응답", json.dumps({"기준": 1}, ensure_ascii=False, indent=2))}]
    # Optional upstream comparison is read-only; the pinned hash above always runs.
    import ast
    from pathlib import Path
    import pytest
    upstream = Path(__file__).resolve().parents[3] / "data/KOFFVQA/src/judges.py"
    if not upstream.is_file():
        pytest.skip("optional upstream template comparison: data/KOFFVQA unavailable; fixed SHA and parser checked")
    node = next(n for n in ast.parse(upstream.read_text()).body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "base_judge_prompt" for t in n.targets))
    assert judge.ORIGINAL_JUDGE_PROMPT == node.value.func.value.value.strip()



def test_repeated_main_saves_separate_identity_and_preserves_summary_order(monkeypatch, tmp_path):
    predfile = tmp_path / "synthetic.xlsx"
    predfile.write_bytes(b"synthetic prediction bytes")
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", lambda self: SimpleNamespace(
        predfile=str(predfile), target_model="target", judge_model="alias",
        judge_base_url="https://unused", judge_api_key="fake", limit=None, seed=None,
        judge_max_tokens=1024, question_column=None, criteria_column=None, response_column=None,
    ))
    monkeypatch.setattr(judge.pd, "read_excel", lambda path: pd.DataFrame([
        {"index": "item", "question": "q", "answer": "rubric", "prediction": "a"},
    ]))
    clients = iter([_client("first"), _client("second")])
    saved = []
    # Isolate runtime IO and network at the helper boundary, without changing argv.
    monkeypatch.setitem(sys.modules, "shared.multimodal.benches.common", SimpleNamespace(
        get_base_dir=lambda path: tmp_path, get_timestamp=lambda: "session",
        get_results_dir=lambda *args, **kwargs: tmp_path,
        save_json=lambda path, payload: saved.append((path.name, payload)),
        build_run_config=lambda **kwargs: {"synthetic": True},
        make_client=lambda *args: next(clients),
    ))
    judge.main()
    judge.main()
    first, second = [payload for name, payload in saved if name == "summary.json"]
    assert first["judge_served_identity"] == {"model": ["first"]}
    assert second["judge_served_identity"] == {"model": ["second"]}
    assert list(first) == list(second) == [
        "benchmark", "judge_model", "judge_request", "judge_prompt_version", "judge_prompt_template_sha256",
        "judge_base_url", "judge_served_identity", "target_model", "predfile",
        "prediction_sha256", "total", "scored", "avg_score", "max_possible_score", "run_config",
    ]
    assert first["scored"] == second["scored"] == 1
    assert first["avg_score"] == second["avg_score"] == 8.0
