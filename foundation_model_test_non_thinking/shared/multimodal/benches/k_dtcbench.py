"""K-DTCBench (NCSOFT) — Korean document/table/chart multiple-choice VQA.

240 samples, 4-choice (A/B/C/D), exact match accuracy.
Source: https://huggingface.co/datasets/NCSOFT/K-DTCBench
"""

import re
import sys

try:
    from datasets import load_dataset
except ImportError as e:
    raise SystemExit("datasets 패키지 미설치 — `uv pip install datasets`") from e

from common import (
    standard_argparser, make_client, chat_with_image,
    get_base_dir, get_timestamp, get_results_dir, save_json,
    build_run_config, resolve_dataset_revision,
    native_sidecar_from_records, summarize_records, write_sidecar,
)


PROMPT_TEMPLATE = """{question}
Options: A: {A}, B: {B}, C: {C}, D: {D}

주어진 선택지 중 해당 옵션의 문자로 바로 답하세요."""
EXPECTED_COUNT = 240


def extract_choice(response: str) -> str:
    """Extract A/B/C/D from response (한국어 답변 패턴 포함). Returns '' if not found."""
    if not response:
        return ""
    s = response.strip()
    s_up = s.upper()
    # 1) 첫 문자가 letter (가장 빠른 케이스)
    if s_up and s_up[0] in "ABCD":
        return s_up[0]
    # 2) 한국어 답변 패턴 (우선순위 순)
    patterns = [
        r'정답[은:]?\s*[\(\[]?\s*([ABCD])',   # "정답: B", "정답은 B", "정답:(B)"
        r'답[은:]?\s*[\(\[]?\s*([ABCD])',     # "답: B", "답은 B"
        r'[\(\[]([ABCD])[\)\]]',              # "(B)", "[B]"
        r'\b([ABCD])\s*번',                   # "B번"
        r'\b([ABCD])\s*[\)\]\.]',             # "B)", "B]", "B."
        r'\b([ABCD])\b',                       # word-boundary fallback
    ]
    for pat in patterns:
        m = re.search(pat, s_up)
        if m:
            return m.group(1)
    return ""


def main():
    parser = standard_argparser()
    args = parser.parse_args()

    base_dir = get_base_dir(__file__)
    ts = get_timestamp(base_dir)
    out_dir = get_results_dir(base_dir, args.model, ts, "k_dtcbench")

    print(f"[k_dtcbench] model={args.model}")
    print(f"[k_dtcbench] base={base_dir}")
    print(f"[k_dtcbench] out={out_dir}")

    # HF dataset revision 결정 (강제 pin: CLI > env > latest)
    revision, rev_source = resolve_dataset_revision(
        "NCSOFT/K-DTCBench", args.revision, "K_DTCBENCH_REVISION",
    )
    print(f"[k_dtcbench] revision={revision} (source={rev_source})")

    load_kwargs = {"split": "test"}
    if revision:
        load_kwargs["revision"] = revision
    ds = load_dataset("NCSOFT/K-DTCBench", **load_kwargs)
    if args.limit:
        ds = ds.select(range(min(args.limit, len(ds))))

    client = make_client(args.base_url, args.api_key)

    results = []
    correct = 0
    by_category = {"document": [0, 0], "table": [0, 0], "chart": [0, 0]}

    for i, row in enumerate(ds):
        prompt = PROMPT_TEMPLATE.format(
            question=row["question"],
            A=row["choice_a"], B=row["choice_b"],
            C=row["choice_c"], D=row["choice_d"],
        )
        try:
            response = chat_with_image(
                client, args.model, prompt, row["image"],
                max_tokens=args.max_tokens, temperature=args.temperature,
                seed=args.seed, timeout=args.timeout,
                retry_max=args.retry_max, retry_backoff=args.retry_backoff,
            )
            err = None
        except Exception as e:
            err = str(e)
            response = {"error": err}

        pred = extract_choice(response) if isinstance(response, str) else ""
        is_correct = isinstance(response, str) and pred == row["answer"]
        if is_correct:
            correct += 1

        cat = row["category"]
        if cat not in by_category:
            by_category[cat] = [0, 0]
        by_category[cat][1] += 1
        if is_correct:
            by_category[cat][0] += 1

        results.append({
            "index": row["index"],
            "category": cat,
            "question": row["question"],
            "answer": row["answer"],
            "response": response,
            "predicted": pred,
            "correct": is_correct,
            "error": err,
        })

        if (i + 1) % 20 == 0:
            acc = correct / (i + 1)
            print(f"[k_dtcbench] {i+1}/{len(ds)} acc={acc:.3f}")

    aggregate = summarize_records("k_dtcbench", results, expected_count=EXPECTED_COUNT)
    correct = aggregate["correct"]
    summary = {
        "benchmark": "K-DTCBench",
        "model": args.model,
        "total": len(results),
        "correct": correct,
        "accuracy": correct / len(results) if results else 0.0,
        "by_category": aggregate["by_category"],
        "counts": aggregate["counts"],
        "accuracy_strict": aggregate["accuracy_strict"],
        "accuracy_conditional": aggregate["accuracy_conditional"],
        "publish_status": aggregate["publish_status"],
        "run_config": build_run_config(
            benchmark="K-DTCBench",
            model=args.model,
            base_url=args.base_url,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            seed=args.seed,
            timeout=args.timeout,
            retry_max=args.retry_max,
            retry_backoff=args.retry_backoff,
            dataset_id="NCSOFT/K-DTCBench",
            dataset_revision=revision,
            dataset_revision_source=rev_source,
            eval_script_path=__file__,
            extra={"limit": args.limit},
        ),
    }

    save_json(out_dir / "results.json", results)
    save_json(out_dir / "summary.json", summary)
    sidecar_path, sidecar = native_sidecar_from_records(
        out_dir, base_dir, results,
        benchmark_id="k_dtcbench", expected_count=EXPECTED_COUNT,
    )
    write_sidecar(sidecar_path, sidecar)

    print(f"\n[k_dtcbench] FINAL acc={summary['accuracy']:.3f} ({correct}/{summary['total']})")
    for cat, stats in summary["by_category"].items():
        print(f"  {cat}: {stats['accuracy']:.3f} ({stats['correct']}/{stats['total']})")
    return 0 if aggregate["publish_status"]["publishable"] and sidecar["publishable"] else 1


if __name__ == "__main__":
    sys.exit(main())
