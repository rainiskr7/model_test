"""입력: 오프라인 HF 캐시/저장 manifest·행. 출력: 검증된 문항·이미지 manifest."""

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys

DATASETS = {
    "k_mmbench": ("NCSOFT/K-MMBench", "03d682e76405292ac5194b6289feb85ef5c4d98b",
                  "dev", "NCSOFT___k-mm_bench", "k-mm_bench"),
    "mtvqa_kr": ("ByteDance/MTVQA", "7cdca63ec6cd71cdd0b52f79fc3176bb9ce36a9c",
                 "test", "ByteDance___mtvqa", "mtvqa"),
    "k_dtcbench": ("NCSOFT/K-DTCBench", "62128c281b7fcbd5af77593a6b65aa385554cb71",
                   "test", "NCSOFT___k-dtc_bench", "k-dtc_bench"),
}

def content_digest(question, answer):
    """질문·정답을 받아 순서가 고정된 SHA256을 반환한다."""
    return hashlib.sha256(json.dumps([question, answer], ensure_ascii=False).encode()).hexdigest()

def manifest_counts(items):
    """문항 map을 받아 문항·이미지·순환 사본 분포를 반환한다."""
    groups = defaultdict(list)
    for item in items.values():
        groups[item["group"]].append(item)
    return {"items": len(items), "groups": len(groups),
            "images": len({v["cluster"] for v in items.values()}),
            "variants": dict(sorted(Counter(str(len(v)) for v in groups.values()).items())),
            "four_options_three_variants": sum(
                len(v) == 3 and items.get(g, v[0]).get("options") == 4 for g, v in groups.items()),
            "mixed_option_groups": sum(len({x.get("options") for x in v}) > 1 for v in groups.values())}

def build_manifest(bench, rows, provenance):
    """원본 행·생성 근거를 받아 파일 쓰기 없이 manifest를 만든다."""
    dataset, revision, split, _, _ = DATASETS[bench]
    items, images, groups = {}, {}, defaultdict(list)
    korean_row = 0
    for row in rows:
        if bench == "mtvqa_kr" and row["lang"].lower() not in ("kr", "ko", "korean"):
            continue
        image_sha = hashlib.sha256(row["image"]["bytes"]).hexdigest()
        cluster = image_sha[:16]
        if cluster in images and images[cluster] != image_sha:
            raise ValueError("image hash prefix collision")
        images[cluster] = image_sha
        if bench == "mtvqa_kr":
            pairs = ast.literal_eval(row["qa_pairs"]) if isinstance(row["qa_pairs"], str) else row["qa_pairs"]
            entries = [(f'{row["id"]}\t{i}', row["id"], q["question"], q["answer"],
                        {"id": row["id"], "qa_idx": i, "row_idx": korean_row})
                       for i, q in enumerate(pairs)]
            korean_row += 1
        else:
            key = str(row["index"])
            group = str(int(key) % 1_000_000) if bench == "k_mmbench" else key
            extra = {"options": sum(row.get(c) is not None for c in "ABCD")} if bench == "k_mmbench" else {}
            entries = [(key, group, row["question"], row["answer"], extra)]
        for key, group, question, answer, extra in entries:
            if key in items or not isinstance(question, str) or not isinstance(answer, str):
                raise ValueError("duplicate key or non-string dataset question/answer")
            items[key] = {"group": group, "cluster": cluster,
                          "content_sha256": content_digest(question, answer), **extra}
            groups[group].append(key)
    value = {"schema_version": 1, "benchmark": bench, "dataset": dataset, "revision": revision,
             "split": split, "items": items, "groups": dict(groups), "images": images,
             "counts": manifest_counts(items), "provenance": provenance}
    validate_manifest(value)
    return value

def validate_manifest(value):
    """manifest 객체의 내부 정합성을 검사하고 잘못되면 ValueError를 낸다."""
    bench = value.get("benchmark") if isinstance(value, dict) else None
    if bench not in DATASETS or value.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema/benchmark")
    dataset, revision, split, _, _ = DATASETS[bench]
    if (value.get("dataset"), value.get("revision"), value.get("split")) != (dataset, revision, split):
        raise ValueError("manifest dataset identity mismatch")
    items, images, groups = value["items"], value["images"], defaultdict(list)
    if not items or not isinstance(items, dict):
        raise ValueError("empty/invalid manifest items")
    for key, item in items.items():
        group, cluster = item["group"], item["cluster"]
        sha = images[cluster]
        if len(sha) != 64 or sha[:16] != cluster or len(item["content_sha256"]) != 64:
            raise ValueError("invalid manifest hash")
        if bench == "k_mmbench" and (str(int(key)) != key or int(key) < 0 or group != str(int(key) % 1_000_000)):
            raise ValueError("invalid circular key")
        if bench == "mtvqa_kr" and (key != f'{item["id"]}\t{item["qa_idx"]}' or group != item["id"]):
            raise ValueError("invalid MTVQA key")
        groups[group].append(key)
    if {k: sorted(v) for k, v in groups.items()} != {k: sorted(v) for k, v in value["groups"].items()}:
        raise ValueError("manifest group membership mismatch")
    if any(len({items[k]["cluster"] for k in keys}) != 1 for keys in groups.values()):
        raise ValueError("group spans different images")
    if value["counts"] != manifest_counts(items) or set(images) != {v["cluster"] for v in items.values()}:
        raise ValueError("manifest counts/images mismatch")

def record_issues(rows, manifest):
    """저장 행·manifest를 받아 원문을 노출하지 않는 검증 문제 목록을 반환한다."""
    expected, seen, issues = manifest["items"], set(), []
    for position, row in enumerate(rows):
        try:
            if manifest["benchmark"] == "mtvqa_kr":
                gold = row["gold"]
                if not isinstance(gold, list) or len(gold) != 1 or not isinstance(gold[0], str):
                    raise ValueError("singleton_string_gold_required")
                key, answer = f'{row["id"]}\t{row["qa_idx"]}', gold[0]
            else:
                index = row["index"]
                if manifest["benchmark"] == "k_mmbench" and type(index) is not int:
                    raise ValueError("integer_index_required")
                key, answer = str(index), row["answer"]
            if key not in expected:
                raise ValueError("unexpected_item")
            if key in seen:
                raise ValueError("duplicate_item")
            seen.add(key)
            if content_digest(row["question"], answer) != expected[key]["content_sha256"]:
                raise ValueError("question_or_gold_mismatch")
            if manifest["benchmark"] == "mtvqa_kr" and any(
                type(row[k]) is not int or row[k] != expected[key][k] for k in ("row_idx", "qa_idx")
            ):
                raise ValueError("image_or_qa_position_mismatch")
        except (KeyError, TypeError):
            issues.append({"row": position, "reason": "invalid_record"})
        except ValueError as exc:
            issues.append({"row": position, "reason": str(exc)})
    if seen != set(expected):
        issues.append({"reason": "missing_items", "count": len(set(expected) - seen)})
    return issues

def load_manifest(bench, revision, directory=None):
    """벤치·revision으로 고정 JSON을 읽어 검증하고 객체와 파일 SHA를 반환한다."""
    if bench not in DATASETS or revision != DATASETS[bench][1]:
        raise ValueError("unsupported dataset revision")
    root = Path(directory) if directory is not None else Path(__file__).with_name("manifests")
    raw = (root / f"{bench}_{revision}.json").read_bytes()
    value = json.loads(raw)
    try:
        validate_manifest(value)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("malformed manifest") from exc
    if value["benchmark"] != bench:
        raise ValueError("manifest benchmark mismatch")
    return value, hashlib.sha256(raw).hexdigest()

def read_cache(bench, cache_root):
    """고정 revision의 Arrow 캐시만 읽고 원본 행과 파일 SHA 근거를 반환한다."""
    if any(os.environ.get(k) != "1" for k in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE")):
        raise ValueError("HF_DATASETS_OFFLINE=1 and HF_HUB_OFFLINE=1 required")
    import pyarrow.ipc as ipc

    _, revision, split, folder, stem = DATASETS[bench]
    directory = Path(cache_root) / folder / "default" / "0.0.0" / revision
    paths = sorted(directory.glob(f"{stem}-{split}*.arrow"))
    if not paths:
        raise ValueError("offline Arrow cache missing")
    rows, sources = [], []
    for path in paths:
        with path.open("rb") as stream:
            table = ipc.open_stream(stream).read_all()
            if bench == "mtvqa_kr":
                table = table.filter([lang.lower() in ("kr", "ko", "korean")
                                      for lang in table["lang"].to_pylist()])
            rows.extend(table.to_pylist())
            stream.seek(0)
            sources.append({"name": path.name, "sha256": hashlib.file_digest(stream, "sha256").hexdigest()})
    return rows, {"builder": "manifest.py:v1", "offline": True, "cache_files": sources,
                  "image_hash": "SHA256 of cached image bytes; first 16 hex; collisions checked"}

def main(argv=None):
    """--build 요청을 받아 revision을 확인하고 커밋 가능한 JSON 하나를 쓴다."""
    from shared.multimodal.rescore.sessions import check_revisions, write_output

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, choices=DATASETS)
    parser.add_argument("--base", type=Path, default=Path.cwd())
    parser.add_argument("--cache-dir", type=Path, default=Path(os.environ.get(
        "HF_DATASETS_CACHE", str(Path(os.environ.get("HF_HOME", "~/.cache/huggingface")).expanduser() / "datasets"))))
    args = parser.parse_args(argv)
    try:
        count = check_revisions(args.base, args.build, DATASETS[args.build][1])
        rows, provenance = read_cache(args.build, args.cache_dir)
        provenance["tracked_summaries_verified"] = count
        value = build_manifest(args.build, rows, provenance)
        target = Path(__file__).with_name("manifests") / f"{args.build}_{value['revision']}.json"
        write_output(target, value, args.base)
        print(json.dumps({"path": str(target), "revision": value["revision"], **value["counts"]}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print("manifest build rejected: offline cache/identity invalid", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
