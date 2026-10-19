"""무엇: 대화 단위 제외 해석 · 입력: 선정/fixture 객체 · 출력: 대화 ID 집합 · 계약 판 5 보정 1 §6-2."""


def dialogue_ids(records, by):
    """state_ref는 KoSGD 가족 참조만 대상으로 하며 턴 위치와 관계없이 대화를 제외한다."""
    if not isinstance(records, list) or by not in {"dialogue_id", "state_ref"}:
        raise ValueError("invalid selection exclusion records")
    result = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid selection exclusion record")
        if by == "dialogue_id":
            value = record.get("dialogue_id")
        else:
            if "state_ref" not in record:
                continue
            ref = record["state_ref"]
            if not isinstance(ref, dict) or set(ref) != {"set", "row_id"}:
                raise ValueError("invalid T0 state_ref")
            if ref["set"] not in {"kosgd", "kosgd2"}:
                continue
            row = ref["row_id"]
            if not isinstance(row, str) or row.count("#") != 1 or not row.rsplit("#", 1)[1].isdigit():
                raise ValueError("invalid KoSGD T0 row identity")
            value = row.rsplit("#", 1)[0]
        if not isinstance(value, str) or not value or any(c in value for c in (":", "#", "\n")):
            raise ValueError("invalid excluded dialogue ID")
        result.add(value)
    return result
