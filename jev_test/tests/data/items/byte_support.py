"""무엇: 항목/전송 회귀 표본 · 입력: 동결 설정·합성 행 · 출력: 바이트 스냅샷 · 계약 §6-2·§9."""

from dataclasses import replace
import json
from pathlib import Path
from string import ascii_uppercase, ascii_lowercase, digits

from jeveval.data.grouping import group_rows
from jeveval.data.items import functionchat, klue_mrc, kmhas, korfin, kosgd, kote
from jeveval.io.config import load_taskspec
from jeveval.io.datasets import read_label_vocab
from jeveval.io.tasks import read_b1_config, read_lists
from jeveval.run.plan_calls import plan_calls
from jeveval.score.labels import rules
from jeveval.types import ModelConfig, SourceRow, SplitPlan

ROOT = Path(__file__).resolve().parents[3]
BUILDERS = dict(kmhas=kmhas, kote_escalation=kote, korfin_asc=korfin,
                klue_mrc_answerable=klue_mrc, kosgd=kosgd, fc_call_decision=functionchat)


def rows_for(name, lists):
    """중복 묶음·가변 질문·직전 USER·정규화·extra를 포함한 공개 합성 행이다."""
    if name == "kmhas":
        rows = [dict(text=" 합성 본문 ", label=[0], label_names=["origin"]),
                dict(text=" 합성 본문 ", label=[], label_names=[]), dict(text="다음", label=[], label_names=[])]
    elif name == "kote_escalation":
        rows = [dict(text=t, labels_majority=v) for t, v in
                [(" 동일 ", ["없음"]), (" 동일 ", []), ("다음", ["짜증"])]]
    elif name == "klue_mrc_answerable":
        rows = [dict(guid=str(i), context="문맥" + str(i), question="질문?", source="news",
                     is_impossible=bool(i)) for i in range(2)]
    elif name == "korfin_asc":
        rows = [dict(SID=s, SRC=t, ASPECT=a, SENTIMENT=v) for s, t, a, v in
                [("1_2", "기업", "누락", "NEGATIVE"), ("1_0", "기업", "기업", "POSITIVE"),
                 ("2_0", "다음", "다음", "NEUTRAL")]]
    elif name == "kosgd":
        rows = [dict(dialogue_id=d, turn_index=i, services=["z"],
                     dialogue=[dict(speaker="USER", utterance="합성" + str(i))],
                     frames=[dict(service="z", state=dict(active_intent=v), actions=[dict(act="INFORM")])])
                for d, i, v in [("d1", 0, "old"), ("d2", 0, "old"), ("d2", 2, "new")]]
    else:
        sentence = lists["functionchat_normalization"]["duplicate_sentence"]
        rows = [dict(serial_num=i, input_messages=[dict(role="system", content=sentence + " " + sentence),
                    dict(role="user", content="사용자" + str(min(i, 1)))],
                    input_tools=[dict(function=dict(name=n + str(min(i, 1)), description=n)) for n in ("z", "a")],
                    type_of_output="slot", ground_truth={}) for i in range(3)]
    return [SourceRow(name, r.get("SID", f"{r['dialogue_id']}#{r['turn_index']}" if name == "kosgd" else str(i)), r)
            for i, r in enumerate(rows)]


def sample(name):
    """실제 동결 task와 정답 규칙을 사용하고 원 데이터는 읽지 않는다."""
    task = load_taskspec(ROOT / "configs/tasks" / ("kosgd_full.yaml" if name == "kosgd" else name + ".yaml"))
    lists = read_lists(ROOT / "configs/tasks/lists")
    if name == "kosgd":
        lists.update(kosgd_catalog=[dict(service="z", intents=[dict(id="z/old"), dict(id="z/new")])],
                     catalog_intents_plus_none={"z/old": "이전", "z/new": "현재", "NONE": "없음"})
    rows = rows_for(name, lists)
    groups = group_rows(rows, task.group_key).members
    representatives = {g: f"{name}:{g}:{members[-1]}" for g, members in groups.items()}
    ids = sorted(groups)
    extra = sorted(f"{name}:{g}:{i}" for g, members in groups.items() for i in members
                   if f"{name}:{g}:{i}" != representatives[g]) if name == "fc_call_decision" else []
    plan = SplitPlan(name, 1, {}, {}, groups, representatives, ids[:1], ids[1:],
                     ["없음"] if name == "kote_escalation" else [], extra, {})
    items = BUILDERS[name].build_items(rows, plan, task, lists, rules(read_label_vocab(ROOT / "configs/datasets.yaml")))
    return task, items


def wire_snapshot(name):
    """JSON 키/질문/선택지 순서를 포함한 실제 바이트를 UTF-8 문자열로 고정한다."""
    task, items = sample(name)
    labels = ascii_uppercase + ascii_lowercase + digits
    cfg = ModelConfig("synthetic", "systemone", "model", None, None, "separate", {"tokens": 8192},
                      None, {}, {}, 1, {"label_token_ids": dict(zip(labels, range(62)))}, {}, {}, {}, "")
    b1 = read_b1_config(ROOT / "configs/tasks/b1.yaml")
    output = {}
    for stage, values in items.items():
        output[stage] = []
        for item in values:
            calls = {}
            for kind in ("systemone", "b1"):
                plans = plan_calls(item, task, replace(cfg, kind=kind), b1)
                assert plans and all(not p.local_errors for p in plans)
                calls[kind] = [dict(body=p.body.decode(), question_ids=p.question_ids,
                                   label_map=None if p.b1_call is None else p.b1_call.label_map) for p in plans]
            output[stage].append(dict(item=json.dumps(item.to_dict(), ensure_ascii=False, separators=(",", ":")),
                                      calls=calls))
    return output
