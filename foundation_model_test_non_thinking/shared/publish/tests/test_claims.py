"""클레임 등급 회귀 테스트.

이 모듈이 지키는 성질은 하나다 — **관측된 불안정으로 설명이 끝나는 우열 주장을
발행하지 않는다.** 그 이상(유의성, 신뢰구간)을 주장하기 시작하면 테스트가 깨진다.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from publish.claims import (  # noqa: E402
    MIN_REPEATS,
    REPEATABILITY_OBSERVED,
    SNAPSHOT,
    comparable,
    credential,
)


def run(run_id, **items):
    return {"run_id": run_id, "items": dict(items)}


class ClaimClass(unittest.TestCase):
    def test_a_single_run_is_a_snapshot(self):
        # 소급 무효화가 아니다. "이 날짜에 이 숫자를 냈다"는 여전히 참이고,
        # 비교의 증거가 아닐 뿐이다.
        cred = credential([run("r1", a=True, b=False)])
        self.assertEqual(cred["claim_class"], SNAPSHOT)
        self.assertEqual(cred["k"], 1)

    def test_two_runs_are_still_a_snapshot(self):
        # 2런은 뒤집힘의 존재만 알려주고 다수결을 만들지 못한다(1:1 은 과반이 없다).
        cred = credential([run("r1", a=True), run("r2", a=False)])
        self.assertEqual(cred["claim_class"], SNAPSHOT)
        self.assertEqual(MIN_REPEATS, 3)

    def test_three_runs_earn_repeatability_observed(self):
        cred = credential([run(f"r{i}", a=True, b=False) for i in range(3)])
        self.assertEqual(cred["claim_class"], REPEATABILITY_OBSERVED)
        self.assertEqual(cred["majority_passed"], 1)
        self.assertEqual(cred["unstable_items"], [])

    def test_no_runs_is_a_snapshot_not_a_crash(self):
        self.assertEqual(credential([])["claim_class"], SNAPSHOT)


class TheCounterexampleThatKillsScalarSpread(unittest.TestCase):
    """건수 산포가 0인데 항목이 뒤집히는 경우.

    실측: 어떤 모델이 통과 건수 553 을 5런 내내 냈는데 통과 항목 10개가 뒤집혔다.
    표본표준편차는 0 이다. s=0 을 σ=0 으로 읽으면 그 모델은 "완벽한 재현"으로
    발행되고, 어떤 차이든 무한대로 유의해진다.
    """

    def _runs(self):
        # 매 런 통과 2개로 동일하지만 어느 항목이 통과했는지는 다르다.
        return [
            run("r1", a=True, b=True, c=False, d=False),
            run("r2", a=True, b=False, c=True, d=False),
            run("r3", a=True, b=False, c=False, d=True),
        ]

    def test_the_pass_count_alone_says_perfect_reproduction(self):
        cred = credential(self._runs())
        self.assertEqual(cred["count_range"], [2, 2], "건수만 보면 산포가 0이다")

    def test_the_envelope_is_not_zero_because_items_flipped(self):
        cred = credential(self._runs())
        lo, hi = cred["instability_envelope"]
        self.assertGreater(hi - lo, 0, "뒤집힘이 있는데 예산이 0이면 반례를 놓친다")
        self.assertEqual(sorted(cred["unstable_items"]), ["b", "c", "d"])

    def test_a_truly_identical_cohort_has_a_zero_width_envelope(self):
        cred = credential([run(f"r{i}", a=True, b=False) for i in range(4)])
        lo, hi = cred["instability_envelope"]
        self.assertEqual(hi - lo, 0, "뒤집힘이 없으면 예산도 0이어야 한다")


class Comparability(unittest.TestCase):
    def _stable(self, run_id_prefix, passing, total=10, k=3):
        items = {f"i{n}": n < passing for n in range(total)}
        return credential([{"run_id": f"{run_id_prefix}{i}", "items": items} for i in range(k)])

    def test_a_snapshot_can_never_win_a_comparison(self):
        # 1회 실행 숫자가 순위표에 오르던 것이 이 저장소의 결함이었다.
        snap = credential([run("r1", a=True)])
        strong = self._stable("s", 10)
        got = comparable(snap, strong)
        self.assertFalse(got["comparable"])
        self.assertIn("snapshot", got["reason"])

    def test_overlapping_envelopes_refuse_the_claim(self):
        # 차이가 관측된 흔들림으로 설명되면 우열을 발행하지 않는다.
        a = credential([
            run("a1", **{"i0": True, "i1": True, "i2": False}),
            run("a2", **{"i0": True, "i1": False, "i2": True}),
            run("a3", **{"i0": True, "i1": True, "i2": False}),
        ])
        b = credential([
            run("b1", **{"i0": True, "i1": False, "i2": True}),
            run("b2", **{"i0": True, "i1": True, "i2": False}),
            run("b3", **{"i0": True, "i1": False, "i2": True}),
        ])
        got = comparable(a, b)
        self.assertFalse(got["comparable"])
        self.assertIn("겹친다", got["reason"])

    def test_disjoint_envelopes_allow_the_claim_and_name_the_winner(self):
        weak, strong = self._stable("w", 2), self._stable("s", 9)
        got = comparable(strong, weak)
        self.assertTrue(got["comparable"])
        self.assertEqual(got["winner"], "left")

    def test_different_coverage_is_never_comparable(self):
        # 채점 항목 수가 다르면 같은 측정이 아니다.
        got = comparable(self._stable("a", 5, total=10), self._stable("b", 5, total=20))
        self.assertFalse(got["comparable"])
        self.assertIn("커버리지", got["reason"])

    def test_a_refused_comparison_does_not_mean_the_models_are_equal(self):
        # 문구가 동등을 주장하면 안 된다 — 이 반복 횟수로 판정할 수 없다는 뜻이다.
        a = self._stable("a", 5)
        got = comparable(a, a)
        self.assertFalse(got["comparable"])
        self.assertNotIn("같다", got["reason"])
        self.assertNotIn("동등", got["reason"])


class ItNeverClaimsSignificance(unittest.TestCase):
    def test_the_source_makes_no_statistical_claim(self):
        source = (Path(__file__).resolve().parents[1] / "claims.py").read_text(encoding="utf-8")
        for forbidden in ("p_value", "p-value 를 계산", "confidence_interval", "stddev", "t_test"):
            self.assertNotIn(forbidden, source, f"통계적 주장을 하고 있다: {forbidden}")

    def test_the_comparable_reason_disclaims_significance(self):
        strong, weak = None, None
        items_s = {f"i{n}": n < 9 for n in range(10)}
        items_w = {f"i{n}": n < 2 for n in range(10)}
        strong = credential([{"run_id": f"s{i}", "items": items_s} for i in range(3)])
        weak = credential([{"run_id": f"w{i}", "items": items_w} for i in range(3)])
        got = comparable(strong, weak)
        self.assertIn("통계적 유의성이 아니라", got["reason"])


class CoverageDifferencesAreNotInstability(unittest.TestCase):
    def test_items_missing_from_one_run_are_dropped_and_recorded(self):
        # 조용히 합집합을 쓰면 커버리지 차이가 불안정으로 둔갑한다.
        cred = credential([
            run("r1", a=True, b=True),
            run("r2", a=True, b=True),
            run("r3", a=True),
        ])
        self.assertEqual(cred["measured_items"], 1)
        self.assertEqual(cred["coverage_dropped"], ["b"])
        self.assertEqual(cred["unstable_items"], [])


if __name__ == "__main__":
    unittest.main()
