"""무엇: T0 입력 확정/복원 · 입력: fixture/공개 원본/길이 빌더 · 출력: 비공개 inputs · 계약 §8-7 T-a/c/g."""

from hashlib import sha256
from pathlib import Path
import re

from jeveval.data.t0_fixture import resolve_source
from jeveval.io.hashes import sha256_file
from jeveval.io.run_files import read_json
from jeveval.io.t0_files import read_lines, write_lines
from jeveval.io.t0_sources import read_sources
from jeveval.t0.record import config_sha256
from jeveval.t0.request import build_request
from jeveval.t0.tolerance import VARIANTS, V11_VARIANTS
from jeveval.types.t0 import T0Boundary, T0Case
from jeveval.types.t0_io import T0Input, T0Inputs


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", value):
        raise ValueError("invalid T0 identifier")
    return value


def request_from(body):
    return build_request(body["model"], body["state"], {"kind": "plain_text"}, body["questions"],
                         images=body.get("images"))


def _lengths(value):
    if value is None:
        return None
    value = [value] if type(value) is int else value
    if not isinstance(value, list) or not value or any(type(n) is not int or n < 0 for n in value):
        raise ValueError("invalid measured total length")
    return value


def _entry(cid, request, reference_name, lengths, boundary=None):
    ref = request_from(dict(request.body, model=reference_name or request.body["model"]))
    return T0Input(identifier(cid), request.body, ref.body, request.request_sha256,
                   request.envelope_sha256, ref.envelope_sha256, _lengths(lengths), boundary)


def _ordinary(fixture, cfg, sources, reference_name, measurer):
    entries = []
    for case in fixture["cases"]:
        if case.get("kind") == "boundary":
            continue
        if ("state_ref" in case) == ("synthetic_state" in case):
            raise ValueError("exactly one T0 state source required")
        if "state_ref" in case:
            state = resolve_source(case["state_ref"], sources)
            if sha256(state.encode()).hexdigest() != case["state_sha256"]:
                raise ValueError("T0 source hash mismatch")
        else:
            state = case["synthetic_state"]
        spec = case.get("state_spec", {"kind":"plain_text"})
        request = build_request(cfg.served_name, state, spec, case["questions"])
        entries.append(_entry(case["case_id"], request, reference_name,
                              None if measurer is None else measurer(request)))
    targets = {(r.case_id, qid) for r in entries for qid in r.body["questions"]}
    batches = fixture["batches"]
    if (len(batches) != len(targets) or {tuple(b["target"]) for b in batches} != targets
            or any(b["placements"] != list(V11_VARIANTS) for b in batches)):
        raise ValueError("incomplete T0 target placements")
    return entries


def _boundaries(fixture, entries, cfg, reference_name, builder):
    bases = {r.case_id: r for r in entries}
    for rule in fixture["cases"]:
        if rule.get("kind") != "boundary":
            continue
        if rule["offsets"] != [0, 1]:
            raise ValueError("invalid boundary offsets")
        base = request_from(bases[rule["base_case"]].body)
        for offset in rule["offsets"]:
            limit = cfg.limit["tokens"]
            request, lengths = base, None
            if builder is not None:
                if type(limit) is not int or limit <= 0:
                    raise ValueError("boundary limit unavailable")
                request, lengths = builder(base, limit + offset)
                lengths = _lengths(lengths)
                if lengths is None or max(lengths) != limit + offset:
                    raise ValueError("boundary builder missed target")
                if request.body["questions"] != base.body["questions"] or request.body["model"] != base.body["model"]:
                    raise ValueError("boundary builder changed question/model")
            boundary = T0Boundary(lengths, limit or 0, cfg.limit["overflow"] or "unconfigured",
                                  cfg.input_limit_response)
            entries.append(_entry(f"{rule['case_id']}_{offset}", request, reference_name, lengths, boundary))


def freeze(path, fixture_path, cfg, root, run_id, *, sources=None, reference_name=None,
           boundary_builder=None, measurer=None):
    if Path(path).exists():
        raise ValueError("T0 inputs already frozen")
    if cfg.id not in VARIANTS or cfg.kind != "systemone":
        raise ValueError("unsupported T0 model family")
    fixture = read_json(fixture_path)
    if fixture.get("schema") != "t0_fixture/1":
        raise ValueError("unsupported T0 fixture schema")
    if sources is None:
        selected = sorted({c["state_ref"]["set"] for c in fixture["cases"] if "state_ref" in c})
        sources = read_sources(root, selected)
    entries = _ordinary(fixture, cfg, sources, reference_name, measurer)
    _boundaries(fixture, entries, cfg, reference_name, boundary_builder)
    ids = [r.case_id for r in entries]
    if not entries or len(set(ids)) != len(ids):
        raise ValueError("duplicate/empty T0 cases")
    header = dict(schema="t0_inputs/1", model=cfg.id, run_id=identifier(run_id),
                  config=cfg.to_dict(), config_sha256=config_sha256(cfg.to_dict()),
                  fixture_sha256=sha256_file(fixture_path))
    write_lines(path, header, [r.to_dict() for r in entries])
    return load(path)


def as_case(row):
    return T0Case(row.case_id, request_from(row.body), row.reference_envelope_sha256, row.boundary)


def load(path):
    header, raw = read_lines(path)
    if header.get("schema") != "t0_inputs/1" or config_sha256(header["config"]) != header["config_sha256"]:
        raise ValueError("T0 inputs configuration mismatch")
    rows = [T0Input.from_dict(r) for r in raw]
    if not rows or len({r.case_id for r in rows}) != len(rows):
        raise ValueError("duplicate/empty T0 cases")
    for row in rows:
        identifier(row.case_id)
        request, ref = request_from(row.body), request_from(row.reference_body)
        if (request.body != row.body or ref.body != row.reference_body
                or request.request_sha256 != ref.request_sha256 or request.request_sha256 != row.request_sha256
                or request.envelope_sha256 != row.envelope_sha256 or ref.envelope_sha256 != row.reference_envelope_sha256):
            raise ValueError("T0 inputs request hash mismatch")
        _lengths(row.lengths)
        if row.boundary is not None and row.boundary.lengths != row.lengths:
            raise ValueError("T0 boundary lengths mismatch")
    return T0Inputs(header, rows, sha256_file(path))
