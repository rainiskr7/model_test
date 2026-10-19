"""Re-read artifacts; equal missing/failed outputs are never a match."""

import argparse
import json
from pathlib import Path

from tools.output_baseline.inputs import sha256, validate_snapshot


def expected_outputs(entries):
    from tools.output_baseline.render_reports import REPORTS

    names = ["reports/" + module + ".stdout" for module in REPORTS]
    for item in entries:
        kind = item["kind"]
        suffix = "stdout" if kind == "agent" else "sidecar.json" if kind == "multimodal" else "summary.json"
        names.append(kind + "/" + item["path"] + "/" + suffix)
    return names


def compare(manifest):
    issues = list(manifest.get("errors", []))
    issues.extend(validate_snapshot(manifest["snapshot"]))
    if not manifest.get("prerequisite", {}).get("ok"):
        issues.append("prerequisite failed")
    if not manifest.get("boundary", {}).get("ok"):
        issues.append("write boundary failed")
    expected = set(manifest["expected_outputs"])
    if not expected:
        issues.append("empty expected outputs")
    sides = manifest["sides"]
    for side in ("head", "working"):
        record = sides.get(side, {})
        issues.extend(f"{side}: {issue}" for issue in record.get("errors", []))
        artifacts = record.get("artifacts", {})
        for name in sorted(expected | set(artifacts)):
            if name not in expected:
                issues.append(f"{side}: unexpected output: {name}")
            elif name not in artifacts or not Path(artifacts[name]["path"]).is_file():
                issues.append(f"{side}: missing output: {name}")
            else:
                kind = name.split("/", 1)[0]
                allowed = (0, 1, 3) if kind == "agent" else (0, 1) if kind in {"taubench", "functionchat"} else (0,)
                if artifacts[name]["rc"] not in allowed:
                    issues.append(f"{side}: failed output: {name} rc={artifacts[name]['rc']}")
    if issues:
        return 2, issues
    differences = []
    for name in sorted(expected):
        left, right = (sides[side]["artifacts"][name] for side in ("head", "working"))
        if left["rc"] != right["rc"] or sha256(left["path"]) != sha256(right["path"]):
            differences.append(f"DIFF: {name}")
    return (1, differences) if differences else (0, [f"MATCH: {len(expected)} outputs"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        rc, messages = compare(json.loads(args.manifest.read_text()))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        rc, messages = 2, [f"invalid manifest: {type(exc).__name__}: {exc}"]
    print("\n".join(messages))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
