"""모델별 격리 감사: pplx 패키지 충돌 없이 실제 인코더와 executor 바이트를 확인한다."""

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jeveval.io.config import load_taskspec, read_yaml
from jeveval.io.models import load_model_config
from jeveval.io.tasks import read_b1_config
from jeveval.run.encoders import measurer_for
from jeveval.run.plan_calls import plan_calls
from jeveval.run.stage_inputs import load_items
from audits.audit_v4 import checks
from audits.audit_v4.offline import capture, guard
from audits.audit_v4.independent import source, labels, requests
from audits.audit_v4.independent.frozen import TABLES


def inspect(root, set_name, model):
    cfg = load_model_config(root / f"configs/models/{model}.yaml")
    measurement = cfg.served_name is None
    if measurement:
        cfg = replace(cfg, served_name="audit_measurement_only")
    b1 = read_b1_config(root / "configs/tasks/b1.yaml")
    dialogues, selected, cat, expected, source_checks = source.load(root, set_name)
    try:
        measurer = measurer_for(cfg)
    except Exception:
        measurer = None
    variants = {}
    for variant in ("full", "actions_only"):
        path = f"configs/tasks/{set_name}_{variant}.yaml"
        task, raw = load_taskspec(root / path), read_yaml(root / path)
        approved = requests.approved(raw, f"{set_name}_{variant}", (root / path).read_bytes())
        try:
            items = [i for stage in ("dev", "test") for i in load_items(root=root, task_path=path, stage=stage)]
            variants[variant] = inspect_items(items, task, raw, cfg, b1, measurer, dialogues, cat, expected)
        except Exception:
            variants[variant] = dict(R4="INCOMPLETE", R7="INCOMPLETE", v4_hash="INCOMPLETE",
                                     R2v3=dict(status="INCOMPLETE", denominator=0), calls={})
        if not approved or not all(source_checks.values()):
            variants[variant]["R4"] = "FAIL"
        variants[variant]["measurement_config"] = measurement
        variants[variant]["byte_evidence"] = "INCOMPLETE" if measurement else variants[variant]["v4_hash"]
        variants[variant]["request_mode"] = ("hypothetical_direct" if variant == "actions_only" and
            cfg.question_scoring == "separate" else "executor_capture")
        if measurement:
            variants[variant]["v4_hash"] = "INCOMPLETE"
    return dict(model=model, variants=variants)


def inspect_items(items, task, raw, cfg, b1, measurer, dialogues, cat, expected):
    actual, targets, truth, built, calls, lengths = {}, {}, {}, {}, {}, []
    byte_checks, measurement_failed, ids, r4_calls = [], False, [], []
    qs = requests.questions(raw, source.options(cat))
    for item in items:
        lid = f"{item.set}:{item.group_id}:{item.item_id}"
        ids.append(lid)
        expected_state = expected[lid]
        targets[lid] = dict(state=requests.wire(expected_state).decode(), questions=qs)
        truth[lid] = labels.gold(dialogues[item.group_id]["turns"][int(item.item_id)], cat, TABLES[f"{task.set}_{task.variant}"])
        built[lid] = {q.id: dict(gold=q.gold, role=q.role, type=q.type, label=q.label) for q in item.questions}
        item_lengths = []
        for p in plan_calls(item, task, cfg, b1):
            projected, byte_status, hashes = inspect_call(p, expected_state, qs, cfg, b1)
            actual[lid] = projected
            r4_calls.append(checks.r4({lid: projected}, {lid: targets[lid]}))
            byte_checks.append(byte_status)
            calls[p.call_id] = hashes
            if measurer is not None:
                try:
                    item_lengths.append(measurer.measure(p).length_tokens)
                except Exception:
                    measurement_failed = True
        if item_lengths:
            lengths.append(max(item_lengths))
    length = checks.lengths(lengths, cfg.limit["tokens"])
    if (measurement_failed or measurer is None or len(lengths) != len(items)) and length["status"] != "FAIL":
        length["status"] = "INCOMPLETE"
    r4 = checks.r4(actual, targets) if set(ids) == set(expected) and len(set(ids)) == len(ids) else "FAIL"
    r4 = checks.combine([r4, *r4_calls])
    return dict(R4=r4, R7=checks.r7(built, truth, actual, targets), v4_hash=checks.combine(byte_checks), R2v3=length, calls=calls)


def inspect_call(p, state, qs, cfg, b1):
    expected, mapping = requests.envelope(state, qs, cfg.to_dict(), b1.to_dict(), p.question_ids[0])
    captured = capture(p, cfg)
    body = json.loads(p.body)
    if p.kind == "systemone":
        projected = dict(state=body["state"], questions=body["questions"])
    else:
        prefix = b1.user_template.split("{state}")[0]
        user = body["messages"][1]["content"]
        decoded, end = json.JSONDecoder().raw_decode(user[len(prefix):])
        projected = dict(state=requests.wire(decoded).decode(), questions=p.request.questions)
        # 전체 messages 비교로 질문 문구/선택지의 바이트 변조도 R4에 연결한다.
        if body["messages"] != json.loads(expected)["messages"]:
            projected["questions"] = {}
    status = checks.hashes(p.body, expected, captured, None if p.b1_call is None else p.b1_call.label_map, mapping)
    digest = lambda b: hashlib.sha256(b).hexdigest()
    return projected, status, dict(planned=digest(p.body), independent=digest(expected), captured=digest(captured))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--set", required=True)
    parser.add_argument("--model", required=True)
    a = parser.parse_args()
    try:
        with guard():
            value = inspect(Path(a.root), a.set, a.model)
        print(json.dumps(value, ensure_ascii=False))
        return 0
    except Exception:
        print('{"status":"INCOMPLETE","error":"model audit unavailable"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
