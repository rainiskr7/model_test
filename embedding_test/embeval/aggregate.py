"""결과 정리 — 계획안 6절. 모델 × 태스크 점수 매트릭스 + 도메인 평균 + 운영비용 표.

mteb 가 results/<group>/<model__mode>/ 아래 남긴 점수 JSON 을 수집해
CSV/마크다운 매트릭스로 만든다. 점수는 절대값보다 상대 순위 해석을 우선(계획안 6절).
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import SETTINGS, all_task_specs

# 태스크별 주 지표(계획안 4절). mteb 결과 dict 의 main_score 를 우선 쓰되,
# 명시 지표가 있으면 그것으로 라벨링한다.
PRIMARY_METRIC = {
    "STS": "spearman",
    "Classification": "accuracy",
    "Retrieval": "ndcg_at_10",
    "Clustering": "v_measure",
    "PairClassification": "ap",
}
TASK_KIND = {s.name: s.kind for s in all_task_specs()}


def _iter_result_files(results_dir: Path):
    """results/<group>/<model__mode>/**/<Task>.json 순회."""
    for group_dir in sorted(p for p in results_dir.iterdir() if p.is_dir()):
        for combo_dir in sorted(p for p in group_dir.iterdir() if p.is_dir()):
            if "__" not in combo_dir.name:
                continue
            model_key, _, mode = combo_dir.name.partition("__")
            for jf in combo_dir.rglob("*.json"):
                if jf.name == "model_meta.json":
                    continue
                yield group_dir.name, model_key, mode, jf


def _extract_score(payload: dict) -> tuple[str, float] | None:
    """mteb 결과 JSON 에서 (태스크명, 주 점수) 추출. 버전별 구조 차이 흡수.

    코덱스 리뷰 반영:
    - split 은 'test' 를 우선한다(여러 split 중 첫 번째를 임의로 집는 위험 제거).
    - 다중 subset/언어 태스크는 entry 가 여러 개다 → 첫 entry 만 집지 말고
      모든 main_score 를 평균한다(특정 subset 만 보고되는 침묵 오류 방지).
    """
    name = payload.get("task_name") or payload.get("mteb_dataset_name")
    scores = payload.get("scores")
    if name is None or not isinstance(scores, dict):
        return None
    # (평탄형: scores 바로 아래 main_score 인 경우는 아래 split 루프 뒤에서 처리)

    # split 우선순위: test > dev/validation > 그 외(정렬로 결정적)
    split_keys = list(scores.keys())
    ordered = ([k for k in ("test", "dev", "validation") if k in split_keys]
               + sorted(k for k in split_keys if k not in ("test", "dev", "validation")))

    for split in ordered:
        split_val = scores[split]
        entries = split_val if isinstance(split_val, list) else [split_val]
        mains = [e["main_score"] for e in entries
                 if isinstance(e, dict) and "main_score" in e]
        if mains:
            return name, float(sum(mains) / len(mains))  # 다중 subset 평균

    # 일부 버전: scores 바로 아래 main_score
    if "main_score" in scores:
        return name, float(scores["main_score"])
    return None


def collect_scores(results_dir: Path) -> list[dict]:
    rows = []
    for group, model_key, mode, jf in _iter_result_files(results_dir):
        try:
            payload = json.loads(jf.read_text())
        except Exception as exc:
            print(f"[aggregate] JSON 파싱 실패 건너뜀: {jf} ({exc})")
            continue
        got = _extract_score(payload)
        if got is None:
            continue
        task_name, score = got
        rows.append({
            "group": group, "model": model_key, "prompt_mode": mode,
            "task": task_name, "kind": TASK_KIND.get(task_name, "?"),
            "metric": PRIMARY_METRIC.get(TASK_KIND.get(task_name, ""), "main_score"),
            "score": round(score, 4),
        })
    return rows


def to_markdown_matrix(rows: list[dict]) -> str:
    """model×task 매트릭스(마크다운). prompt_mode 별로 섹션 분리."""
    if not rows:
        return "_(결과 없음 — 평가를 먼저 실행하세요)_\n"
    out = []
    modes = sorted({r["prompt_mode"] for r in rows})
    for mode in modes:
        mrows = [r for r in rows if r["prompt_mode"] == mode]
        tasks = sorted({r["task"] for r in mrows})
        models = sorted({r["model"] for r in mrows})
        cell = {(r["model"], r["task"]): r["score"] for r in mrows}
        out.append(f"\n### prompt_mode = `{mode}`\n")
        out.append("| model | " + " | ".join(tasks) + " | avg |")
        out.append("|" + "---|" * (len(tasks) + 2))
        for m in models:
            vals = [cell.get((m, t)) for t in tasks]
            present = [v for v in vals if v is not None]
            avg = round(sum(present) / len(present), 4) if present else None
            cells = [("" if v is None else f"{v:.4f}") for v in vals]
            out.append(f"| {m} | " + " | ".join(cells) + f" | {'' if avg is None else f'{avg:.4f}'} |")
    return "\n".join(out) + "\n"


def write_reports(results_dir: Path | None = None, cost_json: Path | None = None) -> Path:
    rd = Path(results_dir or SETTINGS.results_dir)
    rows = collect_scores(rd) if rd.exists() else []

    # CSV
    csv_path = rd / "scores_long.csv"
    rd.mkdir(parents=True, exist_ok=True)
    headers = ["group", "model", "prompt_mode", "task", "kind", "metric", "score"]
    lines = [",".join(headers)]
    for r in rows:
        lines.append(",".join(str(r[h]) for h in headers))
    csv_path.write_text("\n".join(lines) + "\n")

    # 마크다운 요약
    md = ["# 임베딩 모델 평가 결과 (자동 생성)\n",
          "> 계획안 6절: 절대값보다 모델 간 상대 순위를 우선 해석.\n",
          "## 점수 매트릭스\n", to_markdown_matrix(rows)]

    if cost_json and Path(cost_json).exists():
        md.append("\n## 운영 비용 (계획안 4·5절)\n")
        md.append(_cost_markdown(json.loads(Path(cost_json).read_text())))

    md_path = rd / "summary.md"
    md_path.write_text("\n".join(md))
    print(f"[aggregate] CSV  → {csv_path}")
    print(f"[aggregate] 요약 → {md_path}")
    return md_path


def _cost_markdown(cost_rows: list[dict]) -> str:
    cols = [("model_key", "model"), ("prompt_mode", "mode"), ("embed_dim", "dim"),
            ("fixed_latency_ms_per_batch", "lat(ms/batch)"),
            ("fixed_throughput_docs_per_s", "tput@fixed"),
            ("max_stable_batch", "max batch"),
            ("max_throughput_docs_per_s", "tput@max"),
            ("peak_vram_gb", "peak VRAM(GB)"),
            ("vectordb_gb_per_1m_docs", "VDB GB/1M")]
    out = ["| " + " | ".join(label for _, label in cols) + " |",
           "|" + "---|" * len(cols)]
    for r in cost_rows:
        if "error" in r:
            out.append(f"| {r.get('model_key','?')} | {r.get('prompt_mode','?')} | "
                       + " | ".join(["ERR"] * (len(cols) - 2)) + " |")
            continue
        out.append("| " + " | ".join(str(r.get(k, "")) for k, _ in cols) + " |")
    return "\n".join(out) + "\n"
