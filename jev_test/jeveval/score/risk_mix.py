"""무엇: 위험 세부 분포 · 입력: 시험 outcome·Item·수락 ID · 출력: 집계 dict · 계약 §7-4·§8-6 D."""


from jeveval.types.length_buckets import LENGTH_LIMITS
from jeveval.score.set_metrics import MetricSpec

LENGTH_BUCKETS = ("le_4096", "le_8192", "le_16384", "gt_16384", "unmeasured")


def length_bucket(n):
    """run.length와 같은 경계이며 미측정은 별도 칸이다 (⑥a-2a R1)."""
    if n is None:
        return "unmeasured"
    if type(n) is not int or n < 0:
        raise ValueError("length must be a nonnegative integer")
    for limit in LENGTH_LIMITS:
        if n <= limit:
            return f"le_{limit}"
    return "gt_16384"


def _add(table, key, accepted, wrong):
    cell = table.setdefault(key, dict(sampled=0, n=0, k=0))
    cell["sampled"] += 1
    cell["n"] += int(accepted)
    cell["k"] += int(accepted and wrong)


def distributions(test, test_items, accepted_ids, *, spec: MetricSpec):
    """빈 마스크를 제외하고 요청 오류를 모든 소속 칸에 센다. 진단은 질문 오류다."""
    mix = dict(by_class={}, by_service={} if test_items and spec.mix_service else None,
               by_stratum={} if test_items and spec.mix_stratum else None, by_n_questions={})
    lengths = {key: dict(sampled=0, n_valid=0, n=0, k=0) for key in LENGTH_BUCKETS}
    diagnostic = {}
    for row in test:
        if row.mask_empty:
            continue
        accepted = row.logical_id in accepted_ids
        bucket = lengths[length_bucket(row.length_max)]
        if row.length_max is None and row.valid:
            raise ValueError("valid outcome requires measured length")
        bucket["sampled"] += 1
        bucket["n_valid"] += int(row.valid)
        bucket["n"] += int(accepted)
        bucket["k"] += int(accepted and row.wrong)
        success = [qid for qid, role in row.roles.items() if role == "success"]
        _add(mix["by_n_questions"], str(len(success)), accepted, row.wrong)
        for qid in success:
            if row.gold[qid] is not None:
                _add(mix["by_class"].setdefault(qid, {}), row.gold[qid], accepted, row.wrong)
        if spec.mix_service:
            for service in set(row.meta["service"] or []):
                _add(mix["by_service"], service, accepted, row.wrong)
        if spec.mix_stratum:
            _add(mix["by_stratum"], row.meta["stratum"], accepted, row.wrong)
        for qid, role in row.roles.items():
            if role == "diagnostic" and row.gold[qid] is not None:
                cell = diagnostic.setdefault(qid, dict(n=0, wrong=0))
                if accepted:
                    cell["n"] += 1
                    cell["wrong"] += int(row.answer[qid] != row.gold[qid])
    assert sum(cell["sampled"] for cell in lengths.values()) == sum(not r.mask_empty for r in test)
    return mix, lengths, diagnostic
