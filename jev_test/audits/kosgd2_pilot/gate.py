"""정답 없이 원응답을 검증하는 200 논리 요청 게이트. 서버 전송 기능 없음."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jeveval.contract.b1_response import read_b1_response
from jeveval.contract.response import validate_response
from jeveval.score.answers import parse_b1, parse_systemone
from audits.kosgd2_pilot.prepare import MODELS, plans, manifest


def answers(calls, records):
    expected = {p.call_id for p in calls}
    ids = [r["call_id"] for r in records]
    if len(ids) != len(set(ids)) or not set(ids) <= expected:
        raise ValueError("invalid response call identities")
    if set(ids) != expected:
        return None, False
    by_id, output = {r["call_id"]: r for r in records}, {}
    for p in calls:
        r = by_id[p.call_id]
        if r.get("request_sha256") != p.request_sha256:
            raise ValueError("response request hash differs")
        if r.get("http_status") != 200 or r.get("raw") is None:
            return None, True
        if p.kind == "systemone":
            v = validate_response(r["raw"], p.request)
            if v.reason:
                return None, True
            output.update({q: parse_systemone(v.answers[q], p.question_types[q]).parsed.answer for q in p.question_ids})
        else:
            v = read_b1_response(r["raw"])
            if v.reason:
                return None, True
            q, b = p.question_ids[0], p.b1_call
            parsed = parse_b1(v.top_logprobs, b.label_order, b.label_map, p.question_types[q])
            if parsed.reason:
                return None, True
            output[q] = parsed.parsed.answer
    return output, True


def evaluate(planned, responses):
    if set(planned) != set(MODELS) or set(responses) != set(MODELS):
        raise ValueError("both pilot models required")
    expected = set(planned[MODELS[0]])
    if len(expected) != 200 or set(planned[MODELS[1]]) != expected:
        raise ValueError("same 200 logical requests required")
    results = {}
    for model in MODELS:
        rows = responses[model]
        ids = [r["logical_id"] for r in rows]
        if len(set(ids)) != len(ids) or not set(ids) <= expected:
            raise ValueError("duplicate or extra pilot identity")
        missing = 200 - len(ids)
        invalid, duplicate = missing, 0
        for row in rows:
            value, complete = answers(planned[model][row["logical_id"]], row["calls"])
            missing += int(not complete)
            invalid += int(value is None)
            duplicate += int(value is not None and value["ongoing_1"] == value["ongoing_2"] != "NONE")
        status = "INCOMPLETE" if missing else "PASS" if invalid <= 10 and duplicate <= 10 else "FAIL"
        results[model] = dict(status=status, denominator=200, invalid=invalid, duplicate=duplicate, missing=missing)
    status = "FAIL" if any(r["status"] == "FAIL" for r in results.values()) else (
        "PASS" if all(r["status"] == "PASS" for r in results.values()) else "INCOMPLETE")
    return dict(schema="kosgd2_pilot_gate/1", status=status, models=results)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    for name in ("source", "selection", "manifest", "responses", "out"):
        p.add_argument("--" + name, required=True)
    a = p.parse_args()
    try:
        selection = json.loads(Path(a.selection).read_text())
        planned = plans(a.root, a.source, selection)
        saved = json.loads(Path(a.manifest).read_text())
        if saved != manifest(a.root, selection, planned):
            raise ValueError("pilot manifest differs")
        payload = Path(a.responses).read_bytes()
        result = evaluate(planned, json.loads(payload))
        result["manifest_sha256"] = hashlib.sha256(Path(a.manifest).read_bytes()).hexdigest()
        result["responses_sha256"] = hashlib.sha256(payload).hexdigest()
        result["completed_manifest"] = {**saved, "responses": {"sha256": result["responses_sha256"]}}
        with Path(a.out).open("x") as f:
            f.write(json.dumps(result, indent=1, sort_keys=True) + "\n")
        print(json.dumps({"status": result["status"]}))
        return 0 if result["status"] == "PASS" else 2
    except Exception:
        print('{"status":"INCOMPLETE","error":"pilot gate input invalid"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
