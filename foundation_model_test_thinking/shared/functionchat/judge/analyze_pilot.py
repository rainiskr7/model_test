#!/usr/bin/env python3
"""판정 파일럿 분석. **합격/불합격을 선언하지 않는다** — 근거만 낸다.

내는 것:
  1. 파싱/전송 실패 건수 (0 이 아니면 나머지 수치는 의미가 없다)
  2. 약한 판정기의 반복 뒤집힘 (per-item, 유형별)
  3. 약한 판정기 vs 강한 판정기 불일치 (per-item, 유형별)
  4. 두 판정기가 내는 점수 차이

codex 지적대로 뒤집힘률은 **판정기 확률성만** 재고 타당도는 못 잰다. 강한 판정기와의
일치도 타당도의 대리 지표일 뿐 검증이 아니다. 최종 판단에는 인간 라벨이 필요하다.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def majority(verdicts):
    vs = [v for v in verdicts if v is not None]
    if not vs:
        return None
    c = Counter(vs)
    top, n = c.most_common(1)[0]
    return top if n * 2 > len(vs) else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", required=True, type=Path)
    args = ap.parse_args(argv)
    d = json.loads(args.pilot.read_text(encoding="utf-8"))
    models = d["models"]
    weak, strong = models[0], (models[1] if len(models) > 1 else None)

    errors = Counter()
    flips = defaultdict(lambda: [0, 0])      # type -> [뒤집힌 항목, 전체]
    disagree = defaultdict(lambda: [0, 0])   # type -> [불일치, 비교가능]
    score = defaultdict(lambda: Counter())

    for r in d["records"]:
        kind = r["type_of_output"]
        for model, runs in r["judges"].items():
            for run in runs:
                if run.get("error"):
                    errors[f"{model}:transport"] += 1
                elif run.get("verdict") is None:
                    errors[f"{model}:parse"] += 1

        wv = [x.get("verdict") for x in r["judges"].get(weak, [])]
        flips[kind][1] += 1
        if len({v for v in wv if v is not None}) > 1:
            flips[kind][0] += 1

        wmaj = majority(wv)
        if wmaj:
            score[weak][kind + ":" + wmaj] += 1
        if strong:
            sv = [x.get("verdict") for x in r["judges"].get(strong, [])]
            smaj = majority(sv)
            if smaj:
                score[strong][kind + ":" + smaj] += 1
            if wmaj and smaj:
                disagree[kind][1] += 1
                if wmaj != smaj:
                    disagree[kind][0] += 1

    print(f"  판정기: 약={weak}  강={strong}")
    print(f"  표본 {len(d['records'])}건, 약한 판정기 반복 {d['repeats']}회\n")

    print("  1) 파싱/전송 실패")
    print(f"     {dict(errors) if errors else '0건 — 구조화 출력이 안정적이다'}\n")

    print("  2) 약한 판정기 반복 뒤집힘 (일관성)")
    tf = tn = 0
    for kind in sorted(flips):
        f, n = flips[kind]; tf += f; tn += n
        print(f"     {kind:<12} {f}/{n} = {f/n:.1%}")
    print(f"     {'전체':<12} {tf}/{tn} = {tf/tn:.1%}\n")

    print("  3) 약 vs 강 불일치 (타당도 대리 지표)")
    td = tc = 0
    for kind in sorted(disagree):
        x, n = disagree[kind]; td += x; tc += n
        print(f"     {kind:<12} {x}/{n} = {x/n:.1%}" if n else f"     {kind:<12} 비교 불가")
    if tc:
        print(f"     {'전체':<12} {td}/{tc} = {td/tc:.1%}  (일치 {1-td/tc:.1%})\n")

    print("  4) 판정기별 통과율")
    for model in models:
        c = score[model]
        kinds = sorted({k.split(":")[0] for k in c})
        parts = []
        for kind in kinds:
            p = c[kind + ":pass"]; f = c[kind + ":fail"]
            parts.append(f"{kind} {p}/{p+f}" if p + f else f"{kind} -")
        print(f"     {model:<24} {'  '.join(parts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
