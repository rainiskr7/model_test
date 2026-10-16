"""무엇: T0 공개 참조와 변형 단계 · 입력: 확정 inputs/참조 런타임 · 출력: 비공개 관측 · 계약 §8-7 T-d/h."""

from pathlib import Path

from jeveval.io import t0_chain, t0_fingerprint
from jeveval.io.hashes import sha256_file
from jeveval.io.t0_files import write_lines
from jeveval.reference.t0_runner import respond
from jeveval.reference.variants import batch, placed
from jeveval.t0.request import canonical_bytes
from jeveval.t0.samples import observation, targets


def _public(bundle, runtime):
    records, responses = [], {}
    for row in bundle.rows:
        try:
            result = respond(runtime, row.reference_body)
            raw = canonical_bytes(result).decode()
            responses[row.case_id] = result
            record = observation(row, bundle.sha256, 200, raw, reference=True)
        except Exception:
            record = observation(row, bundle.sha256, None, "", reference=True, error="reference_failure")
        records.append(record.to_dict())
    return records, responses


def _batch_one(rows, runtime, public):
    if runtime.family == "pplx_v1_1":
        return True, None
    try:
        equal = all(canonical_bytes(batch(runtime, [row.reference_body], 1)[0]) ==
                    canonical_bytes(public[row.case_id]) for row in rows)
        return equal, None if equal else "batch_one_mismatch"
    except Exception:
        return False, "batch_one_unavailable"


def _variant(runtime, row, variant, companions):
    body = row.reference_body
    if runtime.family == "pplx_v1_1":
        answers = {}
        for qid in body["questions"]:
            result = respond(runtime, placed(body, qid, variant, companions))
            answers[qid] = result["answers"][qid]
        return dict(answers=answers)
    size = int(variant.rsplit("_", 1)[1])
    # 요청을 배치 k의 첫 위치에 놓고 다른 fixture 요청으로 나머지를 채운다.
    others = companions or [body]
    requests = [body] + [others[i % len(others)] for i in range(size - 1)]
    return batch(runtime, requests, size)[0]


def _samples(bundle, runtime, rows, policy):
    records = []
    for row in rows:
        companions = [r.reference_body for r in rows if r.case_id != row.case_id]
        for variant in policy.variants[runtime.family]:
            for repeat in range(policy.repeats):
                raw, error = "", None
                try:
                    raw = canonical_bytes(_variant(runtime, row, variant, companions)).decode()
                except Exception:
                    error = "variant_failure"
                records.append(dict(case_id=row.case_id, inputs_sha256=bundle.sha256,
                    request_sha256=row.request_sha256, envelope_sha256=row.reference_envelope_sha256,
                    target_sha256=targets(row), variant=variant, repeat=repeat, response_raw=raw, error=error))
    return records


def execute(directory, bundle, runtime, checkpoint, device, policy):
    directory = Path(directory)
    t0_chain.policy(bundle, policy)
    if runtime.family != bundle.metadata["model"]:
        raise ValueError("reference family mismatch")
    records, public = _public(bundle, runtime)
    normal = [r for r in bundle.rows if r.boundary is None]
    equal, reason = _batch_one(normal, runtime, public)
    # 불일치가 하나라도 있으면 그 모델 전체 변형을 unmeasured로 남긴다.
    samples = _samples(bundle, runtime, normal, policy) if equal else []
    header = dict(schema="t0_reference/1", inputs_sha256=bundle.sha256)
    write_lines(directory / "reference.jsonl", header, records)
    header = dict(schema="t0_variants/1", inputs_sha256=bundle.sha256, family=runtime.family,
                  reference_sha256=sha256_file(directory / "reference.jsonl"),
                  tolerance_policy_sha256=policy.sha256, batch_one_equal=equal, reason=reason)
    write_lines(directory / "variants.jsonl", header, samples)
    t0_fingerprint.add_reference(directory, bundle, runtime, checkpoint, device)
    return dict(ok=True, cases=len(records), variants=len(samples), reason=reason)
