"""K-DTCBench (NCSOFT) — Korean document/table/chart multiple-choice VQA.

240 samples, 4-choice (A/B/C/D), exact match accuracy.
Source: https://huggingface.co/datasets/NCSOFT/K-DTCBench
"""

try:
    from datasets import load_dataset
except ImportError as e:
    raise SystemExit("datasets 패키지 미설치 — `uv pip install datasets`") from e

from common import (
    standard_argparser, make_client, chat_with_image,
    get_base_dir, get_timestamp, get_results_dir, save_json,
    build_run_config, resolve_dataset_revision,
)
# 객관식 답 추출은 전용 모듈에 위임 (단일 책임 — k_mmbench 와 공유).
from answer_parse import extract_choice


# thinking 모델용: 추론 허용 + 마지막 줄 정답 마커 강제 ('바로 답하세요' 제거).
PROMPT_TEMPLATE = """{question}
Options: A: {A}, B: {B}, C: {C}, D: {D}

단계별로 신중히 추론한 뒤, 마지막 줄에 반드시 '정답: X' 형식으로 답하세요 (X는 A/B/C/D 중 하나)."""


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
                top_p=args.top_p, top_k=args.top_k,
                seed=args.seed, timeout=args.timeout,
                retry_max=args.retry_max, retry_backoff=args.retry_backoff,
            )
            err = None
        except Exception as e:
            response = ""
            err = str(e)

        pred = extract_choice(response)
        is_correct = pred == row["answer"]
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

    summary = {
        "benchmark": "K-DTCBench",
        "model": args.model,
        "total": len(results),
        "correct": correct,
        "accuracy": correct / len(results) if results else 0.0,
        "by_category": {
            cat: {"correct": c, "total": t, "accuracy": (c / t) if t else 0.0}
            for cat, (c, t) in by_category.items()
        },
        "run_config": build_run_config(
            benchmark="K-DTCBench",
            model=args.model,
            base_url=args.base_url,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            top_p=args.top_p,
            top_k=args.top_k,
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

    print(f"\n[k_dtcbench] FINAL acc={summary['accuracy']:.3f} ({correct}/{summary['total']})")
    for cat, stats in summary["by_category"].items():
        print(f"  {cat}: {stats['accuracy']:.3f} ({stats['correct']}/{stats['total']})")


if __name__ == "__main__":
    main()
