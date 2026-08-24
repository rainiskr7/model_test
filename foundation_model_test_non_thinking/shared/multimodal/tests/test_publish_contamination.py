from __future__ import annotations

import json
from pathlib import Path

from shared.multimodal.publish.adapters import parse_kreta_response
from shared.multimodal.publish.derive import derive_source, discover_sources


REPO = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).parent / "fixtures" / "known_kreta_contamination.json"


def test_known_contaminated_kreta_sources_are_rejected():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(cases) == 10
    for case in cases:
        source = REPO / case["path"]
        assert source.is_file(), case["path"]
        _, sidecar = derive_source(source, REPO)
        assert sidecar["status"] == "REJECTED"
        assert sidecar["publishable"] is False
        assert sidecar["counts"]["attempted"] == case["attempted"]
        assert sidecar["counts"]["errored"] == case["errored"]
        rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
        poisoned_correct = sum(
            bool(row.get("if_right"))
            for row in rows
            if isinstance(row.get("response"), dict) and row["response"].get("error")
        )
        assert poisoned_correct == case["errored_marked_correct"]


def test_non_error_kreta_sources_survive_independent_response_regrading():
    dirty = {case["path"] for case in json.loads(FIXTURE.read_text(encoding="utf-8"))}
    sources = [path for path in discover_sources(REPO) if path.suffix == ".jsonl"]
    clean = []
    for path in sources:
        if path.relative_to(REPO).as_posix() in dirty:
            continue
        _, candidate = derive_source(path, REPO)
        if candidate["publishable"]:
            clean.append(path)
    assert len(clean) == 11
    for source in clean:
        _, sidecar = derive_source(source, REPO)
        rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
        parser_choices = [parse_kreta_response(row.get("response")) for row in rows]
        independent_correct = sum(
            choice == str(row.get("answer", "")).strip().upper()
            for choice, row in zip(parser_choices, rows)
        )
        assert sidecar["status"] == "LEGACY_REVALIDATED", source
        assert sidecar["publishable"] is True
        assert sidecar["counts"]["errored"] == 0
        assert sidecar["counts"]["correct_measured"] == independent_correct
        assert sidecar["counts"]["no_answer"] == sum(not choice for choice in parser_choices)
        assert sidecar["upstream_comparison"]["parser_disagreement_rows"] >= 1
