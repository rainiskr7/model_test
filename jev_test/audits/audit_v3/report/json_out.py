"""Audit fingerprints and artifacts; writes are confined to audit_v3/out."""

import hashlib
import json
import platform
from copy import deepcopy
from datetime import datetime, timezone

import tokenizers

from build import wording
from common.io import fingerprint_files, json_text, sha256_text
from common.request import serialize
from config import HERE, OUT, SPEC_AMBIGUITIES


def select_primary(rules):
    if any(rules[rule]["variants"]["actions_only"]["status"] == "FAIL" for rule in ("R2v3", "R4")):
        return "STOP"
    if all(rule["status"] == "PASS" for rule in rules.values()):
        return "full"
    if any(rule["status"] == "FAIL" for rule in rules.values()):
        return "actions_only"
    # SPEC-AMBIGUOUS: A1. Null records an undefined choice; it is not STOP or FAIL.
    return None


def _request_digest(requests):
    digest = hashlib.sha256()
    for index, request in enumerate(requests):
        if index:
            digest.update(b"\n")
        digest.update(serialize(request["state"], request["questions"]).encode("utf-8"))
    return digest.hexdigest()


def create(rules, statistics, variants, inputs, tokenizer_inputs, started_at):
    constants = {key: value for key, value in vars(wording).items() if key.isupper()}
    ambiguities = deepcopy(SPEC_AMBIGUITIES)
    primary = select_primary(rules)
    ambiguities[0]["triggered"] = primary is None
    ambiguities[1]["triggered"] = bool(rules["R5"]["violation_counts"]["a"] or rules["R5"]["violation_counts"]["b"])
    ambiguities[2]["triggered"] = bool(statistics["copy_baseline"]["unavailable_bundles"] or
                                      statistics["distribution"]["second_slot_none"]["unavailable_bundles"])
    ambiguities[3]["triggered"] = any(rules["R6"][field]["conflicting_service_frames"]
                                      for field in ("previous_user", "next_user"))
    return {"started_at": started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
            "runtime": {"python": platform.python_version(), "tokenizers": tokenizers.__version__},
            "sample_count": len(variants["full"]), "inputs": inputs, "tokenizers": tokenizer_inputs,
            "fingerprints": {"spec": fingerprint_files([HERE / "SPEC.md"])[0],
                             "python_files": fingerprint_files(sorted(HERE.rglob("*.py"))),
                             "wording_constants": constants, "wording_constants_sha256": sha256_text(json_text(constants)),
                             "requests_sha256": {variant: _request_digest(requests) for variant, requests in variants.items()},
                             "request_digest_format": "UTF-8 serialize(state,questions), joined by LF, no trailing LF"},
            "rules": rules, "statistics": statistics, "primary_variant": primary,
            "spec_ambiguities": ambiguities,
            "precedence_resolution": "JEV_TEST_PLAN.md §7-1 requires all six injections to detect FAIL; run.py includes that R7 gate."}


def write(report, variants):
    if not OUT.resolve().is_relative_to(HERE.resolve()):
        raise ValueError("Output directory escapes audit_v3")
    OUT.mkdir(exist_ok=True)
    contents = {"result.json": json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"}
    for variant, requests in variants.items():
        contents[f"example_{variant}.json"] = serialize(requests[0]["state"], requests[0]["questions"])
    for name, text in contents.items():
        path = OUT / name
        if not path.resolve().is_relative_to(HERE.resolve()):
            raise ValueError(f"Output file escapes audit_v3: {path}")
        path.write_text(text, encoding="utf-8")
