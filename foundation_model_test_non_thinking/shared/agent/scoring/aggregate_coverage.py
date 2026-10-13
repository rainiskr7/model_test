"""Pure formatting of L7 field coverage diagnostics."""

def _format_l7_coverage(distribution: dict, per_field: dict, entries_classifiable: int, coverage: dict) -> dict:
    """L7 필드 적중 분포와 커버리지를 발행 형식으로 구성한다."""
    fields_required = sum(entry["required"] for entry in per_field.values())
    fields_present = sum(entry["present"] for entry in per_field.values())
    complete_entries = sum(
        count
        for (required, present), count in distribution.items()
        if required == present
    )
    partial_entries = sum(
        count
        for (required, present), count in distribution.items()
        if 0 < present < required
    )
    zero_entries = sum(
        count
        for (_required, present), count in distribution.items()
        if present == 0
    )
    return {
        "annotation_only": True,
        "distribution": [
            {
                "fields_required": required,
                "fields_present": present,
                "entry_count": distribution[(required, present)],
            }
            for required, present in sorted(distribution)
        ],
        "per_field": {
            name: {
                **counts,
                "hit_rate": counts["present"] / counts["required"],
            }
            for name, counts in sorted(per_field.items())
        },
        "totals": {
            "entries": entries_classifiable,
            "complete_entries": complete_entries,
            "partial_entries": partial_entries,
            "zero_entries": zero_entries,
            "fields_required": fields_required,
            "fields_present": fields_present,
            "field_hit_rate": (
                fields_present / fields_required if fields_required else None
            ),
        },
        "coverage": coverage,
        "eligibility_rule": (
            "Uses the exact ResultFieldCoverage_det seeded-only resolver, field "
            "normalization, and value matcher; normalized non-numeric values "
            "longer than 80 characters are excluded, and entries with an "
            "unresolved field are unclassifiable."
        ),
        "statement": (
            "ResultFieldCoverage_det is all-or-nothing per golden-fields entry; "
            "partial field hits shown here are discarded by its score."
        ),
    }
