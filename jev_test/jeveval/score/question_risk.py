"""무엇: 탐색적 질문 위험 · 입력: 질문 관측 · 출력: question_risk/1 통계 · 계약 §7-4b."""

from jeveval.score import risk
from jeveval.score.question_outcomes import align
from jeveval.score.threshold import TAUS, select
from jeveval.types import RequestOutcome


def _request(row):
    return RequestOutcome(row.logical_id, row.group_id, row.stage, row.status, row.valid,
                          not row.present or row.gold is None, row.confidence, row.wrong,
                          {row.question_id: row.gold}, None if row.answer is None else {row.question_id: row.answer},
                          row.length_max, row.meta, {row.question_id: row.role})


def counts(rows):
    """미존재·MISSING·false·NONE과 무효는 구별한다. 무효 유라벨은 분모에 남는다."""
    return dict(n_groups=len(rows), n_absent=sum(not r.present for r in rows),
                n_missing=sum(r.present and r.gold is None for r in rows),
                n_denom=sum(r.present and r.gold is not None for r in rows),
                n_invalid=sum(r.present and r.gold is not None and not r.valid for r in rows),
                n_false=sum(r.gold == "false" for r in rows), n_none=sum(r.gold == "NONE" for r in rows))


def apply(test, tau, t):
    """봉인된 임계값을 시험 관측에만 적용한다."""
    accepted = [r for r in test if t is not None and r.present and r.gold is not None and r.valid and r.confidence >= t]
    n, k = (None, None) if t is None else (len(accepted), sum(int(r.wrong) for r in accepted))
    u = None if t is None else risk.upper(k, n)
    status = risk.cell_status(tau, t, n, u)
    return dict(t_star=t, n_accepted=n, k_errors=k, U=u, status=status,
                coverage=dict(num=n or 0, den=counts(test)["n_denom"]))


def cell(dev, test, tau):
    return apply(test, tau, select([_request(r) for r in dev], tau).t_star)


def thresholds(dev):
    """개발 관측만으로 질문별 고정 τ의 임계값을 선택한다."""
    return {qid: {tau: select([_request(r) for r in dev if r.question_id == qid], tau).t_star
                  for tau in TAUS} for qid in sorted({r.question_id for r in dev})}


def calculate(dev, test, frozen=None):
    """질문마다 하나의 대표만 허용하고 주/진단 표를 분리한다."""
    dev, test = align(dev, test)
    for name, rows in (("dev", dev), ("test", test)):
        keys = [(r.group_id, r.question_id) for r in rows]
        ids = [(r.logical_id, r.question_id) for r in rows]
        if any(r.stage != name for r in rows) or len(set(keys)) != len(keys) or len(set(ids)) != len(ids):
            raise ValueError("expected unique stage representatives per question")
    if frozen is not None and set(frozen) != {r.question_id for r in [*dev, *test]}:
        raise ValueError("registered question scope differs")
    tables = dict(questions={}, diagnostic={})
    for qid in sorted({r.question_id for r in [*dev, *test]}):
        development, trial = ([r for r in rows if r.question_id == qid] for rows in (dev, test))
        header = next(iter(development or trial))
        table = tables["questions" if header.role == "success" else "diagnostic"]
        table[qid] = dict(role=header.role, label=header.label, type=header.qtype,
                         denominator=dict(dev=counts(development), test=counts(trial)),
                         by_tau={tau: (cell(development, trial, tau) if frozen is None else
                                      apply(trial, tau, frozen[qid][tau])) for tau in TAUS})
    return tables
