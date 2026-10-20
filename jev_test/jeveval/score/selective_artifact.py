"""무엇: 보조 통계 파일 계약 · 입력: 집계/출처 · 출력: selective/1·검증 · 계약 §7-4c."""

import math

from jeveval.score.selective import statistics
from jeveval.score.power import power_table

IDENTITY = ("model", "set", "variant", "run_id")
VERSION = "tied-partial-1"


def build(rows, identity, evidence, risk):
    """원문·개별 점수·ID를 보조 공개 산출물에 넣지 않는다."""
    return dict(schema="selective/1", **identity, definition_version=VERSION,
                inputs=dict(evidence), power=power_table(risk), **statistics(rows))


def validate(value, identity, hashes, risk):
    """다른 run·입력·불가능한 수치를 거부한다. 원기록 재계산은 oracle의 책임이다."""
    if value["schema"] != "selective/1" or value["definition_version"] != VERSION:
        raise ValueError("selective definition")
    if any(value[k] != identity[k] for k in IDENTITY):
        raise ValueError("selective identity")
    if value["inputs"] != {p: hashes[p] for p in ("risk.json", "test/final.jsonl")}:
        raise ValueError("selective evidence")
    d, n, invalid = (value[k] for k in ("n_denom", "n_valid", "n_invalid"))
    if any(type(x) is not int or x < 0 for x in (d, n, invalid)) or n + invalid != d:
        raise ValueError("selective counts")
    if any(c["test"]["n_denom"] != d for c in risk["cells"].values()):
        raise ValueError("selective denominator")
    for key in ("max_coverage", "partial_aurc", "auroc"):
        _probability(value[key])
    if value["max_coverage"] != (n / d if d and n else None):
        raise ValueError("selective maximum")
    if not n and any(value[k] is not None for k in ("partial_aurc", "auroc")):
        raise ValueError("empty selective metric")
    if n and (value["partial_aurc"] is None or value["partial_aurc"] > n / d):
        raise ValueError("selective area")
    _grid(value["grid"], d, n)
    if value["power"] != power_table(risk):
        raise ValueError("selective power")


def _probability(value):
    if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1):
        raise ValueError("selective probability")


def _grid(grid, denom, valid):
    if len(grid) != 10:
        raise ValueError("selective grid")
    previous = errors = 0
    for tenth, cell in enumerate(grid, 1):
        for key in ("target", "coverage", "risk"):
            _probability(cell[key])
        if cell["target"] != tenth / 10:
            raise ValueError("selective target")
        if not valid:
            if any(cell[k] is not None for k in ("n_accepted", "k_errors", "coverage", "risk")):
                raise ValueError("empty grid")
            continue
        n, k = cell["n_accepted"], cell["k_errors"]
        if (type(n) is not int or type(k) is not int or not previous <= n <= valid or
                not errors <= k <= n or k - errors > n - previous or 10 * n > tenth * denom):
            raise ValueError("grid counts")
        if cell["coverage"] != n / denom or cell["risk"] != (k / n if n else None):
            raise ValueError("grid ratios")
        previous, errors = n, k
    if valid and previous != valid:
        raise ValueError("grid endpoint")
