"""무엇: 역사 집계 구조·연결 검증 · 입력: schema 객체들 · 출력: 오류/없음 · 계약 §5-1b; 순수."""

from jeveval.score.threshold import TAUS
from jeveval.types import RiskCell


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError("invalid historical count")


def _ratio(ratio):
    _count(ratio["num"])
    _count(ratio["den"])
    if ratio["num"] > ratio["den"]:
        raise ValueError("invalid historical ratio")


def validate(artifacts, hashes):
    threshold = artifacts.get("threshold.json")
    risk = artifacts.get("risk.json")
    scores = artifacts.get("scores.json")
    if threshold is not None:
        if set(threshold["by_tau"]) != set(TAUS):
            raise ValueError("threshold TAUS mismatch")
        if "dev/final.jsonl" in hashes and threshold["dev_input"]["sha256"] != hashes["dev/final.jsonl"]:
            raise ValueError("threshold dev input hash mismatch")
    if risk is not None:
        for tau, value in risk["cells"].items():
            cell = RiskCell.from_dict(value)
            if cell.tau != tau or cell.status not in ("MEETS", "FAILS", "UNDERPOWERED", "NO_THRESHOLD"):
                raise ValueError("invalid risk cell")
            if threshold is not None and cell.t_star != threshold["by_tau"][tau]["t_star"]:
                raise ValueError("risk threshold differs")
            for counts in (cell.dev, cell.test):
                _count(counts["n_groups"])
                _count(counts["n_denom"])
                if "coverage" in counts:
                    _ratio(counts["coverage"])
                    if counts["coverage"] != dict(num=counts["n_accepted"] or 0, den=counts["n_denom"]):
                        raise ValueError("risk coverage/count mismatch")
                if counts["n_accepted"] is not None:
                    _count(counts["n_accepted"])
                    _count(counts["k_errors"])
                    if not counts["k_errors"] <= counts["n_accepted"] <= counts["n_denom"] <= counts["n_groups"]:
                        raise ValueError("inconsistent risk counts")
    if scores is not None:
        for population in scores["populations"].values():
            for question in population["questions"].values():
                _ratio(question["accuracy"])
                for stats in question["classes"].values():
                    for key in ("support", "predicted", "tp"):
                        _count(stats[key])
