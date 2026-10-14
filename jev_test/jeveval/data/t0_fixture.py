"""무엇: 풀 밖 T0 fixture 구성 · 입력: 공개 SourceRow/합성 문구 · 출력: 참조 ID만 든 fixture · 계약 §8-7 T-c."""

from copy import deepcopy
from hashlib import sha256

from jeveval.t0.request import canonical_bytes
from jeveval.t0.tolerance import V11_VARIANTS
from jeveval.types.t0_io import T0Sources


def source_state(row):
    """라벨 없이 원문 필드만 선택하며 복합 대화도 정규 문자열로 보존한다."""
    key = {"kmhas": "text", "kote_escalation": "text", "korfin_asc": "SRC",
           "klue_mrc_answerable": "context", "kosgd": "dialogue"}[row.set]
    value = row.fields[key]
    return value if isinstance(value, str) else canonical_bytes(value).decode("utf-8")


def resolve_source(ref, sources: T0Sources):
    name, rid = ref["set"], ref["row_id"]
    if name not in sources.rows:
        raise ValueError("T0 source set unavailable")
    group = sources.groups[name].row_to_group.get(rid)
    if group is None or group in sources.pools[name]:
        raise ValueError("T0 source is missing or inside evaluation pool")
    return source_state(next(row for row in sources.rows[name] if row.row_id == rid))


def make_fixture(sources: T0Sources, template):
    cases = []
    for name in sorted(sources.rows):
        eligible = [r for r in sources.rows[name]
                    if sources.groups[name].row_to_group[r.row_id] not in sources.pools[name]]
        if not eligible:
            raise ValueError("no out-of-pool T0 source")
        def rank(row):
            return sha256(canonical_bytes([sources.seed, "t0", name, row.row_id])).hexdigest()
        row = min(eligible, key=rank)
        state = source_state(row)
        cases.append(dict(case_id=name, state_ref=dict(set=name, row_id=row.row_id),
                          state_sha256=sha256(state.encode()).hexdigest(),
                          questions=deepcopy(template["mixed"]), purpose="mixed_public"))
    for count in (8, 17):
        case = deepcopy(cases[min(int(count == 17), len(cases) - 1)])
        case.update(case_id=f"questions_{count}", purpose=f"questions_{count}")
        choices = list(template["mixed"].values())
        case["questions"] = {f"q_{i}": deepcopy(choices[i % len(choices)]) for i in range(count)}
        cases.append(case)
    for cid, state in template["serialization"].items():
        cases.append(dict(case_id=cid, synthetic_state={"text":state},
                          state_spec=dict(kind="json_string", keys=["text"], target_key="text"),
                          questions=deepcopy(template["mixed"]), purpose="serialization"))
    placements = [dict(target=[case["case_id"], qid], placements=list(V11_VARIANTS))
                  for case in cases for qid in case["questions"]]
    cases.append(dict(case_id="boundary", kind="boundary", offsets=[0, 1], base_case=cases[0]["case_id"]))
    return dict(schema="t0_fixture/1", seed=sources.seed, cases=cases, batches=placements)
