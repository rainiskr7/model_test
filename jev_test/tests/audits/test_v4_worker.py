"""네트워크 없는 executor/client/독립 전체 봉투 일치 시험."""

import json
from pathlib import Path

from audits.audit_v4.offline import capture, guard
from audits.audit_v4.worker import inspect_call
from jeveval.client.systemone import send_systemone
from jeveval.client.vllm_chat import send_chat
from jeveval.io.config import load_taskspec, read_yaml
from jeveval.io.models import load_model_config
from jeveval.io.tasks import read_b1_config, read_lists
from jeveval.run.plan_calls import plan_calls
from jeveval.types import Item, BoundQuestion

ROOT = Path(__file__).resolve().parents[2]


def test_three_hashes_match_both_clients_and_executor():
    task = load_taskspec(ROOT / "configs/tasks/kosgd2_full.yaml")
    lists = read_lists(ROOT / "configs/tasks/lists")
    state = dict(dialogue=[dict(speaker="USER", utterance="synthetic")], catalog=lists["kosgd_catalog"])
    qs = [BoundQuestion(q.id, q.role, q.type, q.instructions, lists[q.options] if q.type == "choice" else None,
                        q.criteria, q.label, None) for q in task.questions]
    item = Item("kosgd2", "d", "0", state, qs, {}, None)
    b1 = read_b1_config(ROOT / "configs/tasks/b1.yaml")
    for model in ("pplx_v1_1", "b1_qwen3_8_27b"):
        cfg = load_model_config(ROOT / f"configs/models/{model}.yaml")
        for p in plan_calls(item, task, cfg, b1):
            with guard():
                projection, status, hashes = inspect_call(p, state, p.request.questions, cfg, b1)
                assert status == "PASS" and len(set(hashes.values())) == 1
                bodies = []
                def post(url, body, timeout, **kw): bodies.append(body)
                if p.kind == "systemone": send_systemone("http://invalid", p.request, post=post)
                else: send_chat("http://invalid", json.loads(p.body), post=post)
                assert bodies == [p.body]


def test_independent_b1_labels_do_not_trust_common_label_order():
    from audits.audit_v4.independent.requests import envelope
    b1 = read_b1_config(ROOT / "configs/tasks/b1.yaml").to_dict()
    cfg = load_model_config(ROOT / "configs/models/b1_qwen3_8_27b.yaml").to_dict()
    state = dict(dialogue=[dict(speaker="USER", utterance="synthetic")], catalog=[])
    qs = dict(q=dict(type="noul", instructions="question", criteria={"true": "yes", "false": "no"}))
    original = envelope(state, qs, cfg, b1, "q")
    b1["labels"].reverse()
    assert envelope(state, qs, cfg, b1, "q") == original
