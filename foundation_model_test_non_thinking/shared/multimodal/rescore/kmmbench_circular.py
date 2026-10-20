"""입력: 저장 K-MMBench 행·고정 manifest. 출력: 순환 묶음 점수와 거부 사유."""

from collections import Counter

from shared.multimodal.rescore.manifest import record_issues

METRIC = "kmmbench_circular_stored_judgement"
UPSTREAM = {
    "repository": "https://github.com/open-compass/VLMEvalKit",
    "path": "vlmeval/dataset/utils/multiple_choice.py",
    "commit": "1445ec4f6fd02b25bad0d713690ee01a24b3b689",
    "basis": "SPEC 판 2; commit = latest touching path, checked 2026-10-20 via GitHub API",
    "difference": "stored correct; require all manifest variants, unlike observed-row upstream grouping",
}


def score(rows, manifest):
    """행·manifest를 받아 그룹별 0/1 점수와 동일 가중 요약을 반환한다."""
    issues = record_issues(rows, manifest)
    for position, row in enumerate(rows):
        if isinstance(row, dict) and type(row.get("correct")) is not bool:
            issues.append({"row": position, "reason": "boolean_correct_required"})
    by_index = {str(row["index"]): row for row in rows
                if isinstance(row, dict) and type(row.get("index")) is int}
    group_scores = []
    for key, members in sorted(manifest["groups"].items(), key=lambda pair: int(pair[0])):
        present = [by_index[index] for index in members if index in by_index]
        complete = len(present) == len(members)
        passed = complete and all(r.get("correct") is True and r.get("error") in (None, "") for r in present)
        group_scores.append({
            "key": key, "cluster": manifest["items"][members[0]]["cluster"],
            "expected": len(members), "observed": len(present), "complete": complete,
            "score": int(passed),
            "row_mean": sum(r.get("correct") is True for r in present) / len(members),
        })
    count = len(group_scores)
    passed = sum(group["score"] for group in group_scores)
    return {
        "metric": METRIC, "version": 1, "upstream": dict(UPSTREAM),
        "accepted": not issues, "issues": issues, "rows": len(rows),
        "row_accuracy": sum(isinstance(r, dict) and r.get("correct") is True for r in rows) / len(rows) if rows else None,
        "groups": count, "passed": passed if not issues else None,
        "accuracy": passed / count if count and not issues else None,
        "variants": dict(sorted(Counter(str(g["expected"]) for g in group_scores).items())),
        "incomplete_groups": sum(not g["complete"] for g in group_scores),
        "errored": sum(isinstance(r, dict) and r.get("error") not in (None, "") for r in rows),
        "group_scores": group_scores,
    }
