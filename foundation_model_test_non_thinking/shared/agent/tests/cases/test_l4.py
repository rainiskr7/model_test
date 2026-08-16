from _harness import DummyContext, _assert, _assert_close, extra_metrics, level_spec

def test_l4_meaningful_result_predicate():
    _assert(extra_metrics.l4_has_meaningful_result(["x"]) is True, "non-empty list")
    _assert(extra_metrics.l4_has_meaningful_result([]) is False, "empty list")
    _assert(extra_metrics.l4_has_meaningful_result({}) is False, "empty dict")
    _assert(
        extra_metrics.l4_has_meaningful_result({"items": []}) is False,
        "only empty list",
    )
    _assert(
        extra_metrics.l4_has_meaningful_result({"items": [], "documents": [{"id": 1}]}) is True,
        "one non-empty list",
    )
    _assert(
        extra_metrics.l4_has_meaningful_result({"price": 58200}) is True,
        "dict with no list",
    )
    _assert(extra_metrics.l4_has_meaningful_result(None) is False, "None")
    _assert(extra_metrics.l4_has_meaningful_result("") is False, "empty string")



def test_l4_stock_trades_empty_payload_not_meaningful():
    result = {
        "t8454OutBlock": {"rsp_cd": "00000"},
        "t8454OutBlock1": [],
        "rsp_cd": "00000",
        "rsp_msg": "해당자료가 없습니다.",
    }
    _assert(extra_metrics.l4_has_meaningful_result(result) is False, "empty trade payload")



def test_l4_stock_quote_shape_meaningful():
    result = {"t1102OutBlock": {"price": 58200}, "rsp_cd": "00000"}
    _assert(extra_metrics.l4_has_meaningful_result(result) is True, "stock quote payload")



def test_l4_coverage_det_recovers_non_search_shape():
    ctx = DummyContext(
        [{"tool": "StockPrice_ls"}, {"tool": "Geocoding_tmap"}],
        [
            {
                "tool": "StockPrice_ls",
                "success": True,
                "error": None,
                "result": {"t1102OutBlock": {"price": 58200}, "rsp_cd": "00000"},
            }
        ],
    )
    _assert_close(extra_metrics.coverage_det(ctx), 0.5, "Coverage_det non-search recovery")
    vendored = level_spec.vendored_metric("Coverage")(ctx)
    _assert_close(vendored, 0.0, "vendored Coverage misses non-search shape")



def test_l4_source_epr_det_counts_meaningful_calls():
    ctx = DummyContext(
        [{"tool": "StockPrice_ls"}, {"tool": "Geocoding_tmap"}],
        [
            {
                "tool": "StockPrice_ls",
                "success": True,
                "error": None,
                "result": {"t1102OutBlock": {"price": 58200}, "rsp_cd": "00000"},
            },
            {
                "tool": "StockPrice_ls",
                "success": True,
                "error": None,
                "result": {"items": []},
            },
        ],
    )
    _assert_close(extra_metrics.source_epr_det(ctx), 0.25, "SourceEPR_det mixed calls")



def test_l4_spec_shape_and_passk_primary():
    specs = level_spec.LEVEL_SPECS["L4"]
    by_name = {spec.name: spec for spec in specs}
    in_score = [spec for spec in specs if spec.in_score]
    _assert(
        [spec.name for spec in in_score] == ["Coverage_det", "SourceEPR_det"],
        "L4 representative metrics",
    )
    _assert(by_name["Coverage"].in_score is False, "vendored Coverage record-only")
    _assert(by_name["SourceEPR"].in_score is False, "vendored SourceEPR record-only")
    primary = level_spec.PASSK_PRIMARY_METRICS["L4"]
    _assert(primary == "Coverage_det", "L4 PassK_det primary")
    _assert(primary in by_name, "L4 PassK_det primary must resolve")



def test_l4_change_leaves_l6_and_l3_shapes_unchanged():
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L6"] if spec.in_score]) == 2,
        "L6 representative metric count",
    )
    _assert(
        [spec.name for spec in level_spec.LEVEL_SPECS["L6"] if spec.in_score]
        == ["GoldenFieldRecall_det", "NoRefetch_det"],
        "L6 representative metric name",
    )
    _assert(
        len(level_spec.LEVEL_SPECS["L3"]) == 5,
        "L3 total metric count",
    )
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L3"] if spec.in_score]) == 4,
        "L3 representative metric count",
    )



TESTS = [
    test_l4_meaningful_result_predicate,
    test_l4_stock_trades_empty_payload_not_meaningful,
    test_l4_stock_quote_shape_meaningful,
    test_l4_coverage_det_recovers_non_search_shape,
    test_l4_source_epr_det_counts_meaningful_calls,
    test_l4_spec_shape_and_passk_primary,
    test_l4_change_leaves_l6_and_l3_shapes_unchanged,
]
