"""입력: 격리 CLI·합성 코호트. 출력: C3의 rc 2·출력 단위·무부작용 검증."""

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from shared.multimodal.rescore.manifest import load_manifest
from shared.stats.__main__ import comparison, main, render_json, render_markdown
from shared.stats.tests.test_stats_paired_units import pair_case
from shared.stats.tests.test_stats_selection_units import session_case


def enriched_pair():
    a, b = pair_case()
    for label, value in (("a", a), ("b", b)):
        value.update(model=label, runs=[{"source": f"results/{label}/session/bench"}],
                     folded_duplicates=[])
    return a, b


def test_main_reads_real_tmp_sidecars_and_outputs_without_writes(tmp_path, monkeypatch, capsys):
    _, directory = session_case(tmp_path)
    session_case(tmp_path, model="b")
    monkeypatch.setattr("shared.stats.selection.load_manifest",
                        lambda bench, revision, _: load_manifest(bench, revision, directory))
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    args = ["--base", str(tmp_path), "--a", "a", "--b", "b", "--bench", "k_dtcbench",
            "--seed", "5", "--resamples", "10"]
    assert main(args + ["--format", "json"]) == 0
    value = json.loads(capsys.readouterr().out)
    assert value["difference"] == 0 and value["ci95"] == [0, 0]
    assert (value["items"], value["images"], value["repetitions_a"]) == (3, 2, 1)
    assert main(args) == 0
    markdown = capsys.readouterr().out
    assert "관측한 반복 평균에 조건부인 문항 표집 불확실성" in markdown
    assert "A−B (pp)" in markdown and "results/a/" in markdown
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("mutation", ["partial", "disjoint", "empty", "repetitions", "cohort", "metric"])
def test_c3_cli_rejects_mismatches_with_rc2_and_candidates(monkeypatch, capsys, mutation):
    a, b = enriched_pair()
    if mutation == "partial":
        b["items"].pop()
    elif mutation == "disjoint":
        for item in b["items"]:
            item["key"] += "_other"
    elif mutation == "empty":
        a["items"] = b["items"] = []
    else:
        b[mutation] = 1 if mutation == "repetitions" else "different"
    monkeypatch.setattr("shared.stats.__main__.load_cohort",
                        lambda base, model, *args: a if model == "a" else b)
    assert main(["--a", "a", "--b", "b", "--bench", "k_dtcbench"]) == 2
    output = capsys.readouterr()
    assert not output.out
    assert len(json.loads(output.err)["candidates"]) == 2


def test_ambiguity_returns_rc2_and_no_unrequested_cohort_choice(tmp_path, capsys):
    session_case(tmp_path)
    session_case(tmp_path, session="second", protocol={"limit": 1})
    assert main(["--base", str(tmp_path), "--a", "a", "--b", "a", "--bench", "k_dtcbench"]) == 2
    assert len(json.loads(capsys.readouterr().err)["candidates"]) == 2


def test_rendering_units_upstream_and_nonmutation():
    a, b = enriched_pair()
    a["upstream"] = b["upstream"] = {"repository": "https://example.org/repo",
                                    "commit": "123", "path": "score.py"}
    value = comparison(a, b, resamples=10)
    value["a"]["model"] = "a|model\nlabel"
    before = deepcopy(value)
    markdown = render_markdown(value)
    assert "33.3333" in markdown and "a\\|model label" in markdown
    assert "/blob/123/score.py" in markdown
    assert json.loads(render_json(value)) == value == before


def test_bad_resamples_and_invalid_input_never_expose_exception_payload(monkeypatch, capsys):
    def fail(*args):
        raise ValueError("SECRET_SENTINEL")
    monkeypatch.setattr("shared.stats.__main__.load_cohort", fail)
    for extra in ([], ["--resamples", "0"]):
        assert main(["--a", "a", "--b", "b", "--bench", "k_dtcbench"] + extra) == 2
        assert "SECRET_SENTINEL" not in capsys.readouterr().err


def test_import_and_module_entry_are_offline_and_do_not_write(tmp_path):
    root = Path(__file__).resolve().parents[3]
    env = {**os.environ, "PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1"}
    code = """
import importlib, os, socket, sys
before = dict(os.environ)
def audit(event, args):
    if event == 'open' and isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
        raise AssertionError('write forbidden')
    if event.startswith('socket.') or event in ('os.mkdir', 'os.remove', 'os.rename'):
        raise AssertionError('side effect forbidden')
sys.addaudithook(audit)
for name in ('item_scores', 'paired', 'selection', '__main__'):
    importlib.import_module('shared.stats.' + name)
assert dict(os.environ) == before
"""
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd=tmp_path, env=env, capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    result = subprocess.run([sys.executable, "-B", "-m", "shared.stats", "--a", "a",
                             "--b", "b", "--bench", "k_dtcbench"],
                            cwd=tmp_path, env=env, capture_output=True)
    assert result.returncode == 2 and b"directory" in result.stderr
    assert not list(tmp_path.iterdir())
