"""무엇: blob 1회 읽기와 셋별 순차 대조. 입력: 고정 Git 범위·원문 provider. 출력: 원문 없는 보고 dict."""

import json
from pathlib import Path
import tempfile

from .decode import views
from .git_objects import CatFile, inventory
from .report import tool_sha
from .sources import NORMALIZATION, source_sets
from .windows import WindowIndex


def scan(root, base, head, *, length=12, max_bytes=256 * 1024 * 1024,
         max_candidates=2_000_000, source_provider=source_sets, scratch=None):
    if length < 1 or max_bytes < 1 or max_candidates < 1:
        raise ValueError("positive limits required")
    base, head, commits, blobs, prohibited, unsupported, already_public = inventory(root, base, head)
    result = dict(schema="publish_check/1", base=base, head=head, tool_sha256=tool_sha(),
                  normalization=NORMALIZATION, length=length, max_blob_bytes=max_bytes,
                  max_candidates=max_candidates, commits=commits, sources={}, source_failures=[],
                  forbidden_paths=prohibited, unsupported_entries=unsupported, blobs=[])
    # Cache views outside the repo, remove them even on exceptions. Never print their content.
    with tempfile.TemporaryDirectory(prefix="publish-check-", dir=scratch) as temporary:
        reader = CatFile(root)
        try:
            for oid, refs in sorted(blobs.items()):
                paths = sorted({r["path"] for r in refs})
                row = dict(oid=oid, paths=paths, references=refs, commit_count=len({r["commit"] for r in refs}),
                           checked=False, failures=[], matches=[])
                result["blobs"].append(row)
                try:
                    segments = list(views(reader.read(oid, max_bytes), paths))
                    Path(temporary, oid).write_text(json.dumps(segments, ensure_ascii=True), encoding="utf-8")
                except Exception:
                    row["failures"].append("blob_read_decode_or_size_failed")
        finally:
            reader.close()
        try:
            for name, documents, manifest in source_provider(root, length):
                if name in result["sources"]:
                    raise ValueError("duplicate source")
                index = WindowIndex(documents, length)
                result["sources"][name] = manifest
                for row in result["blobs"]:
                    if row["failures"]:
                        continue
                    try:
                        segments = json.loads(Path(temporary, row["oid"]).read_text(encoding="utf-8"))
                        for view, value_index, text in segments:
                            for match in index.matches(text, max_candidates=max_candidates):
                                row["matches"].append(dict(set=name, view=view, value_index=value_index, **match))
                    except Exception:
                        row["failures"].append("matching_failed")
                del index, documents
        except Exception:
            result["source_failures"].append("source_load_or_index_failed")
        if not result["sources"]:
            result["source_failures"].append("no_sources")
        for row in result["blobs"]:
            row["checked"] = not row["failures"] and not result["source_failures"]
    result["counts"] = dict(total_blobs=len(blobs), checked_blobs=sum(r["checked"] for r in result["blobs"]),
                            already_public_blobs=already_public,
                            failed_blobs=sum(not r["checked"] for r in result["blobs"]),
                            match_intervals=sum(len(r["matches"]) for r in result["blobs"]))
    result["ok"] = (result["counts"]["failed_blobs"] == 0 and not result["source_failures"]
                    and not prohibited and not unsupported and result["counts"]["match_intervals"] == 0)
    return result
