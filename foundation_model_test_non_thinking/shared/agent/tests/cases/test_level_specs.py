from _harness import _assert, level_spec

def test_other_level_shapes_unchanged():
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L1"] if spec.in_score]) == 3,
        "L1 representative metric count",
    )
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L2"] if spec.in_score]) == 3,
        "L2 representative metric count",
    )
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L3"] if spec.in_score]) == 4,
        "L3 representative metric count",
    )
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L4"] if spec.in_score]) == 2,
        "L4 representative metric count",
    )
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L7"] if spec.in_score]) == 3,
        "L7 representative metric count",
    )
    _assert(level_spec.PASSK_PRIMARY_METRICS["L1"] == "CallEM", "L1 PassK_det primary")



TESTS = [
    test_other_level_shapes_unchanged,
]
