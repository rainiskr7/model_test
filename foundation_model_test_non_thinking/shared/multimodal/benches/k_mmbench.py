"""K-MMBench (NCSOFT) — Korean multimodal benchmark, 20 categories, multiple-choice.

4,329 samples (dev split), A/B/C/D, accuracy.
Source: https://huggingface.co/datasets/NCSOFT/K-MMBench

기본 동작: 전체 카테고리. 특정 카테고리만 평가하려면 --categories 인자 사용.
plan #2의 "선별" 운영을 위해 --categories 옵션 제공.
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


PROMPT_TEMPLATE_BASE = """{question}
Options: A: {A}, B: {B}, C: {C}, D: {D}

주어진 선택지 중 해당 옵션의 문자로 바로 답하세요."""

PROMPT_TEMPLATE_HINT = """Hint: {hint}

{question}
Options: A: {A}, B: {B}, C: {C}, D: {D}

주어진 선택지 중 해당 옵션의 문자로 바로 답하세요."""
EXPECTED_COUNT = 4329


def extract_choice(response: str) -> str:
    """Extract A/B/C/D from response (한국어 답변 패턴 포함). Returns '' if not found."""
    if not response:
        return ""
    s = response.strip()
    s_up = s.upper()
    if s_up and s_up[0] in "ABCD":
        return s_up[0]
    patterns = [
        r'정답[은:]?\s*[\(\[]?\s*([ABCD])',
        r'답[은:]?\s*[\(\[]?\s*([ABCD])',
        r'[\(\[]([ABCD])[\)\]]',
        r'\b([ABCD])\s*번',
        r'\b([ABCD])\s*[\)\]\.]',
        r'\b([ABCD])\b',
    ]
    for pat in patterns:
        m = re.search(pat, s_up)
        if m:
            return m.group(1)
    return ""


def main():
    parser = standard_argparser()
    parser.add_argument(
        "--categories",
        type=str,
        default=None,
        help="콤마로 구분된 카테고리 (선별 평가). 없으면 전체. "
             "예: structuralized_imagetext_understanding,attribute_recognition",
    )
    parser.add_argument(
        "--sample-mode",
        type=str,
        default="stratified",
        choices=["head", "random", "stratified"],
        help="--limit 사용 시 샘플링 방식 "
             "(stratified=카테고리별 균등 [default], random=무작위, head=앞에서부터)",
    )
    args = parser.parse_args()

    base_dir = get_base_dir(__file__)
    ts = get_timestamp(base_dir)
    out_dir = get_results_dir(base_dir, args.model, ts, "k_mmbench")

    print(f"[k_mmbench] model={args.model}")
    print(f"[k_mmbench] out={out_dir}")

    revision, rev_source = resolve_dataset_revision(
        "NCSOFT/K-MMBench", args.revision, "K_MMBENCH_REVISION",
    )
    print(f"[k_mmbench] revision={revision} (source={rev_source})")
    load_kwargs = {"split": "dev"}
    if revision:
        load_kwargs["revision"] = revision
    ds = load_dataset("NCSOFT/K-MMBench", **load_kwargs)

    if args.categories:
        cats = [c.strip() for c in args.categories.split(",") if c.strip()]
        before = len(ds)
        ds = ds.filter(lambda x: x["category"] in cats)
        print(f"[k_mmbench] filter {cats} → {len(ds)}/{before}")

    if args.limit and args.limit < len(ds):
        import random
        from collections import defaultdict
        # 카테고리별 인덱스 그룹화 (이미지 안 로드, 컬럼만)
        category_col = ds["category"]
        idx_by_cat = defaultdict(list)
        for i, c in enumerate(category_col):
            idx_by_cat[c].append(i)

        if args.sample_mode == "head":
            chosen = list(range(args.limit))
        elif args.sample_mode == "random":
            random.seed(args.seed if args.seed is not None else 42)
            chosen = random.sample(range(len(ds)), args.limit)
        else:
            # stratified (default): 카테고리당 동일 비율 + rounding loss 는 큰 카테고리에서 보충
            random.seed(args.seed if args.seed is not None else 42)
            n_cats = len(idx_by_cat)
            per_cat_base = args.limit // n_cats
            chosen = []
            for c, idxs in idx_by_cat.items():
                idxs_shuffled = idxs[:]
                random.shuffle(idxs_shuffled)
                chosen.extend(idxs_shuffled[:min(per_cat_base, len(idxs))])
            # 부족분: 큰 카테고리에서 추가
            shortfall = args.limit - len(chosen)
            if shortfall > 0:
                # 사용 안 한 인덱스 풀
                chosen_set = set(chosen)
                rest = [i for i in range(len(ds)) if i not in chosen_set]
                random.shuffle(rest)
                chosen.extend(rest[:shortfall])
            chosen.sort()  # 원본 순서 유지
            print(f"[k_mmbench] stratified sampling: {n_cats} categories × ~{per_cat_base} = {len(chosen)}")
        ds = ds.select(chosen)

    client = make_client(args.base_url, args.api_key)

    results = []
    correct = 0
    by_category: dict[str, list[int]] = {}

    for i, row in enumerate(ds):
        hint = (row.get("hint") or "").strip()
        if hint:
            prompt = PROMPT_TEMPLATE_HINT.format(
                hint=hint, question=row["question"],
                A=row["A"], B=row["B"], C=row["C"], D=row["D"],
            )
        else:
            prompt = PROMPT_TEMPLATE_BASE.format(
                question=row["question"],
                A=row["A"], B=row["B"], C=row["C"], D=row["D"],
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
        by_category.setdefault(cat, [0, 0])
        by_category[cat][1] += 1
        if is_correct:
            by_category[cat][0] += 1

        results.append({
            "index": row["index"],
            "category": cat,
            "l2_category": row.get("l2-category"),
            "question": row["question"],
            "answer": row["answer"],
            "response": response,
            "predicted": pred,
            "correct": is_correct,
            "error": err,
        })

        if (i + 1) % 50 == 0:
            print(f"[k_mmbench] {i+1}/{len(ds)} acc={correct/(i+1):.3f}")

    selected_variant = bool(args.categories or args.limit)
    expected_count = len(ds) if selected_variant else EXPECTED_COUNT
    aggregate = summarize_records("k_mmbench", results, expected_count=expected_count)
    correct = aggregate["correct"]
    summary = {
        "benchmark": "K-MMBench",
        "model": args.model,
        "total": len(results),
        "correct": correct,
        "accuracy": correct / len(results) if results else 0.0,
        "by_category": aggregate["by_category"],
        "counts": aggregate["counts"],
        "accuracy_strict": aggregate["accuracy_strict"],
        "accuracy_conditional": aggregate["accuracy_conditional"],
        "publish_status": aggregate["publish_status"],
        "publish_expected_count": expected_count,
        "run_config": build_run_config(
            benchmark="K-MMBench",
            model=args.model,
            base_url=args.base_url,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            seed=args.seed,
            timeout=args.timeout,
            retry_max=args.retry_max,
            retry_backoff=args.retry_backoff,
            dataset_id="NCSOFT/K-MMBench",
            dataset_revision=revision,
            dataset_revision_source=rev_source,
            eval_script_path=__file__,
            extra={
                "categories_filter": args.categories,
                "limit": args.limit,
                "sample_mode": args.sample_mode,
            },
        ),
    }

    save_json(out_dir / "results.json", results)
    save_json(out_dir / "summary.json", summary)
    sidecar_path, sidecar = native_sidecar_from_records(
        out_dir, base_dir, results,
        benchmark_id="k_mmbench", expected_count=expected_count,
    )
    write_sidecar(sidecar_path, sidecar)

    print(f"\n[k_mmbench] FINAL acc={summary['accuracy']:.3f} ({correct}/{summary['total']})")
    for cat in sorted(summary["by_category"].keys()):
        s = summary["by_category"][cat]
        print(f"  {cat}: {s['accuracy']:.3f} ({s['correct']}/{s['total']})")
    return 0 if aggregate["publish_status"]["publishable"] and sidecar["publishable"] else 1


if __name__ == "__main__":
    sys.exit(main())
