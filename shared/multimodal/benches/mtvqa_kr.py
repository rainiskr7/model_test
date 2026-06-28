"""MTVQA (ByteDance) — Multilingual Text-centric VQA, **Korean subset**.

원본 9개 언어 중 lang=KR 또는 language=Korean 만 필터.
Free-form VQA (정답 짧은 문자열). 메트릭: normalized exact match.
Source: https://huggingface.co/datasets/ByteDance/MTVQA
"""

import re
import unicodedata

try:
    from datasets import load_dataset
except ImportError as e:
    raise SystemExit("datasets 패키지 미설치 — `uv pip install datasets`") from e

from common import (
    standard_argparser, make_client, chat_with_image,
    get_base_dir, get_timestamp, get_results_dir, save_json,
    build_run_config, resolve_dataset_revision,
)


PROMPT_TEMPLATE = """{question}

이미지를 보고 위 질문에 한 단어 또는 짧은 구로 정확히 답하세요. 설명·머리말 없이 답만 출력하세요."""


def normalize_answer(s: str) -> str:
    """공백·문장부호·한글 정규화 후 소문자."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).strip()
    # 따옴표/괄호 등 양 끝 제거
    s = re.sub(r'^[\'"`「『\(\[<]+|[\'"`」』\)\]>.,!?:;]+$', "", s).strip()
    return s.lower()


def is_match(pred: str, gold: str) -> bool:
    """Pred 와 gold 매칭 (loose substring 의 false positive 줄이기 위해 단계적).

    1) Exact 일치 → PASS
    2) Word-level 매치 (gold 가 pred 의 토큰 중 하나)
    3) 긴 gold (>3 char) 만 substring 허용 (짧은 단어 false positive 회피)
    4) Pred 가 gold 의 prefix/substring (모델이 짧게 답한 경우, pred 길이 ≥2)
    """
    p, g = normalize_answer(pred), normalize_answer(gold)
    if not p or not g:
        return False
    # 1) Exact
    if p == g:
        return True
    # 2) Word-level (whitespace 토큰)
    p_tokens = re.findall(r'\S+', p)
    if g in p_tokens:
        return True
    # 3) 긴 gold (>3 char) 만 substring
    if len(g) > 3 and g in p:
        return True
    # 4) Pred 가 gold 안에 (pred 가 짧지 않음)
    if len(p) >= 2 and p in g:
        return True
    return False


def _is_korean_row(row: dict) -> bool:
    for key in ("language", "lang", "Language"):
        v = row.get(key)
        if v is None:
            continue
        s = str(v).strip().lower()
        if s in ("korean", "ko", "kr"):
            return True
    return False


def main():
    parser = standard_argparser()
    parser.add_argument("--split", type=str, default="test", help="HF split (default: test)")
    parser.add_argument("--config", type=str, default=None, help="HF config (없으면 default)")
    args = parser.parse_args()

    base_dir = get_base_dir(__file__)
    ts = get_timestamp(base_dir)
    out_dir = get_results_dir(base_dir, args.model, ts, "mtvqa_kr")

    print(f"[mtvqa_kr] model={args.model}")
    print(f"[mtvqa_kr] out={out_dir}")

    revision, rev_source = resolve_dataset_revision(
        "ByteDance/MTVQA", args.revision, "MTVQA_REVISION",
    )
    print(f"[mtvqa_kr] revision={revision} (source={rev_source})")

    # MTVQA는 multi-config 일 수 있음. 한국어 서브셋 자동 탐색.
    ds = None
    load_kwargs = {"split": args.split}
    if args.config:
        load_kwargs["name"] = args.config
    if revision:
        load_kwargs["revision"] = revision

    try:
        ds = load_dataset("ByteDance/MTVQA", **load_kwargs)
    except Exception as e:
        # 대안: Korean config 명시 시도
        for cand in ("Korean", "ko", "KR"):
            try:
                ds = load_dataset("ByteDance/MTVQA", name=cand, split=args.split,
                                  **({"revision": revision} if revision else {}))
                print(f"[mtvqa_kr] loaded config={cand}")
                break
            except Exception:
                continue
        if ds is None:
            raise SystemExit(f"MTVQA 로딩 실패: {e}")

    # 단일 config 로드 시 lang 컬럼으로 필터, Korean config 면 통과
    cols = list(ds.column_names) if hasattr(ds, "column_names") else list(ds[0].keys())
    lang_key = next((k for k in ("language", "lang", "Language") if k in cols), None)
    if lang_key:
        before = len(ds)
        # 메모리 절약: 언어 컬럼만 추출해 인덱스 결정 (이미지 안 로드)
        languages = ds[lang_key]
        korean_idx = [
            i for i, lv in enumerate(languages)
            if str(lv).strip().lower() in ("korean", "ko", "kr")
        ]
        ds = ds.select(korean_idx)
        print(f"[mtvqa_kr] korean filter → {len(ds)}/{before} (column={lang_key})")

    if args.limit:
        ds = ds.select(range(min(args.limit, len(ds))))

    client = make_client(args.base_url, args.api_key)

    results = []
    correct = 0

    # MTVQA 실제 컬럼: image, id, qa_pairs (str repr of list of dicts), lang
    sample = ds[0]
    cols = list(sample.keys())

    image_key = next((k for k in ("image", "Image") if k in cols), None)
    if image_key is None:
        raise SystemExit(f"image column not found in {cols}")

    # qa_pairs 형식 (MTVQA): str repr of list of dicts
    # 또는 일부 데이터셋은 question/answer 직접 컬럼
    qa_pairs_key = "qa_pairs" if "qa_pairs" in cols else None
    direct_q_key = next((k for k in ("question", "Question") if k in cols), None)
    direct_a_key = next((k for k in ("answer", "answers", "gt_answer", "label") if k in cols), None)

    if qa_pairs_key is None and (direct_q_key is None or direct_a_key is None):
        raise SystemExit(f"qa_pairs OR question+answer column 미존재. cols={cols}")

    import ast

    def _expand_qa(row) -> list:
        """row → list of (question, [gold_answers]). MTVQA의 qa_pairs 파싱."""
        if qa_pairs_key:
            raw = row[qa_pairs_key]
            try:
                parsed = ast.literal_eval(raw) if isinstance(raw, str) else raw
            except (ValueError, SyntaxError):
                return []
            if not isinstance(parsed, list):
                return []
            out = []
            for qa in parsed:
                if not isinstance(qa, dict):
                    continue
                q = qa.get("question") or qa.get("Q") or ""
                a = qa.get("answer") or qa.get("A") or qa.get("answers")
                if not q or a is None:
                    continue
                if isinstance(a, list):
                    gold = [str(x) for x in a]
                else:
                    gold = [str(a)]
                out.append((str(q), gold))
            return out
        # direct columns
        q = row[direct_q_key]
        a = row[direct_a_key]
        gold = [str(x) for x in a] if isinstance(a, list) else [str(a)]
        return [(str(q), gold)]

    for i, row in enumerate(ds):
        qa_list = _expand_qa(row)
        if not qa_list:
            continue

        for qa_idx, (question, gold_list) in enumerate(qa_list):
            prompt = PROMPT_TEMPLATE.format(question=question)
            try:
                response = chat_with_image(
                    client, args.model, prompt, row[image_key],
                    max_tokens=args.max_tokens, temperature=args.temperature,
                    seed=args.seed, timeout=args.timeout,
                    retry_max=args.retry_max, retry_backoff=args.retry_backoff,
                )
                err = None
            except Exception as e:
                response = ""
                err = str(e)

            is_correct = any(is_match(response, g) for g in gold_list)
            if is_correct:
                correct += 1

            results.append({
                "row_idx": i,
                "qa_idx": qa_idx,
                "id": row.get("id"),
                "question": question,
                "gold": gold_list,
                "response": response,
                "correct": is_correct,
                "error": err,
            })

        if (i + 1) % 25 == 0:
            total_q = len(results)
            print(f"[mtvqa_kr] row {i+1}/{len(ds)} (Q={total_q}) acc={correct/total_q:.3f}")

    summary = {
        "benchmark": "MTVQA-KR",
        "model": args.model,
        "total": len(results),
        "correct": correct,
        "accuracy": correct / len(results) if results else 0.0,
        "metric": "normalized exact/substring match (case-insensitive)",
        "run_config": build_run_config(
            benchmark="MTVQA-KR",
            model=args.model,
            base_url=args.base_url,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            seed=args.seed,
            timeout=args.timeout,
            retry_max=args.retry_max,
            retry_backoff=args.retry_backoff,
            dataset_id="ByteDance/MTVQA",
            dataset_revision=revision,
            dataset_revision_source=rev_source,
            eval_script_path=__file__,
            extra={
                "split": args.split,
                "config": args.config,
                "limit": args.limit,
            },
        ),
    }

    save_json(out_dir / "results.json", results)
    save_json(out_dir / "summary.json", summary)

    print(f"\n[mtvqa_kr] FINAL acc={summary['accuracy']:.3f} ({correct}/{summary['total']})")


if __name__ == "__main__":
    main()
