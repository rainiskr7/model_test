"""무엇: T0 단계 파일 해시 검증 · 입력: inputs/관측/변형 파일 · 출력: 검증된 레코드 · 계약 §8-7 T-a."""

from pathlib import Path

from jeveval.io.hashes import sha256_file
from jeveval.io.run_files import read_json
from jeveval.io.t0_files import read_lines
from jeveval.t0.samples import targets
from jeveval.types.t0 import T0Observation


def digest(path):
    return sha256_file(path) if Path(path).exists() else None


def observations(directory, bundle, side):
    path = Path(directory) / f"{side}.jsonl"
    if not path.exists():
        return []
    header, records = read_lines(path)
    if header != dict(schema=f"t0_{side}/1", inputs_sha256=bundle.sha256):
        raise ValueError("T0 observation inputs hash mismatch")
    expected, seen, result = {r.case_id: r for r in bundle.rows}, set(), []
    for record in records:
        record = dict(record)
        record.pop("latency_ms", None)
        record.pop("response_bytes", None)
        obs = T0Observation.from_dict(record)
        if obs.case_id not in expected or obs.case_id in seen:
            raise ValueError("unexpected/duplicate T0 observation")
        seen.add(obs.case_id)
        row = expected[obs.case_id]
        envelope = row.reference_envelope_sha256 if side == "reference" else row.envelope_sha256
        if (obs.inputs_sha256 != bundle.sha256 or obs.request_sha256 != row.request_sha256
                or obs.envelope_sha256 != envelope):
            raise ValueError("T0 observation request hash mismatch")
        result.append(obs)
    return result


def variants(directory, bundle):
    path = Path(directory) / "variants.jsonl"
    if not path.exists():
        return dict(batch_one_equal=False, reason="missing_variants"), []
    header, records = read_lines(path)
    if (header.get("schema") != "t0_variants/1" or header["inputs_sha256"] != bundle.sha256
            or header["family"] != bundle.metadata["model"]
            or header["reference_sha256"] != digest(Path(directory) / "reference.jsonl")):
        raise ValueError("T0 variants provenance mismatch")
    expected = {r.case_id: r for r in bundle.rows if r.boundary is None}
    seen = set()
    for record in records:
        key = (record["case_id"], record["variant"], record["repeat"])
        if record["case_id"] not in expected or key in seen:
            raise ValueError("unexpected/duplicate T0 variant")
        seen.add(key)
        row = expected[record["case_id"]]
        if (record["inputs_sha256"] != bundle.sha256 or record["request_sha256"] != row.request_sha256
                or record["envelope_sha256"] != row.reference_envelope_sha256
                or record["target_sha256"] != targets(row)):
            raise ValueError("T0 variant target hash mismatch")
    return header, records


def fingerprint(directory, bundle):
    value = read_json(Path(directory) / "fingerprint.json")
    for key, expected in (("inputs_sha256", bundle.sha256),
                          ("config_sha256", bundle.metadata["config_sha256"]),
                          ("fixture_sha256", bundle.metadata["fixture_sha256"])):
        if value[key] != expected:
            raise ValueError("T0 fingerprint provenance mismatch")
    return value
