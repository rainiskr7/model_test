"""무엇: T0 허용폭/판정 단계 조립 · 입력: 검증된 단계 파일 · 출력: 원문 없는 결과 · 계약 §8-7 T-e/f/h."""

from pathlib import Path

from jeveval.io import t0_chain
from jeveval.io.run_files import read_json, write_json
from jeveval.io.t0_inputs import as_case
from jeveval.t0.judge import judge
from jeveval.t0.record import build_record
from jeveval.t0.response import validate_response
from jeveval.t0.rounding import epsilon, parse
from jeveval.t0.samples import targets
from jeveval.t0.tolerance import measure
from jeveval.types.t0 import T0Tolerance, T0Variant


def _provenance(directory, bundle):
    return dict(inputs_sha256=bundle.sha256,
                reference_sha256=t0_chain.digest(directory / "reference.jsonl"),
                variants_sha256=t0_chain.digest(directory / "variants.jsonl"))


def tolerance(directory, bundle, rounding=None):
    directory = Path(directory)
    policy = parse(rounding)
    t0_chain.fingerprint(directory, bundle)
    t0_chain.observations(directory, bundle, "reference")
    header, records = t0_chain.variants(directory, bundle)
    result = {}
    for row in bundle.rows:
        if row.boundary is not None:
            continue
        questions = row.body["questions"]
        samples = [T0Variant(r["variant"], r["repeat"], r["target_sha256"],
                   validate_response(r["response_raw"] if r["error"] is None else "", questions,
                                     epsilon(policy["reference"])))
                   for r in records if r["case_id"] == row.case_id]
        measured = measure(questions, samples, family=bundle.metadata["model"],
            epsilon_r=epsilon(policy["reference"]), target_sha256=targets(row),
            batch_one_equal=header["batch_one_equal"])
        result[row.case_id] = {qid: value.to_dict() for qid, value in measured.items()}
    record = dict(schema="t0_tolerance/1", **_provenance(directory, bundle),
                  rounding=policy["reference"], reason=header["reason"], cases=result)
    write_json(directory / "tolerance.json", record)
    return dict(ok=True, cases=len(result))


def evaluate(directory, bundle, rounding=None, no_reference=False):
    directory = Path(directory)
    policy = parse(rounding)
    t0_chain.fingerprint(directory, bundle)
    refs = t0_chain.observations(directory, bundle, "reference")
    servers = t0_chain.observations(directory, bundle, "server")
    t0_chain.variants(directory, bundle)
    measured = read_json(directory / "tolerance.json")
    if measured.get("schema") != "t0_tolerance/1" or any(
            measured[k] != v for k, v in _provenance(directory, bundle).items()):
        raise ValueError("T0 tolerance provenance mismatch")
    if policy["reference"] is not None and measured["rounding"] != policy["reference"]:
        raise ValueError("T0 tolerance rounding policy mismatch")
    tolerances = {cid: {qid: T0Tolerance.from_dict(t) for qid, t in qs.items()}
                  for cid, qs in measured["cases"].items()}
    result = judge([as_case(r) for r in bundle.rows], refs, servers, tolerances,
                   inputs_sha256=bundle.sha256, reference_epsilon=epsilon(policy["reference"]),
                   server_epsilon=epsilon(policy["server"]), has_reference=not no_reference)
    record = build_record(model=bundle.metadata["model"], run_id=bundle.metadata["run_id"],
        model_yaml_dict=bundle.metadata["config"], judgement=result, inputs_sha256=bundle.sha256,
        tolerance_sha256=t0_chain.digest(directory / "tolerance.json"),
        temperature=dict(path="real", status="NOT_RUN", evidence_sha256=None))
    record.update(rounding=policy, **{k: v for k, v in _provenance(directory, bundle).items()
                                    if k != "inputs_sha256"},
                  server_sha256=t0_chain.digest(directory / "server.jsonl"),
                  fingerprint_sha256=t0_chain.digest(directory / "fingerprint.json"))
    write_json(directory / "t0.json", record)
    return dict(ok=True, status=result.status, n_expected_cases=result.n_expected_cases,
                n_expected_questions=result.n_expected_questions)
