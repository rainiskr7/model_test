"""무엇: T0 단계 통합 준비 · 입력: tmp_path/가짜 모듈 · 출력: 실행 seam · 계약 §8-7."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest
import yaml

from jeveval.data.grouping import group_rows
from jeveval.data.t0_fixture import make_fixture
from jeveval.io.config import read_yaml
from jeveval.io.t0_files import write_fixture
from jeveval.reference.t0_runner import load
from jeveval.run.cmd_t0 import run
from jeveval.types import AttemptResult, SourceRow
from jeveval.types.t0_io import T0Sources
from . import fakes

ROOT = Path(__file__).resolve().parents[2]
CANARY = "PRIVATE_T0_STATE_CANARY_70913"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("T0_TEST_AUTH", "secret_auth_canary")
    def prepare(family="clef", boundary=False, mismatch=False):
        root = tmp_path / family
        root.mkdir(exist_ok=True)
        cfg = read_yaml(ROOT / "configs/models" / f"{family}.yaml")
        cfg.update(served_name="served", auth_env="T0_TEST_AUTH", limit=dict(tokens=100, overflow="reject"),
                   input_limit_response=dict(status=400, body_regex="too long"))
        (root / f"{family}.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
        rows = [SourceRow("kmhas", str(i), {"text": CANARY + str(i)}) for i in range(3)]
        sources = T0Sources({"kmhas": rows}, {"kmhas": group_rows(rows, "text")}, {"kmhas": {"0"}}, 42)
        template = json.loads((ROOT / "configs/t0/template_v1.json").read_text())
        # 작은 표본에서도 생성기는 모든 직렬화/질문 수를 만든다.
        fixture = make_fixture(sources, template)
        ordinary = [deepcopy(fixture["cases"][0]), deepcopy(fixture["cases"][0])]
        ordinary[1]["case_id"] = "second"
        fixture["cases"] = ordinary + ([fixture["cases"][-1]] if boundary else [])
        fixture["batches"] = [dict(target=[c["case_id"], q], placements=fixture["batches"][0]["placements"])
                              for c in ordinary for q in c["questions"]]
        write_fixture(root / "fixture.json", fixture)
        checkpoint = root / "checkpoint"
        checkpoint.mkdir(exist_ok=True)
        (checkpoint / "weights.fake").write_bytes(b"fake checkpoint")
        mod = fakes.module()
        if mismatch:
            original = mod.systemone if family.startswith("clef") else mod.answer
            if family.startswith("clef"):
                def changed(*args, **kwargs):
                    value = original(*args, **kwargs)
                    value["answers"]["binary"]["noul"] = .6
                    return value
                mod.systemone = changed
            else:
                mod.answer = lambda q, p: dict(original(q, p), extra=True)
        runtime = load(family, checkpoint, device="cpu", reference=mod, answer_module=mod, server=mod)
        return SimpleNamespace(root=root, family=family, sources=sources, runtime=runtime,
                               fixture=fixture, directory=root / "results/_t0" / family / "r1")
    return prepare


def inputs(ctx, **kwargs):
    return run(root=ctx.root, stage="inputs", model=f"{ctx.family}.yaml", run_id="r1",
               fixture="fixture.json", sources=ctx.sources, **kwargs)


def stage(ctx, name, **kwargs):
    return run(root=ctx.root, stage=name, run_dir=ctx.directory, **kwargs)


def fake_post(mode="same"):
    calls = []
    def post(url, payload, timeout, headers):
        body = json.loads(payload)
        calls.append(body)
        assert headers == {"Authorization": "Bearer secret_auth_canary"}
        if mode in ("timeout", "timeout_and_fail") and len(calls) == 1:
            return AttemptResult("start", "end", 1., None, None, "timeout", "")
        value = fakes.response(body)
        if mode in ("flip", "timeout_and_fail"):
            q = value["answers"]["choice_two"]
            a, b = q["probabilities"]
            q["probabilities"] = {a:.3, b:.7}
            q["choice"] = b
        return AttemptResult("start", "end", 1., 200, None, None, json.dumps(value))
    post.calls = calls
    return post
