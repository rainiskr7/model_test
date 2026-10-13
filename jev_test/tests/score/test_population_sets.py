"""무엇: 셋별 모집단 통합 · 입력: 코호트/KoSGD fixture · 출력: 칸·pooled·도구 점수 · 계약 §7-6."""

import pytest

from jeveval.score.population import population
from tests.score.population_support import answer, fixture, population_args, question, record
from tests.score.test_population import assert_calibration


def test_functionchat_test_vs_all_rows_fixture():
    data = fixture("cohort_population.json")
    fc, records = data["functionchat"], []
    for stage in ("dev", "test", "extra"):
        for iid in fc[stage]:
            group = next(g for g, ids in fc["groups"].items() if iid in ids)
            is_call = iid in ("i1", "i4")
            qs = [question("action", "call" if is_call else "slot", "fc:type_of_output",
                           {"call": "call", "slot": "slot", "relevance": "relevance"}),
                  question("tool", "fn" if is_call else "NONE", "fc:tool", {"fn": "fn", "NONE": "none"})]
            parsed = {q.id: answer(q.gold, {k: float(k == q.gold) for k in q.options}, 1) for q in qs}
            records.append(record(qs, parsed, set_name="fc_call_decision", gid=group, iid=iid,
                                  stage=stage, status=fc["statuses"][iid]))
    for name, expected in data["expected"]["functionchat"].items():
        selected = records if name == "all_rows" else [r for r in records if r[2].stage == "test"]
        result = population(**population_args(selected, "fc_call_decision", expected["certified"], expected["unit"]))
        assert result.certified == expected["certified"] and result.unit == expected["unit"]
        assert result.counts["n_sampled"] == expected["n_sampled"]
        assert result.request["n_scored"] == expected["n_scored"]
        assert result.questions["tool"].macro_f1 is None
        assert result.set_specific["tool_acc_on_call"] == dict(num=2 if name == "all_rows" else 1,
                                                             den=2 if name == "all_rows" else 1)
        assert result.set_specific["none_acc_on_noncall"] == dict(num=int(name == "all_rows"), den=int(name == "all_rows"))


def test_korfin_fixture_pools_observations_before_f1_and_calibration():
    data = fixture("cohort_population.json")
    rows, records = data["korfin"]["questions"], []
    for index in range(3):
        qs, parsed = [], {}
        for qid, observations in rows.items():
            if index >= len(observations):
                continue
            obs = observations[index]
            qs.append(question(qid, obs["gold"], "korfin:sentiment", {k: k for k in obs["probs"]}))
            parsed[qid] = answer(obs["answer"], obs["probs"], obs["confidence"])
        records.append(record(qs, parsed, set_name="korfin_asc", gid=str(index),
                              flags=["aspect_not_in_text:aspect_2"]))
    result = population(**population_args(records, "korfin_asc"))
    expected, pooled = data["expected"]["korfin"], result.pooled["aspect"]
    assert pooled.n_scored == expected["pooled"]["n_scored"]
    assert pooled.accuracy == expected["pooled"]["accuracy"]
    assert pooled.macro_f1 == expected["pooled"]["macro_f1"]
    assert_calibration(pooled.calibration, expected["pooled"]["calibration"])
    mean = sum(q.macro_f1 for q in result.questions.values()) / len(result.questions)
    assert mean == expected["question_macro_f1_mean"] and mean != pooled.macro_f1
    assert result.set_specific["aspect_not_in_text"] == dict(n_scored=1, wrong=dict(num=1, den=1))


def test_kosgd_fixture_all_bundles_and_copy_baseline():
    data = fixture("kosgd_slots.json")
    options = {k: k for k in [*data["catalog_order"], "NONE"]}
    for case in data["cases"]:
        qs = [question(f"q{n}", g, f"ongoing_slot_{n}", options)
              for n, g in enumerate(case["expected"]["fixed_gold"], 1)]
        parsed = {q.id: answer(p, {k: float(k == p) for k in options}, 1)
                  for q, p in zip(qs, case["predicted"])}
        copy = case.get("copy_prev", case["expected"]["fixed_gold"])
        entry = record(list(reversed(qs)), parsed, set_name="kosgd", baseline={"copy_prev": copy})
        result = population(**population_args([entry], "kosgd"))
        assert result.set_specific == dict(bundle_correct=dict(num=int(case["expected"]["group_correct"]), den=1),
                                           order_only_bundles=int(case["expected"]["order_only"]),
                                           copy_baseline_bundle_correct=dict(num=int(case["expected"].get("copy_prev_correct", True)), den=1))


def test_kosgd_fixed_slot_brier_counterexample():
    case = fixture("kosgd_slots.json")["counterexample"]
    qs = [question(f"q{n}", g, f"ongoing_slot_{n}", {"b": "b", "a": "a", "NONE": "none"})
          for n, g in enumerate(case["fixed_gold"], 1)]
    parsed = {q.id: answer(p, probs, .99) for q, p, probs in zip(qs, case["predicted"], case["probabilities"])}
    entry = record(qs, parsed, set_name="kosgd", baseline={"copy_prev": case["fixed_gold"]})
    result = population(**population_args([entry], "kosgd"))
    assert [q.calibration["brier"] for q in result.questions.values()] == pytest.approx(case["expected"]["fixed_slot_brier"])
    assert result.request["wrong"] == dict(num=0, den=1)
    assert result.set_specific["order_only_bundles"] == 1
    assert all(q.accuracy == dict(num=0, den=1) for q in result.questions.values())


def test_kosgd_both_missing_excludes_bundles_and_baseline():
    qs = [question(f"q{n}", None, f"ongoing_slot_{n}", {"NONE": "none"}) for n in (1, 2)]
    entry = record(qs, {q.id: answer("NONE", {"NONE": 1}, 1) for q in qs}, set_name="kosgd")
    result = population(**population_args([entry], "kosgd"))
    assert result.set_specific["bundle_correct"] == dict(num=0, den=0)
    assert result.set_specific["copy_baseline_bundle_correct"] == dict(num=0, den=0)
    assert result.counts["n_empty_mask"] == 1
    assert all(q.n_missing == 1 for q in result.questions.values())
