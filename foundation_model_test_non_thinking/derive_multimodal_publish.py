#!/usr/bin/env python3
"""Derive multimodal publication sidecars; dry-run unless --write is given."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shared.multimodal.publish.derive import (
    derive_all,
    derive_source,
    derived_sidecar_path,
    existing_native_sidecar,
    native_sidecar_from_source,
    preflight_kreta_source,
    rejected_sidecar_from_source,
    write_sidecar,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path("."))
    parser.add_argument("--write", action="store_true", help="write sidecars below _derived")
    parser.add_argument("--source", type=Path, help="derive only this source path")
    parser.add_argument("--native", action="store_true", help="mark a clean single source as NATIVE")
    parser.add_argument("--preflight-kreta", action="store_true", help="validate KRETA JSONL before evaluate.py")
    parser.add_argument("--reject-reason", help="force a single source to REJECTED with this runner failure")
    parser.add_argument("--force", action="store_true", help="allow passive derive to overwrite existing NATIVE sidecars")
    args = parser.parse_args(argv)
    if (args.native or args.preflight_kreta or args.reject_reason) and args.source is None:
        parser.error("--native/--preflight-kreta/--reject-reason requires --source")
    if args.reject_reason and (args.native or args.preflight_kreta):
        parser.error("--reject-reason cannot be combined with --native/--preflight-kreta")
    skipped_native: list[Path] = []

    def native_skip(path: Path, sidecar: dict) -> None:
        skipped_native.append(path)

    def native_overwrite_warning(path: Path, sidecar: dict) -> None:
        protocol = sidecar.get("protocol") or {}
        provenance = {
            "recorded": protocol.get("recorded") or {},
            "inferred": protocol.get("inferred") or {},
            "unknown": protocol.get("unknown") or [],
        }
        print(
            f"WARNING: --force overwriting NATIVE {path}; "
            f"completed_at_utc={sidecar.get('completed_at_utc')!r}; "
            f"protocol provenance={json.dumps(provenance, ensure_ascii=False, sort_keys=True)}",
            file=sys.stderr,
        )
    if args.preflight_kreta:
        ok, failures = preflight_kreta_source(args.source, args.base)
        if ok:
            print(f"KRETA preflight OK: {args.source}")
            return 0
        try:
            path, sidecar = derive_source(args.source, args.base)
            if args.write:
                write_sidecar(path, sidecar)
        except Exception as exc:
            print(f"KRETA rejected sidecar failed: {exc}", file=sys.stderr)
        for failure in failures:
            print(f"KRETA preflight REJECTED: {failure}", file=sys.stderr)
        return 1
    try:
        if args.source is not None:
            path = derived_sidecar_path(args.source)
            existing = existing_native_sidecar(path) if path.exists() else None
            passive_downgrade = existing is not None and not (args.native or args.reject_reason)
            if passive_downgrade and not args.force:
                native_skip(path, existing)
                derived = []
            else:
                if passive_downgrade:
                    native_overwrite_warning(path, existing)
                derived = [
                    rejected_sidecar_from_source(args.source, args.base, args.reject_reason)
                    if args.reject_reason
                    else native_sidecar_from_source(args.source, args.base)
                    if args.native
                    else derive_source(args.source, args.base)
                ]
            if args.write:
                for path, sidecar in derived:
                    write_sidecar(path, sidecar)
        else:
            derived = derive_all(
                args.base,
                write=args.write,
                force=args.force,
                on_native_skip=native_skip,
                on_native_overwrite=native_overwrite_warning,
            )
    except Exception as exc:
        print(f"derive failed: {exc}", file=sys.stderr)
        return 2
    if skipped_native:
        for path in skipped_native:
            print(f"skipped existing NATIVE {path}")
        print(f"skipped {len(skipped_native)} existing NATIVE sidecar(s)")
    if not derived and not skipped_native:
        print("multimodal 산출물이 없습니다.", file=sys.stderr)
        return 2
    action = "wrote" if args.write else "would write"
    for path, sidecar in derived:
        counts = sidecar.get("counts") or {}
        status = sidecar["status"]
        status_text = status.value if hasattr(status, "value") else status
        print(
            f"{action} {path}: {status_text} "
            f"(attempted={counts.get('attempted')}, errored={counts.get('errored')}, "
            f"unresolved={counts.get('unresolved')})"
        )
    print(
        f"{len(derived)} sidecar(s); {'write complete' if args.write else 'dry-run'}; "
        f"native skipped={len(skipped_native)}"
    )
    if args.native and any(sidecar["status"] != "NATIVE" for _, sidecar in derived):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
