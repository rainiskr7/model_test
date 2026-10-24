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
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from shared.functionchat.judge.judge_pilot import (
    JUDGE_ENDPOINT,
    ServedIdentity,
    VERDICT_SCHEMA,
    call_judge,
    rubric_digest,
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


def record_key(row: Dict[str, Any]) -> Tuple[Any, Any]:
    """항목·레코드를 가리키는 키 (dataset, serial_num). serial_num 은 데이터셋마다 따로 매겨져 겹치므로 단독으로 쓰지 않는다.
    둘 중 하나라도 없거나 None 이면 키로 쓸 수 없다 — 조용히 None 으로 묶지 않고 멈춘다."""
    dataset, serial = row.get("dataset"), row.get("serial_num")
    if dataset is None or serial is None:
        raise SystemExit(f"[judge] dataset/serial_num 이 없는 항목은 재판정 키로 쓸 수 없다: dataset={dataset!r} serial_num={serial!r}")
    return (dataset, serial)


def _require_unique_keys(rows: List[Dict[str, Any]], label: str) -> None:
    counts = Counter(record_key(r) for r in rows)
    dup = sorted(k for k, n in counts.items() if n > 1)
    if dup:
        raise SystemExit(f"[judge] {label} 에 (dataset, serial_num) 중복 {len(dup)}개 — 재판정을 시작하지 않는다: {dup[:5]}")


def select_retry_items(
    items: List[Dict[str, Any]], previous_records: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """판정 불가(judge_error) 레코드에 해당하는 항목만 고른다. 판정 API 를 부르기 **전에** 입력을 검사한다."""
    _require_unique_keys(previous_records, "기존 judge.json records")
    _require_unique_keys(items, "수집된 항목")
    unresolved = {record_key(r) for r in previous_records if r["status"] == "judge_error"}
    selected = [i for i in items if record_key(i) in unresolved]
    missing = sorted(unresolved - {record_key(i) for i in selected})
    if missing:
        raise SystemExit(f"[judge] 판정 불가 {len(missing)}건에 해당하는 원본 항목이 없다 — 재판정을 시작하지 않는다: {missing[:5]}")
    return selected


def merge_retry_records(
    previous_records: List[Dict[str, Any]], redone: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """재판정 레코드를 기존 레코드에 병합한다. 판정 불가였던 레코드만 교체할 수 있다."""
    _require_unique_keys(redone, "재판정 레코드")
    unresolved = {record_key(r) for r in previous_records if r["status"] == "judge_error"}
    redone_keys = {record_key(r) for r in redone}
    not_unresolved = sorted(redone_keys - unresolved)
    if not_unresolved:
        raise SystemExit(f"[judge] 재판정이 판정 불가가 아닌 레코드를 바꾸려 한다 — judge.json 을 쓰지 않는다: {not_unresolved[:5]}")
    merged = [r for r in previous_records if record_key(r) not in redone_keys] + list(redone)
    if Counter(record_key(r) for r in merged) != Counter(record_key(r) for r in previous_records):
        raise SystemExit("[judge] 재판정 병합 전후 (dataset, serial_num) 구성이 다르다 — judge.json 을 쓰지 않는다")
    return merged


def _parse_args(argv):
    """Parse args."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True, type=Path)
    ap.add_argument("--data-dir", type=Path, default=Path("data/FunctionChat-Bench/data"))
    ap.add_argument("--judge-model", default="openai/gpt-4.1-mini")
    ap.add_argument("--judge-provider", default=None)
    ap.add_argument("--judge-reasoning-effort", choices=("", "low", "medium", "high"), default=None)
    ap.add_argument("--judge-max-tokens", type=int, default=None)
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
    if not args.judge_model.strip():
        ap.error("--judge-model must not be empty")
    if args.judge_max_tokens is not None and args.judge_max_tokens <= 0:
        ap.error("--judge-max-tokens must be a positive integer")
    args.judge_provider = args.judge_provider or None
    args.judge_reasoning_effort = args.judge_reasoning_effort or None
    return args


def _load_api_key(args):
    """Read the required key from the selected environment variable."""
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"{args.api_key_env} 환경변수가 필요합니다 (값은 인자로 받지 않습니다).")
    return api_key


def _load_inputs(args):
    """Load rubrics and candidates and select unresolved records for retry."""
    out_path = args.results_dir / "judge.json"
    stored = None
    if out_path.exists():
        try:
            stored = json.loads(out_path.read_text(encoding="utf-8"))
            request = stored.get("judge_request")
            old = ((request["model"], request["provider"] or None,
                    request["reasoning_effort"] or None, request["max_tokens_effective"])
                   if "judge_request" in stored else (stored["judge"]["model"], None, None, 700))
            current = (args.judge_model, args.judge_provider, args.judge_reasoning_effort,
                       args.judge_max_tokens if args.judge_max_tokens is not None else 700)
            if old != current:
                print("[judge] 판정기 프로파일 불일치 — 재판정 저장 위치를 나눠라", file=sys.stderr)
                raise SystemExit(2)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f"[judge] 기존 판정 기록 확인 실패 ({type(exc).__name__}) — 쓰지 않는다", file=sys.stderr)
            raise SystemExit(2) from exc
    rubrics = load_rubrics(args.data_dir)
    items = collect_items(args.results_dir)

    # --retry-unresolved: 기존 judge.json 에서 판정 불가(동점)로 남은 항목만 다시 돈다.
    # 전체 재실행은 이미 확정된 615건까지 다시 부르는 낭비다.
    previous = None
    if args.retry_unresolved:
        if not out_path.exists():
            raise SystemExit(f"--retry-unresolved 인데 {out_path} 가 없습니다.")
        previous = stored
        items = select_retry_items(items, previous["records"])
        print(f"[judge] 재판정 대상 {len(items)}건 (기존 판정 불가)")
    return rubrics, items, previous


def _judge_item(item: Dict[str, Any], *, rubrics, args, api_key, identity):
    """Request all repeated votes for one candidate unless generation failed."""
    kind = str(item.get("type_of_output"))
    # 후보 생성이 실패한 항목은 판정하지 않는다. 판정할 응답이 없기 때문이다.
    # 그러나 **조용히 빼지도 않는다** — candidate_generation_error 로 남겨
    # 커버리지 게이트가 잡게 한다.
    if item.get("generation_failed"):
        return item, []
    prompt = render_prompt(rubrics[kind], item)
    return item, [
        call_judge(prompt, args.judge_model, api_key, args.timeout, args.retries,
                   identity=identity, provider=args.judge_provider,
                   reasoning_effort=args.judge_reasoning_effort, max_tokens=args.judge_max_tokens)
        for _ in range(args.repeats)
    ]


def _run_judgments(args, rubrics, items, api_key, identity):
    """Request candidate votes with the configured worker pool."""
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        judge_item = partial(_judge_item, rubrics=rubrics, args=args,
                             api_key=api_key, identity=identity)
        pairs = list(pool.map(judge_item, items))
    return pairs


def _aggregate_votes(pairs, item_count):
    """Aggregate votes, lost votes and errors and print progress."""
    per_type: Dict[str, Counter] = defaultdict(Counter)
    records = []
    errors = Counter()
    for index, (item, runs) in enumerate(pairs, start=1):
        kind = str(item.get("type_of_output"))
        verdicts = [r.get("verdict") for r in runs]
        for r in runs:
            if r.get("error"):
                errors["transport"] += 1
            elif r.get("verdict") is None:
                errors["parse"] += 1
        if item.get("generation_failed"):
            records.append(
                {
                    "serial_num": item.get("serial_num"),
                    "dataset": item.get("dataset"),
                    "type_of_output": kind,
                    "verdict": None,
                    "status": "candidate_generation_error",
                    "unstable": False,
                    "vote_integrity": {"requested": 0, "received": 0, "lost": 0,
                                       "single_vote": False},
                    "verdicts": [],
                    "justification_ko": None,
                }
            )
            per_type[kind]["candidate_generation_error"] += 1
            continue
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
        if index % 50 == 0 or index == item_count:
            print(f"[judge] {index}/{item_count}")
    return records, per_type, errors


def _merge_previous(previous, records, per_type):
    """Merge only unresolved records and rebuild type counts."""
    if previous is not None:
        # 재판정하지 않은 기존 레코드를 합치고 유형별 집계를 다시 만든다.
        records = merge_retry_records(previous["records"], records)
        per_type = defaultdict(Counter)
        for r in records:
            kind = r["type_of_output"]
            per_type[kind][r["verdict"] or r["status"]] += 1
            if r["unstable"]:
                per_type[kind]["unstable"] += 1
    return records, per_type


def _build_summary(args, rubrics, records, per_type, errors, identity):
    """Build judge metadata, vote distribution and aggregate metrics."""
    judged = sum(c["pass"] + c["fail"] for c in per_type.values())
    passed = sum(c["pass"] for c in per_type.values())
    summary = {
        "benchmark": "kakao/FunctionChat-Bench (LLM judge layer)",
        "scoring_version": SCORING_VERSION,
        "judge_request": {
            "model": args.judge_model,
            "provider": args.judge_provider,
            "reasoning_effort": args.judge_reasoning_effort,
            "max_tokens_requested": args.judge_max_tokens,
            "max_tokens_effective": args.judge_max_tokens if args.judge_max_tokens is not None else 700,
            "temperature": 0,
        },
        "judge": {
            "model": args.judge_model,
            # 재판정(--retry-unresolved)을 하면 항목마다 투표 수가 다르다. 단일 값으로
            # 적으면 거짓이 된다 — 2026-08-23 에 repeats=5 로 기록됐으나 실제로는
            # 623건이 2회, 13건만 5회였다. 실제 분포를 기록한다.
            "repeats_requested_this_invocation": args.repeats,
            "votes_per_item": None,  # 아래에서 실측으로 채운다
            "temperature": 0,
            "output_contract": "json_schema strict {verdict, justification_ko}",
            "rubric_source": "upstream data/rubric_{type}.txt",
            # "unmodified" 라고 적어두는 것은 주장일 뿐이다. 본문 해시를 남긴다.
            "rubric_sha256": rubric_digest(rubrics),
            "endpoint": JUDGE_ENDPOINT,
            # 요청한 alias 가 아니라 엔드포인트가 실제로 서빙했다고 보고한 값.
            "served_identity": identity.snapshot(),
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
    return summary


def _apply_publish_gate(summary, items, previous, records):
    """Record coverage failures without dropping unjudged candidates."""
    judged = summary["overall"]["judged"]
    # **발행 게이트.** 지금까지 이 스크립트는 무슨 일이 있어도 exit 0 이었다.
    # 분모가 조용히 줄어드는 것이 이 층의 주된 오염 경로이므로 코드로 막는다.
    expected = len(items) if previous is None else len(previous["records"])
    gate_failures: List[str] = []
    n_judge_err = sum(1 for r in records if r["status"] == "judge_error")
    n_gen_err = sum(1 for r in records if r["status"] == "candidate_generation_error")
    if len(records) != expected:
        gate_failures.append(
            f"레코드 수가 기대와 다르다: {len(records)} != {expected} — 항목이 조용히 사라졌다"
        )
    if judged + n_judge_err + n_gen_err != len(records):
        gate_failures.append(
            f"분해가 맞지 않는다: judged {judged} + judge_error {n_judge_err} + "
            f"generation_error {n_gen_err} != {len(records)}"
        )
    if n_judge_err:
        gate_failures.append(f"판정 불가 {n_judge_err}건 — 완전 측정이 아니다")
    if n_gen_err:
        gate_failures.append(
            f"후보 생성 실패 {n_gen_err}건 — 판정할 응답이 없다. 완전 측정이 아니다"
        )
    summary["publish_status"] = {
        "publishable": not gate_failures,
        "failures": gate_failures,
        "expected_records": expected,
    }
    return gate_failures


def _save_summary(args, summary, gate_failures):
    """Write judge JSON, print results and return the existing gate status."""
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
    for f in gate_failures:
        print(f"[judge] FAIL: {f}", file=sys.stderr)
    if gate_failures:
        print(
            f"[judge] NOT PUBLISHABLE: {len(gate_failures)}건의 검증 실패", file=sys.stderr
        )
        return 1
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Coordinate input validation, repeated judging, merging and reporting."""
    args = _parse_args(argv)
    api_key = _load_api_key(args)
    rubrics, items, previous = _load_inputs(args)
    identity = ServedIdentity()
    identity.reset(((previous or {}).get("judge") or {}).get("served_identity"))
    print(f"[judge] 대상 {len(items)}건, 판정기 {args.judge_model}, 반복 {args.repeats}")
    pairs = _run_judgments(args, rubrics, items, api_key, identity)
    records, per_type, errors = _aggregate_votes(pairs, len(items))
    records, per_type = _merge_previous(previous, records, per_type)
    summary = _build_summary(args, rubrics, records, per_type, errors, identity)
    gate_failures = _apply_publish_gate(summary, items, previous, records)
    return _save_summary(args, summary, gate_failures)


if __name__ == "__main__":
    sys.exit(main())
