#!/usr/bin/env python3
"""FunctionChat 판정 계층 본 실행.

exact-match 트랙이 측정하지 못하는 636건(되묻기 slot / 거절 relevance /
완결 completion)을 상류 루브릭으로 판정한다.

결정론 층과 **합치지 않는다.** 별도 산출물(judge.json)과 별도 채점 버전
functionchat_judge_v1 로 낸다. exact 층의 안정성(분산 0.000)이 판정 잡음에
오염되면 안 된다.

파일럿(judge_pilot.py)에서 확인한 것:
  파싱 실패 0건 / mini 반복 뒤집힘 3.3% / mini vs full 일치 98.3%
따라서 본 실행은 mini 단일 판정기를 쓰되, **반복 2회를 돌려 뒤집힌 항목을 표시**한다.
뒤집힌 항목은 점수에 넣되 unstable 로 세어 해석에 쓴다.

한계: 인간 라벨 검증을 하지 않았다. 이 수치는 "판정기 기준 점수" 이지 정답률의
추정치가 아니다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from judge_pilot import (  # noqa: E402
    VERDICT_SCHEMA,
    call_judge,
    collect_items,
    load_rubrics,
    render_prompt,
)

SCORING_VERSION = "functionchat_judge_v1"


def majority(verdicts: List[Optional[str]]) -> Optional[str]:
    """유효 표의 과반을 돌려준다. 과반이 없으면 None.

    **분모는 유효 표 수이지 요청한 반복 수가 아니다.** 전송 실패로 표가 줄면 남은
    표만으로 과반을 따진다 — 예컨대 2회 중 1회가 실패하면 [None, "fail"] 이 되고
    유효 표는 1개이므로 "fail" 이 과반이 된다. 이는 1표짜리 판정이므로 호출 측이
    반드시 `lost_votes` 를 함께 기록해 사후에 걸러낼 수 있어야 한다.
    """
    vs = [v for v in verdicts if v is not None]
    if not vs:
        return None
    top, n = Counter(vs).most_common(1)[0]
    return top if n * 2 > len(vs) else None


def vote_integrity(verdicts: List[Optional[str]], requested: int) -> Dict[str, Any]:
    """표가 유실됐는지, 그래서 판정이 몇 표에 기대는지 기록한다."""
    valid = [v for v in verdicts if v is not None]
    return {
        "requested": requested,
        "received": len(valid),
        "lost": requested - len(valid),
        "single_vote": len(valid) == 1,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True, type=Path)
    ap.add_argument("--data-dir", type=Path, default=Path("data/FunctionChat-Bench/data"))
    ap.add_argument("--judge-model", default="openai/gpt-4.1-mini")
    # 3회여야 과반이 성립한다. 2회는 갈리면 판정 불가가 되어 분모에서 빠진다 —
    # 2026-08-23 본 실행에서 21건(qwen 12/gemma 9)이 그렇게 사라졌다.
    # 전송·파싱 실패는 0건이었고 전부 동점이었다.
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--api-key-env", default="TAUBENCH_USER_API_KEY")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument(
        "--retry-unresolved",
        action="store_true",
        help="기존 judge.json 의 판정 불가 항목만 다시 판정해 병합한다",
    )
    args = ap.parse_args(argv)

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"{args.api_key_env} 환경변수가 필요합니다 (값은 인자로 받지 않습니다).")

    rubrics = load_rubrics(args.data_dir)
    items = collect_items(args.results_dir)

    # --retry-unresolved: 기존 judge.json 에서 판정 불가(동점)로 남은 항목만 다시 돈다.
    # 전체 재실행은 이미 확정된 615건까지 다시 부르는 낭비다.
    previous = None
    out_path = args.results_dir / "judge.json"
    if args.retry_unresolved:
        if not out_path.exists():
            raise SystemExit(f"--retry-unresolved 인데 {out_path} 가 없습니다.")
        previous = json.loads(out_path.read_text(encoding="utf-8"))
        unresolved = {
            r["serial_num"] for r in previous["records"] if r["status"] == "judge_error"
        }
        items = [i for i in items if i.get("serial_num") in unresolved]
        print(f"[judge] 재판정 대상 {len(items)}건 (기존 판정 불가)")

    print(f"[judge] 대상 {len(items)}건, 판정기 {args.judge_model}, 반복 {args.repeats}")

    per_type: Dict[str, Counter] = defaultdict(Counter)
    records = []
    errors = Counter()

    # 항목마다 독립이고 temperature=0 이므로 병렬 호출이 결과를 바꾸지 않는다.
    # 순차로는 636건 x 2회에 4시간이 걸렸다 (2026-08-23 실측).
    def judge_one(item: Dict[str, Any]):
        kind = str(item.get("type_of_output"))
        prompt = render_prompt(rubrics[kind], item)
        return item, [
            call_judge(prompt, args.judge_model, api_key, args.timeout, args.retries)
            for _ in range(args.repeats)
        ]

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        pairs = list(pool.map(judge_one, items))

    for index, (item, runs) in enumerate(pairs, start=1):
        kind = str(item.get("type_of_output"))
        verdicts = [r.get("verdict") for r in runs]
        for r in runs:
            if r.get("error"):
                errors["transport"] += 1
            elif r.get("verdict") is None:
                errors["parse"] += 1
        final = majority(verdicts)
        unstable = len({v for v in verdicts if v is not None}) > 1
        integrity = vote_integrity(verdicts, len(runs))
        # 표가 유실돼 단 1표로 확정된 판정은 정식 판정으로 세지 않는다.
        # 전송 실패가 조용히 반복 수를 깎고 그 사실이 남지 않는 경로였다.
        if final and integrity["lost"] and integrity["single_vote"]:
            final = None
        # 판정 불가는 fail 로 바꾸지 않는다. 별도 상태로 남긴다.
        status = "judged" if final else "judge_error"
        per_type[kind][status if not final else final] += 1
        if unstable:
            per_type[kind]["unstable"] += 1
        records.append(
            {
                "serial_num": item.get("serial_num"),
                "dataset": item.get("dataset"),
                "type_of_output": kind,
                "verdict": final,
                "status": status,
                "unstable": unstable,
                "vote_integrity": integrity,
                "verdicts": verdicts,
                "justification_ko": runs[0].get("justification_ko"),
            }
        )
        if index % 50 == 0 or index == len(items):
            print(f"[judge] {index}/{len(items)}")

    if previous is not None:
        # 재판정하지 않은 기존 레코드를 합치고 유형별 집계를 다시 만든다.
        redone = {r["serial_num"] for r in records}
        merged = [r for r in previous["records"] if r["serial_num"] not in redone]
        records = merged + records
        per_type = defaultdict(Counter)
        for r in records:
            kind = r["type_of_output"]
            per_type[kind][r["verdict"] or r["status"]] += 1
            if r["unstable"]:
                per_type[kind]["unstable"] += 1

    judged = sum(c["pass"] + c["fail"] for c in per_type.values())
    passed = sum(c["pass"] for c in per_type.values())
    summary = {
        "benchmark": "kakao/FunctionChat-Bench (LLM judge layer)",
        "scoring_version": SCORING_VERSION,
        "judge": {
            "model": args.judge_model,
            # 재판정(--retry-unresolved)을 하면 항목마다 투표 수가 다르다. 단일 값으로
            # 적으면 거짓이 된다 — 2026-08-23 에 repeats=5 로 기록됐으나 실제로는
            # 623건이 2회, 13건만 5회였다. 실제 분포를 기록한다.
            "repeats_requested_this_invocation": args.repeats,
            "votes_per_item": None,  # 아래에서 실측으로 채운다
            "temperature": 0,
            "output_contract": "json_schema strict {verdict, justification_ko}",
            "rubric_source": "upstream data/rubric_{type}.txt (unmodified)",
            "human_validation": "not performed",
        },
        "caveat": (
            "판정기 기준 점수다. 인간 라벨 검증을 하지 않았으므로 정답률의 추정치가 "
            "아니다. exact 층(functionchat_exact_v2)과 합산하지 말 것."
        ),
        "overall": {
            "judged": judged,
            "passed": passed,
            "failed": judged - passed,
            "pass_rate": (passed / judged) if judged else None,
            "judge_errors": sum(1 for r in records if r["status"] == "judge_error"),
            "unstable": sum(1 for r in records if r["unstable"]),
        },
        "by_type": {k: dict(v) for k, v in sorted(per_type.items())},
        "errors": dict(errors),
        "records": records,
    }
    from collections import Counter as _C
    summary["judge"]["votes_per_item"] = {
        str(k): v for k, v in sorted(_C(len(r["verdicts"]) for r in records).items())
    }
    out = args.results_dir / "judge.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    o = summary["overall"]
    for kind, counts in summary["by_type"].items():
        p, f = counts.get("pass", 0), counts.get("fail", 0)
        rate = f"{p/(p+f):.4f}" if p + f else "-"
        print(f"[judge] {kind:<12} {p}/{p+f} = {rate}  unstable={counts.get('unstable',0)}")
    print(f"[judge] overall {o['passed']}/{o['judged']} = {o['pass_rate']:.6f}  "
          f"errors={o['judge_errors']}  unstable={o['unstable']}")
    print(f"[judge] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
