"""무엇: 등록 증거 읽기 · 입력: root/run · 출력: 파일 schema · 계약 판 5 보정 2 §7-4b."""

from pathlib import Path

import yaml

from jeveval.io import analysis, run_files
from jeveval.io.config import read_yaml
from jeveval.io.hashes import sha256_file
from jeveval.io.paths import inside

ARTIFACTS = ("fingerprint.json", "question_threshold.json", "test/question_seal.json", "test/seal.json")
START = ("seal.json", "question_seal.json", "attempts.jsonl", "final.jsonl", "derived.json", "replay.json")


def started(directory):
    """빈 파일도 시작 증거다. 손상된 파일을 읽어 무시하지 않는다."""
    return any(run_files.exists(Path(directory) / "test" / name) for name in START)


def declaration(root, fp):
    """저장 fingerprint가 동결한 자기 overlay와 manifest만 읽는다."""
    name = f"configs/sets/{fp.get('set')}.yaml"
    if name not in fp.get("files", {}):
        return None, None, None
    path = inside(root, name)
    if sha256_file(path) != fp["files"][name]:
        raise ValueError("registered overlay changed")
    manifest = read_yaml(path).get("analysis")
    if manifest is None:
        return None, None, None
    value, digest = analysis.policy(root, manifest)
    if digest != fp["files"].get(manifest):
        raise ValueError("manifest not frozen")
    return manifest, digest, value


def read(root, directory):
    """읽기 실패는 고정 오류로 보존하며 원문 예외를 넘기지 않는다."""
    directory = inside(root, directory)
    result = dict(schema="question_registration_evidence/1", artifacts={}, hashes={}, errors=[],
                  manifest=None, manifest_sha256=None, policy=None, started=started(directory))
    for name in ARTIFACTS:
        try:
            path = inside(root, directory / name)
            if path.exists():
                result["artifacts"][name] = run_files.read_json(path)
                result["hashes"][name] = sha256_file(path)
        except (ValueError, OSError, TypeError):
            result["errors"].append("invalid_registration_artifact")
    try:
        fp = result["artifacts"].get("fingerprint.json", {})
        result["manifest"], result["manifest_sha256"], result["policy"] = declaration(root, fp)
        path = inside(root, directory / "dev/final.jsonl")
        if path.exists():
            result["hashes"]["dev/final.jsonl"] = sha256_file(path)
    except (ValueError, OSError, TypeError, KeyError, yaml.YAMLError):
        result["errors"].append("invalid_registration_inputs")
    return result
