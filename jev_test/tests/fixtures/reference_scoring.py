"""무엇: 독립 수치 참조 · 입력: 합성 관측 · 출력: 기대 집계 · 계약 §7-1·§7-5."""

import math
from fractions import Fraction


def threshold_reference(rows, tau):
    eligible = [r for r in rows if r['valid'] and not r['mask_empty']]
    denominator = sum(not r['mask_empty'] for r in rows)
    selected = None
    for t in sorted({r['s'] for r in eligible}, reverse=True):
        accepted = [r for r in eligible if r['s'] >= t]
        n, k = len(accepted), sum(r['wrong'] for r in accepted)
        if Fraction(k, n) <= Fraction(tau) / 2:
            if selected is None or n > selected[0]:
                selected = (n, k, t)
    n, k, t = selected if selected else (None, None, None)
    return dict(tau=tau, status='SELECTED' if selected else 'NO_THRESHOLD',
                t_star=t, n_accepted=n, k_errors=k,
                coverage={'num':n or 0, 'den':denominator})


def calibration_reference(rows):
    bins = []
    for i in range(15):
        lo, hi = i / 15, (i + 1) / 15
        members = [r for r in rows if lo <= r['confidence'] and
                   (r['confidence'] < hi or i == 14 and r['confidence'] == 1)]
        n = len(members)
        bins.append(dict(index=i, lo=lo, hi=hi, n=n,
                         acc=sum(r['answer'] == r['gold'] for r in members)/n if n else None,
                         conf=math.fsum(r['confidence'] for r in members)/n if n else None))
    n = len(rows)
    ece = sum(b['n'] * abs(b['acc'] - b['conf']) for b in bins if b['n'])/n if n else None
    brier = math.fsum(p*p - 2*p*(k == r['gold']) + (k == r['gold'])
                      for r in rows for k, p in r['probs'].items())/n if n else None
    loss = math.fsum(-math.log(min(1, max(1e-12, r['probs'][r['gold']])))
                     for r in rows)/n if n else None
    return dict(ece=ece, bins=bins, brier=brier, log_loss=loss)


def f1_reference(gold, answers):
    classes = {}
    for cls in sorted(set(gold) | set(answers)):
        support, predicted = gold.count(cls), answers.count(cls)
        tp = sum(g == a == cls for g, a in zip(gold, answers))
        classes[cls] = dict(support=support, predicted=predicted, tp=tp,
                            recall={'num':tp, 'den':support},
                            precision={'num':tp, 'den':predicted})
    fs = {k:2*v['tp']/(v['support']+v['predicted']) for k,v in classes.items()}
    return classes, fs, sum(fs.values())/len(fs) if fs else None
