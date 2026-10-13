"""JSON input and fingerprints. This module never writes files."""

import hashlib
import json


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=_object,
                         parse_constant=lambda value: _bad_constant(value))


def _bad_constant(value):
    raise ValueError(f"Non-JSON numeric constant: {value}")


def required_files(folder, pattern, expected=None):
    paths = sorted(folder.glob(pattern))
    if not paths or (expected is not None and len(paths) != expected):
        raise ValueError(f"Unexpected file count in {folder}: {len(paths)}; expected {expected}")
    return paths


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False)


def fingerprint_files(paths):
    return [{"path": str(path), "sha256": sha256_file(path)} for path in paths]
