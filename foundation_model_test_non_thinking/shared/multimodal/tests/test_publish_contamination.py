from __future__ import annotations

import json
from pathlib import Path

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


def test_all_clean_kreta_sources_survive_legacy_revalidation():
    dirty = {case["path"] for case in json.loads(FIXTURE.read_text(encoding="utf-8"))}
    sources = [path for path in discover_sources(REPO) if path.suffix == ".jsonl"]
    clean = [path for path in sources if path.relative_to(REPO).as_posix() not in dirty]
    assert len(clean) == 11
    for source in clean:
        _, sidecar = derive_source(source, REPO)
        assert sidecar["status"] == "LEGACY_REVALIDATED", source
        assert sidecar["publishable"] is True
        assert sidecar["counts"]["errored"] == 0
