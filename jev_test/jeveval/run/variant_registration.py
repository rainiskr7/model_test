"""무엇: 확신 등록 사슬 검사 · 입력: 증거/dev 재계산 · 출력: 등록 상태/봉인 · 계약 §7-4d."""

from jeveval.score.isotonic import apply_isotonic
from jeveval.score.threshold import TAUS
from jeveval.score.variant_scores import CANDIDATES
from jeveval.types import Threshold
from jeveval.run import variant_calculation

IDENTITY = ("model", "set", "variant", "run_id")


def check_development(evidence, dev, *, sealed):
    """gate와 운영 상태기가 같은 dev 재계산·등록 판정을 사용한다."""
    recomputed = variant_calculation.development(dev)
    return check(evidence, recomputed, sealed=sealed)


def seal_fields(evidence):
    """봉인은 정책 전체 바이트와 fingerprint를 결합한다."""
    q = evidence["artifacts"]["variant_threshold.json"]
    return dict(schema="variant_seal/1", **{k: q[k] for k in IDENTITY},
                variant_threshold_sha256=evidence["hashes"]["variant_threshold.json"],
                fingerprint_sha256=evidence["hashes"]["fingerprint.json"])


def _threshold(e):
    q, fp = (e["artifacts"][n] for n in ("variant_threshold.json", "fingerprint.json"))
    if q["schema"] != "variant_threshold/1" or any(q[k] != fp[k] for k in IDENTITY):
        raise ValueError("variant identity")
    if (q["fingerprint_sha256"] != e["hashes"]["fingerprint.json"] or q["manifest"] != e["manifest"] or
            q["manifest_sha256"] != e["manifest_sha256"] or q["dev_final_sha256"] != e["hashes"]["dev/final.jsonl"] or
            q["threshold_sha256"] != e["hashes"]["threshold.json"] or e["policy"]["status"] != "registered"):
        raise ValueError("variant evidence")
    if set(q["by_tau"]) != set(TAUS):
        raise ValueError("variant taus")
    for tau, choice in q["by_tau"].items():
        t = Threshold.from_dict(choice["threshold"])
        if choice["candidate"] not in CANDIDATES or t.tau != tau:
            raise ValueError("variant selection")
    for fitted in q["calibrators"].values():
        apply_isotonic(fitted, .5)


def check(e, recomputed=None, *, sealed=True):
    """선언 누락과 손상을 구분하며 timestamp를 등록 근거로 쓰지 않는다."""
    a = e["artifacts"]
    if not e["errors"] and e["manifest"] is None and not any(
            n in a for n in ("variant_threshold.json", "test/variant_seal.json")):
        return "exploratory"
    try:
        if e["errors"]:
            raise ValueError("variant inputs")
        _threshold(e)
        if recomputed is not None and any(a["variant_threshold.json"][k] != v for k, v in recomputed.items()):
            raise ValueError("variant dev recomputation")
        if sealed:
            expected = seal_fields(e)
            if any(a["test/variant_seal.json"].get(k) != v for k, v in expected.items()):
                raise ValueError("variant seal")
            seal = a["test/seal.json"]
            if (seal["dev_final_sha256"] != e["hashes"]["dev/final.jsonl"] or
                    seal["threshold_sha256"] != e["hashes"]["threshold.json"]):
                raise ValueError("main seal")
        return "registered"
    except (ValueError, KeyError, TypeError, AttributeError):
        return "registration_damaged"
