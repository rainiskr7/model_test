"""Shared utilities for vsm/multimodal Korean benchmark runners — facade.

기능별 모듈로 분리하고 여기서 re-export 한다 (기존 `from common import ...` 호환 유지):
  - paths.py     : safe_model_name / get_base_dir / get_timestamp / get_results_dir / save_json / append_jsonl
  - client.py    : make_client / image_to_data_url / chat_with_image
  - cli.py       : standard_argparser
  - textnorm.py  : normalize_text / normalize_number
  - metadata.py  : get_hf_dataset_revision / get_git_commit / get_package_version /
                   get_eval_script_hash / resolve_dataset_revision / build_run_config

__main__ 은 셸 wrapper(KRETA, KOFFVQA, KO-VLM-Benchmark)용 run_config.json 작성 CLI.
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from paths import (
    safe_model_name, get_base_dir, get_timestamp, get_results_dir,
    save_json, append_jsonl,
)
from client import (
    make_client, image_to_data_url, chat_with_image,
)
from cli import (
    standard_argparser,
)
from textnorm import (
    normalize_text, normalize_number,
)
from metadata import (
    get_hf_dataset_revision, get_git_commit, get_package_version,
    get_eval_script_hash, resolve_dataset_revision, build_run_config,
    build_resume_context,
)
from shared.multimodal.publish import (
    native_sidecar_from_records,
    native_sidecar_from_source,
    summarize_records,
    write_sidecar,
)

__all__ = [
    "safe_model_name", "get_base_dir", "get_timestamp", "get_results_dir",
    "save_json", "append_jsonl",
    "make_client", "image_to_data_url", "chat_with_image",
    "standard_argparser",
    "normalize_text", "normalize_number",
    "get_hf_dataset_revision", "get_git_commit", "get_package_version",
    "get_eval_script_hash", "resolve_dataset_revision", "build_run_config",
    "build_resume_context",
    "native_sidecar_from_records", "native_sidecar_from_source",
    "summarize_records", "write_sidecar",
    "prepare_native_output", "save_native_results",
]


def prepare_native_output(script_path, model, benchmark_id, *, get_base_dir,
                          get_timestamp, get_results_dir, print_base=False):
    """Resolve output paths and print the native runner startup messages."""
    base_dir = get_base_dir(script_path)
    ts = get_timestamp(base_dir)
    out_dir = get_results_dir(base_dir, model, ts, benchmark_id)
    print(f"[{benchmark_id}] model={model}")
    if print_base:
        print(f"[{benchmark_id}] base={base_dir}")
    print(f"[{benchmark_id}] out={out_dir}")
    return base_dir, out_dir


def save_native_results(out_dir, base_dir, results, summary, *, benchmark_id,
                        expected_count, save_json, native_sidecar_from_records,
                        write_sidecar):
    """Save native records, summary and sidecar in their existing order."""
    save_json(out_dir / "results.json", results)
    save_json(out_dir / "summary.json", summary)
    sidecar_path, sidecar = native_sidecar_from_records(
        out_dir, base_dir, results,
        benchmark_id=benchmark_id, expected_count=expected_count,
    )
    write_sidecar(sidecar_path, sidecar)
    return sidecar


# ── CLI: 셸 wrapper(KRETA, KOFFVQA, KO-VLM-Benchmark)에서 run_config.json 작성 ──
# Usage:
#   python common.py --out PATH --benchmark NAME --model M --base-url URL \
#                    [--dataset-id ID] [--repo-dir DIR] \
#                    [--temperature T] [--max-tokens N]
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Write run_config.json for shell-based bench wrappers")
    ap.add_argument("--out", required=True, help="run_config.json 경로")
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--dataset-id", default=None)
    ap.add_argument("--repo-dir", default=None)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--max-tokens", type=int, default=None)
    args = ap.parse_args()

    cfg = build_run_config(
        benchmark=args.benchmark,
        model=args.model,
        base_url=args.base_url,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        dataset_id=args.dataset_id,
        repo_dir=Path(args.repo_dir) if args.repo_dir else None,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(out_path, cfg)
    print(f"[run_config] {out_path}")
