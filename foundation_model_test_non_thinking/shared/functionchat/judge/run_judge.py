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
    vs = [v for v in verdicts if v is not None]
    if not vs:
        return None
    top, n = Counter(vs).most_common(1)[0]
    return top if n * 2 > len(vs) else None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True, type=Path)
    ap.add_argument("--data-dir", type=Path, default=Path("data/FunctionChat-Bench/data"))
    ap.add_argument("--judge-model", default="openai/gpt-4.1-mini")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--api-key-env", default="TAUBENCH_USER_API_KEY")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args(argv)

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"{args.api_key_env} 환경변수가 필요합니다 (값은 인자로 받지 않습니다).")

    rubrics = load_rubrics(args.data_dir)
    items = collect_items(args.results_dir)
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
                "verdicts": verdicts,
                "justification_ko": runs[0].get("justification_ko"),
            }
        )
        if index % 50 == 0 or index == len(items):
            print(f"[judge] {index}/{len(items)}")

    judged = sum(c["pass"] + c["fail"] for c in per_type.values())
    passed = sum(c["pass"] for c in per_type.values())
    summary = {
        "benchmark": "kakao/FunctionChat-Bench (LLM judge layer)",
        "scoring_version": SCORING_VERSION,
        "judge": {
            "model": args.judge_model,
            "repeats": args.repeats,
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
