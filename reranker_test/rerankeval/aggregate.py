"""결과 정리 — 계획안 7절. 2-stage A/B + native + latency 를 표로 묶는다.

출력:
  results/summary.md  — A/B 개선폭 매트릭스(모델×데이터셋), candidate 민감도, latency
  results/rerank_long.csv — long-format
점수는 절대값보다 baseline 대비 개선폭 + 모델 간 상대순위 우선(계획안 7절).
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import SETTINGS


def _load_rerank(results_dir: Path) -> list[dict]:
    d = results_dir / "rerank"
    if not d.exists():
        return []
    out = []
    for jf in sorted(d.glob("*.json")):
        try:
            out.append(json.loads(jf.read_text()))
        except Exception as exc:
            print(f"[aggregate] JSON 파싱 실패 건너뜀: {jf} ({exc})")
            continue
    return out


def _primary_value(rec: dict, which: str) -> float | None:
    """rec['baseline'|'reranked'] 에서 primary 지표값."""
    block = rec.get(which, {})
    return block.get(rec.get("primary"))


def to_markdown(rerank_recs: list[dict], latency_rows: list[dict] | None) -> str:
    out = ["# 리랭커 평가 결과 (자동 생성)\n",
           "> 계획안 7절: baseline 대비 개선폭 + 모델 간 상대순위 우선 해석.\n"]

    # A/B 매트릭스: 운영 top_n(=후보 최댓값) 기준
    if rerank_recs:
        op_n = max(r["top_n"] for r in rerank_recs)
        rows = [r for r in rerank_recs if r["top_n"] == op_n]
        tasks = sorted({r["task"] for r in rows})
        models = sorted({r["reranker"] for r in rows})
        out.append(f"\n## A/B 개선폭 (primary 지표, top_n={op_n})\n")
        out.append("| reranker | " + " | ".join(tasks) + " |")
        out.append("|" + "---|" * (len(tasks) + 1))
        for m in models:
            cells = []
            for t in tasks:
                rec = next((r for r in rows if r["reranker"] == m and r["task"] == t), None)
                if not rec:
                    cells.append("")
                    continue
                b = _primary_value(rec, "baseline")
                a = _primary_value(rec, "reranked")
                if a is None or b is None:
                    cells.append("")
                else:
                    cells.append(f"{a:.3f} ({a-b:+.3f})")
            out.append(f"| {m} | " + " | ".join(cells) + " |")
        out.append("\n_셀: reranked_primary (baseline 대비 Δ)_\n")

        # candidate 수 민감도
        out.append("\n## Candidate 수 민감도 (primary 지표)\n")
        out.append("| reranker | task | " +
                   " | ".join(f"top{n}" for n in sorted({r['top_n'] for r in rerank_recs})) + " |")
        out.append("|" + "---|" * (2 + len({r['top_n'] for r in rerank_recs})))
        ns = sorted({r['top_n'] for r in rerank_recs})
        for m in models:
            for t in tasks:
                vals = []
                for n in ns:
                    rec = next((r for r in rerank_recs
                                if r["reranker"] == m and r["task"] == t and r["top_n"] == n), None)
                    v = _primary_value(rec, "reranked") if rec else None
                    vals.append("" if v is None else f"{v:.3f}")
                out.append(f"| {m} | {t} | " + " | ".join(vals) + " |")

    if latency_rows:
        out.append("\n## Latency & 효율 (계획안 3·5절)\n")
        out.append("| reranker | mode | top_n | p50(ms) | p95(ms) | p99(ms) | qps | VRAM(GB) |")
        out.append("|---|---|---|---|---|---|---|---|")
        for r in latency_rows:
            if "error" in r:
                out.append(f"| {r['reranker']} | {r['mode']} | ERR | | | | | |")
                continue
            out.append(f"| {r['reranker']} | {r['mode']} | {r['top_n']} | {r['p50_ms']} | "
                       f"{r['p95_ms']} | {r['p99_ms']} | {r['throughput_qps']} | {r['peak_vram_gb']} |")
    return "\n".join(out) + "\n"


def write_reports(results_dir: Path | None = None, latency_json: Path | None = None) -> Path:
    rd = Path(results_dir or SETTINGS.results_dir)
    rd.mkdir(parents=True, exist_ok=True)
    rerank_recs = _load_rerank(rd)

    # long CSV
    csv = rd / "rerank_long.csv"
    headers = ["task", "reranker", "embedder", "mode", "top_n", "primary",
               "baseline_primary", "reranked_primary", "delta_primary",
               "candidate_recall", "n_queries", "p95_ms"]
    lines = [",".join(headers)]
    for r in rerank_recs:
        b = _primary_value(r, "baseline")
        a = _primary_value(r, "reranked")
        lines.append(",".join(str(x) for x in [
            r["task"], r["reranker"], r.get("embedder", ""), r["mode"], r["top_n"],
            r.get("primary", ""), "" if b is None else round(b, 4),
            "" if a is None else round(a, 4),
            "" if (a is None or b is None) else round(a - b, 4),
            round(r.get("candidate_recall", 0.0), 4),
            r.get("n_queries", ""), r.get("rerank_latency", {}).get("p95", ""),
        ]))
    csv.write_text("\n".join(lines) + "\n")

    latency_rows = None
    if latency_json and Path(latency_json).exists():
        latency_rows = json.loads(Path(latency_json).read_text())

    md = rd / "summary.md"
    md.write_text(to_markdown(rerank_recs, latency_rows))
    print(f"[aggregate] CSV  → {csv}")
    print(f"[aggregate] 요약 → {md}")
    return md
