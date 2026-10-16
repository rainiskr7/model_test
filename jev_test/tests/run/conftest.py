"""무엇: 순수 실행 테스트 표본 · 입력: 합성 값/기존 fixture · 출력: 계획·시도 · 계약 §8-6."""

from dataclasses import replace
import json
from pathlib import Path
from string import ascii_uppercase, ascii_lowercase, digits
from types import SimpleNamespace

import pytest

from jeveval.io.policy import read_retry_policy
from jeveval.run.plan_calls import plan_calls
from jeveval.types import AttemptRecord, B1Config, BoundQuestion, Item, LengthInfo, ModelConfig, TaskSpec

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def env():
    """파일이나 실제 모델 없이 systemone/B1에 공통으로 쓸 항목을 만든다."""
    policy = read_retry_policy(REPO / "configs/policy.yaml")
    cfg = ModelConfig(id="synthetic", kind="systemone", served_name="model", base_url=None,
        auth_env=None, question_scoring="separate", limit={"tokens": 100, "overflow": "reject"},
        input_limit_response={"status": 422, "body_regex": "too long"}, encoder={}, tokenizer={},
        concurrency=1, b1=None, serving={}, repo={}, t0={}, notes="")
    q = BoundQuestion("is_ready", "success", "noul", "준비?", None,
                      {"true": "예", "false": "아니오"}, "synthetic", "true")
    item = Item("synthetic", "g1", "i1", "합성 원문", [q], {}, None)
    task = TaskSpec("synthetic", "full", {"kind": "plain_text"}, [], None, "synthetic")
    labels = list(ascii_uppercase + ascii_lowercase + digits)
    b1 = B1Config("합성 시스템", "{state}\n{instructions}\n{options}", labels, {"max_tokens": 1})
    bcfg = replace(cfg, kind="b1", b1={"label_token_ids": dict(zip(labels, range(62)))})
    return SimpleNamespace(cfg=cfg, bcfg=bcfg, b1=b1, q=q, item=item, task=task, policy=policy,
        plan=plan_calls(item, task, cfg, None)[0], length=LengthInfo(12, 7, 100, 5))


@pytest.fixture
def make_attempt():
    """현재 계획과 일치하는 terminal 시도를 기본으로 만들고 지정 관측값을 덮어쓴다."""
    def make(plan, **changes):
        """시계·전송 없이 고정된 한 시도 기록을 만든다."""
        record = AttemptRecord(plan.call_id, plan.logical_id, 1, "session",
            "2026-10-13T00:00:00.000Z", "2026-10-13T00:00:01.000Z", 1000,
            200, None, None, True, plan.request_sha256,
            '{"answers":{"is_ready":{"type":"noul","noul":0.8}}}')
        return replace(record, **changes)
    return make


@pytest.fixture
def fixture_json():
    """허용된 기존 fixture 디렉터리에서만 입력을 읽는다."""
    def read(name):
        """지정 fixture를 원본 변경 없이 JSON으로 읽는다."""
        return json.loads((Path(__file__).parents[1] / "fixtures" / name).read_text())
    return read


@pytest.fixture
def b1_raw():
    """기존 라벨 로그확률을 실제 B1 응답 봉투에 넣는다."""
    def wrap(rows, **extra):
        """-Infinity를 포함한 원응답 문자열을 합성한다."""
        return json.dumps({"choices": [{"logprobs": {"content": [{"top_logprobs": rows}]}}], **extra})
    return wrap
