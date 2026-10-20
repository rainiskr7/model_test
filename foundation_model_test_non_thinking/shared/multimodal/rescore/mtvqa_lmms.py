"""입력: 저장 MTVQA 행·고정 manifest. 출력: lmms 방식 문항 점수와 거부 사유."""

from shared.multimodal.rescore.manifest import record_issues

METRIC = "mtvqa_lmms_eval"
UPSTREAM = {
    "repository": "https://github.com/EvolvingLMMs-Lab/lmms-eval",
    "path": "lmms_eval/tasks/mtvqa/utils.py",
    "function": "mtvqa_process_results",
    "commit": "d8fcb9c345fd89b22b4857244b3fdbb89206f8f5",
    "basis": "SPEC 판 2; commit = latest touching path, checked 2026-10-20 via GitHub API",
    "difference": "singleton gold unwrap; errors and normalized-empty gold always fail",
}


def lmms_match(prediction, answer):
    """문자열 응답·gold를 받아 lmms 정규화·포함 판정을 반환한다."""
    if not isinstance(prediction, str) or not isinstance(answer, str):
        return False
    pred = prediction.strip().lower().replace(".", "")
    gold = answer.strip().lower().replace(".", "")
    return bool(gold) and gold in pred


def score(rows, manifest):
    """행·manifest를 받아 문항 가중 정답률과 이미지 식별자를 반환한다."""
    issues = record_issues(rows, manifest)
    item_scores, empty_gold, errored = [], 0, 0
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        gold = row.get("gold")
        if not isinstance(gold, list) or len(gold) != 1 or not isinstance(gold[0], str):
            continue
        error = row.get("error") not in (None, "")
        empty = not gold[0].strip().lower().replace(".", "")
        errored += error
        empty_gold += empty
        response = row.get("response")
        if not error and not isinstance(response, str):
            issues.append({"row": position, "reason": "string_response_required"})
        key = f'{row.get("id")}\t{row.get("qa_idx")}'
        item = manifest["items"].get(key)
        if item is not None:
            item_scores.append({"key": key, "image_id": item["id"], "cluster": item["cluster"],
                                "score": int(not error and lmms_match(response, gold[0]))})
    correct = sum(item["score"] for item in item_scores)
    return {
        "metric": METRIC, "version": 1, "upstream": dict(UPSTREAM),
        "accepted": not issues, "issues": issues, "rows": len(rows),
        "correct": correct if not issues else None,
        "accuracy": correct / len(rows) if rows and not issues else None,
        "stored_correct": sum(isinstance(r, dict) and r.get("correct") is True for r in rows),
        "stored_accuracy": sum(isinstance(r, dict) and r.get("correct") is True for r in rows) / len(rows) if rows else None,
        "errored": errored, "empty_gold": empty_gold, "item_scores": item_scores,
    }
