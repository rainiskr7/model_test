"""무엇: T0 5단계 통합 · 입력: 세 공개 API/한 번 전송 · 출력: PASS/FAIL/INCOMPLETE · 계약 §8-7."""

import json

import pytest

from jeveval.io.hashes import sha256_file
from jeveval.io.run_files import read_json
from jeveval.io.t0_files import read_lines
from jeveval.t0.request import build_request
from jeveval.t0.tolerance import REPEATS, VARIANTS
from .conftest import CANARY, fake_post, inputs, stage


@pytest.mark.parametrize("family", ["clef", "clef_flash", "pplx_v1", "pplx_v1_1"])
@pytest.mark.parametrize("mode, expected", [("same", "PASS"), ("flip", "FAIL"),
    ("timeout_and_fail", "FAIL"), ("timeout", "INCOMPLETE")])
def test_full_pipeline(setup, family, mode, expected):
    ctx = setup(family)
    inputs(ctx)
    result = stage(ctx, "reference", checkpoint="checkpoint", runtime=ctx.runtime, device="cpu")
    assert result["variants"] == 2 * len(VARIANTS[family]) * REPEATS
    post = fake_post(mode)
    stage(ctx, "server", base_url="http://127.0.0.1:1", post=post)
    assert len(post.calls) == 2
    stage(ctx, "tolerance", rounding="reference=4")
    result = stage(ctx, "judge", rounding="reference=4,server=4")
    assert result["status"] == expected
    assert result["n_expected_cases"] == 2 and result["n_expected_questions"] == 12
    tolerance = read_json(ctx.directory / "tolerance.json")
    assert all(t["measurement"] == "measured_zero" for qs in tolerance["cases"].values() for t in qs.values())
    for name in ("t0.json", "tolerance.json", "fingerprint.json"):
        public = (ctx.directory / name).read_text()
        assert CANARY not in public and "secret_auth_canary" not in public
    assert CANARY in (ctx.directory / "inputs.jsonl").read_text()
    fingerprint = read_json(ctx.directory / "fingerprint.json")["reference"]
    assert fingerprint["dtype"] == "float32" and fingerprint["device"] == "cpu"
    assert fingerprint["checkpoint_files"] == {"weights.fake": sha256_file(ctx.root / "checkpoint/weights.fake")}
    assert fingerprint["modules"]
    _, raw = read_lines(ctx.directory / "inputs.jsonl")
    assert [r["body"] for r in raw] == post.calls


@pytest.mark.parametrize("family", ["clef", "pplx_v1"])
def test_batch_one_mismatch_is_model_wide_unmeasured(setup, family):
    ctx = setup(family, mismatch=True)
    inputs(ctx)
    ref = stage(ctx, "reference", checkpoint="checkpoint", runtime=ctx.runtime)
    assert ref["variants"] == 0 and ref["reason"] == "batch_one_mismatch"
    # 서버는 공개 진입점 결과와 같아도 변형의 검증 실패를 대체하지 못한다.
    _, records = read_lines(ctx.directory / "reference.jsonl")
    post = fake_post()
    if family == "clef":
        from jeveval.types import AttemptResult
        post = lambda *a, **k: AttemptResult("s", "e", 0., 200, None, None, records[0]["response_raw"])
    stage(ctx, "server", base_url="http://127.0.0.1:1", post=post)
    stage(ctx, "tolerance", rounding="reference=4")
    assert stage(ctx, "judge", rounding="reference=4,server=4")["status"] == "INCOMPLETE"
    assert all(t["measurement"] == "unmeasured"
               for qs in read_json(ctx.directory / "tolerance.json")["cases"].values() for t in qs.values())


def builder(base, target):
    return build_request(base.body["model"], "x" * (target - 10), {"kind":"plain_text"},
                         base.body["questions"]), target


@pytest.mark.parametrize("reject, expected", [(True, "PASS"), (False, "FAIL")])
def test_boundary_reject_policy(setup, reject, expected):
    from jeveval.types import AttemptResult
    ctx = setup(boundary=True)
    inputs(ctx, boundary_builder=builder)
    stage(ctx, "reference", checkpoint="checkpoint", runtime=ctx.runtime)
    regular = fake_post()
    def post(url, payload, timeout, headers):
        if reject and len(json.loads(payload)["state"]) + 10 == 101:
            return AttemptResult("s", "e", 0., 400, None, None, "too long")
        return regular(url, payload, timeout, headers)
    stage(ctx, "server", base_url="http://127.0.0.1:1", post=post)
    stage(ctx, "tolerance", rounding="reference=4")
    assert stage(ctx, "judge", rounding="reference=4,server=4")["status"] == expected
    cases = read_json(ctx.directory / "t0.json")["cases"]
    assert cases[-2]["status"] == "PASS" and cases[-1]["status"] == expected


def test_missing_boundary_builder_and_rounding(setup):
    ctx = setup(boundary=True)
    inputs(ctx)
    stage(ctx, "reference", checkpoint="checkpoint", runtime=ctx.runtime)
    stage(ctx, "server", base_url="http://127.0.0.1:1", post=fake_post())
    stage(ctx, "tolerance", rounding="reference=4")
    assert stage(ctx, "judge", rounding="reference=4,server=4")["status"] == "INCOMPLETE"
    assert stage(ctx, "judge")["status"] == "INCOMPLETE"


def test_all_v11_targets_and_placements(setup):
    ctx = setup("pplx_v1_1")
    inputs(ctx)
    stage(ctx, "reference", checkpoint="checkpoint", runtime=ctx.runtime)
    calls = ctx.runtime.model.calls[2:]
    assert len(calls) == 2 * 6 * len(VARIANTS[ctx.family]) * REPEATS
    for qid in ctx.fixture["cases"][0]["questions"]:
        positions = {(len(b["questions"]), list(b["questions"]).index(qid)) for b in calls if qid in b["questions"]}
        assert positions == {(1,0), (8,0), (8,7), (17,0), (17,7), (17,8), (17,15), (17,16)}
