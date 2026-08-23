#!/usr/bin/env python3
"""functionchat / taubench 산출물에서 **발행 가능한 수치만** 보고한다.

이 도구가 존재하는 이유: AGENT_TRACK_CLOSEOUT.md 에 "인용 금지" 를 적어두는 것만으로는
부족하다. 문서는 무시할 수 있다 — 실제로 2026-08-23 에 게이트가 거부한
gemma telecom 0.4615 를 요약 파일만 보고 최종 수치로 여러 번 인용했다.

그래서 규칙을 코드로 옮긴다.

  - publish_status.publishable != true 인 런은 **점수를 출력하지 않는다.**
    REJECTED 로 표시하고 사유를 적는다.
  - 판정 축은 인간 검증 전까지 항상 PROVISIONAL 딱지를 붙인다.
  - 분자/분모를 함께 낸다. 반올림된 점수만으로는 표본 크기가 사라진다.
  - --strict 는 거부된 런이 하나라도 있으면 exit 1 한다 (CI 용).

측정값을 이 스크립트에 하드코딩하지 않는다. 전부 산출물에서 읽는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 판정 축이 provisional 인 조건. 산출물의 judge.human_validation 이 이 값이면
# 아무리 점수가 좋아도 확정 수치로 내지 않는다.
UNVALIDATED = "not performed"


def load(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def fraction(num: Optional[int], den: Optional[int]) -> str:
    if not den:
        return "-"
    return f"{num}/{den} = {num/den:.4f}"


def collect(base: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for summary_path in sorted(base.glob("results/*/*/language/*/summary.json")):
        track = summary_path.parent.name
        if track not in ("functionchat", "taubench"):
            continue
        d = load(summary_path)
        if d is None:
            continue
        status = d.get("publish_status") or {}
        publishable = bool(status.get("publishable"))
        # 게이트 기록이 없다 = 채점기가 현재 계약으로 이 산출물을 받아들이지 못한다는 뜻이다
        # (재채점하면 실패한다). 발행 가능으로 볼 수 없다.
        if not status:
            publishable = False
        run = summary_path.parent.parent.parent
        row = {
            "model": run.parent.name,
            "run": run.name,
            "track": track,
            "publishable": publishable,
            "failures": status.get("failures") or [],
            "has_gate_record": bool(status),
        }
        if track == "functionchat":
            o = d.get("overall") or {}
            row["axes"] = [("exact", o.get("passed"), o.get("measured"), False)]
            judge = load(summary_path.parent / "judge.json")
            if judge:
                jo = judge.get("overall") or {}
                unvalidated = (judge.get("judge") or {}).get("human_validation") == UNVALIDATED
                row["axes"].append(("judged", jo.get("passed"), jo.get("judged"), unvalidated))
                row["judge_errors"] = jo.get("judge_errors")
                row["unstable"] = jo.get("unstable")
        else:
            row["axes"] = []
            for domain, entry in sorted((d.get("by_domain") or {}).items()):
                if not isinstance(entry, dict) or entry.get("status") != "measured":
                    continue
                row["axes"].append(
                    (domain, entry.get("passed"), entry.get("measured"), False)
                )
                row["runnable"] = entry.get("runnable_tasks")
        rows.append(row)
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, default=Path("foundation_model_test_non_thinking"))
    ap.add_argument("--strict", action="store_true", help="거부된 런이 있으면 exit 1")
    ap.add_argument("--show-rejected", action="store_true", default=True)
    args = ap.parse_args(argv)

    rows = collect(args.base)
    if not rows:
        print("산출물이 없습니다.", file=sys.stderr)
        return 2

    published = [r for r in rows if r["publishable"]]
    rejected = [r for r in rows if not r["publishable"]]
    no_record = [r for r in rows if not r["has_gate_record"]]

    print("=" * 78)
    print("발행 가능 (publish_status.publishable == true)")
    print("=" * 78)
    for r in sorted(published, key=lambda x: (x["track"], x["model"], x["run"])):
        head = f"  [{r['track']}] {r['model']} / {r['run']}"
        print(head)
        for name, num, den, provisional in r["axes"]:
            tag = "  ** PROVISIONAL — 판정기 기준, 인간 검증 없음 **" if provisional else ""
            print(f"      {name:<12} {fraction(num, den)}{tag}")
        if r.get("judge_errors") is not None:
            print(f"      (판정 불가 {r['judge_errors']}, 불안정 {r.get('unstable')})")

    if rejected and args.show_rejected:
        print()
        print("=" * 78)
        print("발행 불가 — 점수를 인용하지 마십시오")
        print("=" * 78)
        for r in sorted(rejected, key=lambda x: (x["track"], x["model"], x["run"])):
            print(f"  [{r['track']}] {r['model']} / {r['run']}")
            reasons = r["failures"] or [
                "게이트 기록 없음 — 현재 채점 계약으로 재채점되지 않는 낡은 산출물"
            ]
            for f in reasons:
                print(f"      X {f}")

    if no_record:
        print()
        print("  ⚠️  게이트 기록이 없는 런 (재채점하세요):")
        for r in no_record:
            print(f"      {r['model']}/{r['run']}/{r['track']}")

    print()
    print(f"  발행 가능 {len(published)} / 거부 {len(rejected)} / 게이트 기록 없음 {len(no_record)}")
    print("  상세 판단 기준: AGENT_TRACK_CLOSEOUT.md")

    if args.strict and (rejected or no_record):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
