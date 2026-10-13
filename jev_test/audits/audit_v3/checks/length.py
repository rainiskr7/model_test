"""R2v3: exact JSON bytes under all three tokenizers and both request methods."""

import math
import sys

from tokenizers import Tokenizer

from common.request import serialize
from config import TOKEN_LIMIT


def percentile(ordered, fraction):
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize(lengths, requests):
    if not lengths:
        raise ValueError("Cannot measure an empty request list")
    ordered = sorted(lengths)
    exceeded = [i for i, size in enumerate(lengths) if size > TOKEN_LIMIT]
    return {"status": "FAIL" if exceeded else "PASS", "numerator": len(exceeded),
            "denominator": len(lengths), "p50": percentile(ordered, 0.5),
            "p95": percentile(ordered, 0.95), "max": ordered[-1], "threshold": TOKEN_LIMIT,
            "examples": [{"dialogue_id": requests[i]["dialogue_id"], "turn_index": requests[i]["turn_index"],
                          "tokens": lengths[i]} for i in exceeded[:5]]}


def check(variants, tokenizer_paths):
    tokenizers = {}
    for name, path in tokenizer_paths.items():
        tokenizer = Tokenizer.from_file(str(path))
        tokenizer.no_truncation()
        tokenizer.no_padding()
        tokenizers[name] = tokenizer
    count = len(next(iter(variants.values())))
    if any(len(rows) != count for rows in variants.values()):
        raise ValueError("Length variants have different request counts")
    lengths = {variant: {name: {"clef": [], "pplx": []} for name in tokenizers} for variant in variants}
    for start in range(0, count, 16):
        texts, text_index, spans = [], {}, {}

        def add_text(text):
            if text not in text_index:
                text_index[text] = len(texts)
                texts.append(text)
            return text_index[text]

        for variant, requests in variants.items():
            spans[variant] = []
            for request in requests[start:start + 16]:
                state, questions = request["state"], request["questions"]
                if not questions:
                    raise ValueError("Length check received empty questions")
                full = add_text(serialize(state, questions))
                singles = [add_text(serialize(state, {qid: q})) for qid, q in questions.items()]
                spans[variant].append((full, singles))
        # Identical text shared between variants is encoded once per tokenizer.
        # All six variant/tokenizer combinations still receive both measurements.
        for name, tokenizer in tokenizers.items():
            encodings = tokenizer.encode_batch(texts, add_special_tokens=False)
            sizes = [len(encoding.ids) for encoding in encodings]
            del encodings
            for variant, entries in spans.items():
                for full, singles in entries:
                    lengths[variant][name]["clef"].append(sizes[full])
                    lengths[variant][name]["pplx"].append(max(sizes[i] for i in singles))
        done = min(start + 16, count)
        if done % 256 == 0 or done == count:
            print(f"[R2v3] {done}/{count} requests, both variants", file=sys.stderr, flush=True)
    results = {}
    for variant, measurements in lengths.items():
        tables = {name: {method: summarize(values, variants[variant]) for method, values in modes.items()}
                  for name, modes in measurements.items()}
        rows = [row for modes in tables.values() for row in modes.values()]
        results[variant] = {"status": "PASS" if all(r["status"] == "PASS" for r in rows) else "FAIL",
                            "numerator": sum(r["numerator"] for r in rows),
                            "denominator": sum(r["denominator"] for r in rows), "measurements": tables,
                            "examples": [dict(e, tokenizer=name, method=method) for name, modes in tables.items()
                                         for method, row in modes.items() for e in row["examples"]][:5]}
    return {"status": "PASS" if all(r["status"] == "PASS" for r in results.values()) else "FAIL",
            "numerator": sum(r["numerator"] for r in results.values()),
            "denominator": sum(r["denominator"] for r in results.values()),
            "unit": "requests x variants x tokenizers x methods exceeding 8192",
            "examples": [dict(e, variant=v) for v, r in results.items() for e in r["examples"]][:5],
            "variants": results}
