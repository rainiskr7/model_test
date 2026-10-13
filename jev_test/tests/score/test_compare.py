"""무엇: C4·공통 코호트 검증 · 입력: 기존 코호트 fixture · 출력: 오류·비교 파일 · 계약 §7-6·8-6 L."""

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

import pytest

from jeveval.score.compare import check_comparable, common_cohort, compare_file
from jeveval.score.population import population
from tests.score.population_support import answer, fixture, population_args, question, record


def test_fixture_exact_intersection_and_all_rows():
    data = fixture("cohort_population.json")
    template = record([question("q")], {"q": answer()})[2]
    models = {m: [replace(template, logical_id=g, status=s) for g, s in rows.items()]
              for m, rows in data["models"].items()}
    assert common_cohort(models, "test") == data["expected"]["common_cohort"]
    fc = data["functionchat"]
    rows = [replace(template, logical_id=i, stage=stage, status=fc["statuses"][i])
            for stage in ("dev", "test", "extra") for i in fc[stage]]
    assert common_cohort(dict(a=rows, b=rows), "test") == ["i4"]
    assert common_cohort(dict(a=rows, b=rows), "all_rows") == ["i1", "i2", "i4"]
    assert common_cohort({}) == []


@pytest.mark.parametrize("field", ["split_sha256", "task_sha256", "test_logical_ids"])
def test_c4_refuses_mismatch_without_intersection(field):
    meta = dict(split_sha256="s", task_sha256="t", test_logical_ids=["a", "b"])
    models = dict(a=deepcopy(meta), b=deepcopy(meta))
    assert check_comparable(models) == []
    models["b"][field] = ["a"] if field == "test_logical_ids" else "changed"
    before = deepcopy(models)
    assert any(field in error for error in check_comparable(models))
    assert models == before


def test_c4_order_duplicates_missing_and_compare_serialization():
    meta = dict(split_sha256="s", task_sha256="t", test_logical_ids=["a", "b"])
    assert check_comparable(dict(a=meta, b=dict(meta, test_logical_ids=["b", "a"]))) == []
    assert check_comparable(dict(a=meta, b=dict(meta, test_logical_ids=["a", "a", "b"])))
    assert check_comparable(dict(a=meta, b={}))
    records = [record([question("q")], {"q": answer()}, gid=g) for g in ("b", "a")]
    pop = population(**population_args(records))
    ids = [r[1].logical_id for r in records]
    output = compare_file(models=["z", "a"], set="s", variant="v", cohort_ids=ids,
                          per_model_population=dict(z=pop, a=pop), bootstrap={"x": []},
                          t0_status=dict(z="partial", a="passed"))
    assert output["models"] == ["a", "z"] and output["schema"] == "compare/1"
    assert output["t0_status"] == dict(a="passed", z="partial")
    assert output["t0_not_passed"] == ["z"]
    assert output["common_cohort"]["logical_ids_sha256"] == sha256("\n".join(sorted(ids)).encode()).hexdigest()
    assert output["common_cohort"]["per_model"]["a"] == pop.to_dict()
    output["common_cohort"]["per_model"]["a"]["counts"]["n_sampled"] = 100
    assert pop.counts["n_sampled"] == 2


def test_reject_invalid_cohort_inputs():
    row = record([question("q")], {"q": answer()})[2]
    with pytest.raises(ValueError, match="duplicate"):
        common_cohort(dict(a=[row, row]))
    with pytest.raises(ValueError, match="stage_filter"):
        common_cohort({}, "dev")
