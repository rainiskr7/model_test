"""무엇: 확신 등록 증거 I/O · 입력: root/run · 출력: 정책·파일·해시 · 계약 §7-4d."""

import yaml

from jeveval.io import analysis, run_files
from jeveval.io.hashes import sha256_file
from jeveval.io.paths import inside
from jeveval.io.question_registration import started

ARTIFACTS = ("fingerprint.json", "variant_threshold.json", "test/variant_seal.json", "test/seal.json")


def read(root, directory):
    """손상은 고정 오류로 반환하고 보조 수치를 공개하지 않는다."""
    directory = inside(root, directory)
    e = dict(artifacts={}, hashes={}, errors=[], manifest=None, manifest_sha256=None,
             policy=None, started=started(directory))
    try:
        for name in ARTIFACTS:
            path = inside(root, directory / name)
            if path.exists():
                e["artifacts"][name] = run_files.read_json(path)
                e["hashes"][name] = sha256_file(path)
        fp = e["artifacts"].get("fingerprint.json", {})
        e["manifest"], e["manifest_sha256"], e["policy"] = analysis.declaration(root, fp, "score_variants")
        for name in ("dev/final.jsonl", "threshold.json"):
            path = inside(root, directory / name)
            if path.exists():
                e["hashes"][name] = sha256_file(path)
    except (ValueError, OSError, KeyError, TypeError, yaml.YAMLError):
        e["errors"].append("invalid_variant_registration")
    return e


def write_new(directory, name, value):
    """등록 정책과 역사 결과는 재작성하지 않는다."""
    path = directory / name
    if run_files.exists(path):
        raise ValueError("analysis artifact already exists")
    run_files.write_json(path, value)
