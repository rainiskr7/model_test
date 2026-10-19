"""라벨 없는 합성 파일럿 원본과 200개 응답 생성기."""

import json


def dialogues():
    return [dict(dialogue_id=f"d{i:04}", turns=[dict(speaker="USER", utterance=f"synthetic-{i}"),
                                               dict(speaker="SYSTEM", utterance="reply"),
                                               dict(speaker="USER", utterance="next")]) for i in range(3000)]


def responses(planned, *, duplicates=0, invalid=0):
    result = {}
    for model, rows in planned.items():
        result[model] = []
        for i, (lid, plans) in enumerate(rows.items()):
            calls = []
            for p in plans:
                if p.kind == "systemone":
                    answers = {}
                    for q, spec in p.request.questions.items():
                        if spec["type"] == "noul": answers[q] = dict(type="noul", noul=.1)
                        else:
                            winner = next(k for k in spec["criteria"] if k != "NONE") if i < duplicates else "NONE"
                            answers[q] = dict(type="choice", choice=winner, confidence=1.,
                                              probabilities={k: float(k == winner) for k in spec["criteria"]})
                    raw = dict(answers=answers)
                else:
                    b = p.b1_call
                    values = list(b.label_map.values())
                    winner = (next(k for k in values if k != "NONE") if i < duplicates else "NONE") if "NONE" in values else "false"
                    raw = dict(choices=[dict(logprobs=dict(content=[dict(top_logprobs=[
                        dict(token=k, logprob=-.01 if v == winner else -20.) for k, v in b.label_map.items()])]))])
                calls.append(dict(call_id=p.call_id, request_sha256=p.request_sha256,
                                  http_status=500 if i < invalid else 200, raw=json.dumps(raw)))
            result[model].append(dict(logical_id=lid, calls=calls))
    return result
