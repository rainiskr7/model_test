#!/usr/bin/env python3
"""FunctionChat 판정 계층 파일럿.

전체 636건을 판정하기 전에 **작은 층화 표본**으로 두 가지에 답한다.

  1. 약한 판정기(gpt-4.1-mini)가 강한 판정기(gpt-4.1)와 얼마나 일치하는가
  2. 같은 판정기를 반복하면 얼마나 흔들리는가 (per-item 뒤집힘)

codex 지적을 반영한 설계:
  - 상류 파서를 이식하지 않는다. 상류는 마지막 2줄을 이어붙여 부분문자열로
    pass/fail 을 찾는데, 'compass' 에 'pass' 가 들어 있고 pass 를 fail 보다 먼저
    검사한다. 우리는 **구조화 출력(json_schema, strict)** 을 강제한다.
  - 파싱 실패를 fail 로 바꾸지 않는다. judge_parse_error 로 따로 센다.
  - 뒤집힘률만으로 발행을 결정하지 않는다. 이 스크립트는 **판단 근거를 만들 뿐**이고
    합격/불합격을 스스로 선언하지 않는다.

루브릭은 상류 것을 그대로 쓴다 (data/FunctionChat-Bench/data/rubric_*.txt).
채점 기준을 우리가 새로 쓰면 상류와 다른 것을 재게 된다.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

VERDICT_SCHEMA = {
    "name": "verdict",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["pass", "fail"]},
            "justification_ko": {"type": "string"},
        },
        "required": ["verdict", "justification_ko"],
        "additionalProperties": False,
    },
}


def load_rubrics(data_dir: Path) -> Dict[str, str]:
    rubrics = {}
    for kind in ("call", "slot", "relevance", "completion"):
        path = data_dir / f"rubric_{kind}.txt"
        rubrics[kind] = path.read_text(encoding="utf-8").strip()
    return rubrics


def render_prompt(rubric: str, item: Dict[str, Any]) -> str:
    """상류와 같은 자리표시자를 채운다 (tools/query/ground_truth/response)."""
    out = item.get("model_output") or {}
    response = {
        "content": out.get("content"),
        "tool_calls": out.get("tool_calls") or [],
    }
    return (
        rubric.replace("{tools}", json.dumps(item.get("tools"), ensure_ascii=False))
        .replace("{query}", json.dumps(item.get("messages"), ensure_ascii=False))
        .replace("{ground_truth}", json.dumps(item.get("ground_truth"), ensure_ascii=False))
        .replace("{response}", json.dumps(response, ensure_ascii=False))
    )


def call_judge(
    prompt: str, model: str, api_key: str, timeout: float, retries: int
) -> Dict[str, Any]:
    """구조화 출력으로 판정을 받는다. 실패는 fail 이 아니라 오류로 돌려준다."""
    body = json.dumps(
        {
            "model": model,
            "temperature": 0,
            "max_tokens": 700,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_schema", "json_schema": VERDICT_SCHEMA},
        }
    ).encode("utf-8")
    last_error = None
    for _ in range(max(1, retries)):
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return {
                "verdict": parsed["verdict"],
                "justification_ko": parsed.get("justification_ko"),
                "raw": content,
                "usage": payload.get("usage"),
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 - 원인을 그대로 기록한다
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(1.0)
    return {"verdict": None, "raw": None, "usage": None, "error": last_error}


def collect_items(results_dir: Path) -> List[Dict[str, Any]]:
    """판정 대상(비-call) 항목만 모은다. 응답이 없으면 제외한다."""
    items = []
    for name in ("call_decision", "dialog"):
        path = results_dir / f"{name}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("results") or []:
            if row.get("type_of_output") == "call":
                continue
            out = row.get("model_output") or {}
            if out.get("content") is None and not out.get("tool_calls"):
                continue
            items.append({**row, "dataset": name})
    return items


def stratified_sample(
    items: List[Dict[str, Any]], per_type: int, seed: int
) -> List[Dict[str, Any]]:
    """유형별로 같은 수를 뽑는다. 유형마다 판정 난이도가 다르므로 균등 추출한다."""
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        buckets[str(item.get("type_of_output"))].append(item)
    rng = random.Random(seed)
    picked: List[Dict[str, Any]] = []
    for kind in sorted(buckets):
        pool = sorted(buckets[kind], key=lambda r: str(r.get("serial_num")))
        rng.shuffle(pool)
        picked.extend(pool[:per_type])
    return picked


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data/FunctionChat-Bench/data"))
    parser.add_argument("--per-type", type=int, default=15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repeats", type=int, default=3, help="같은 판정기 반복 횟수")
    parser.add_argument("--models", default="openai/gpt-4.1-mini,openai/gpt-4.1")
    parser.add_argument("--api-key-env", default="TAUBENCH_USER_API_KEY")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args(argv)

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"{args.api_key_env} 환경변수가 필요합니다 (값은 인자로 받지 않습니다).")

    rubrics = load_rubrics(args.data_dir)
    items = collect_items(args.results_dir)
    sample = stratified_sample(items, args.per_type, args.seed)
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    print(f"[judge-pilot] 대상 {len(items)}건 중 층화 표본 {len(sample)}건, 모델 {models}")

    records = []
    for index, item in enumerate(sample, start=1):
        kind = str(item.get("type_of_output"))
        prompt = render_prompt(rubrics[kind], item)
        entry = {
            "serial_num": item.get("serial_num"),
            "dataset": item.get("dataset"),
            "type_of_output": kind,
            "judges": {},
        }
        for model in models:
            runs = []
            n = args.repeats if model == models[0] else 1
            for _ in range(n):
                runs.append(call_judge(prompt, model, api_key, args.timeout, args.retries))
            entry["judges"][model] = runs
        records.append(entry)
        if index % 5 == 0 or index == len(sample):
            print(f"[judge-pilot] {index}/{len(sample)}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "results_dir": str(args.results_dir),
                "per_type": args.per_type,
                "seed": args.seed,
                "repeats": args.repeats,
                "models": models,
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[judge-pilot] wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
