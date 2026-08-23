#!/usr/bin/env python3
"""FunctionChat raw artifacts를 deterministic ``summary.json``으로 채점한다."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

if __package__:
    from .exact_match import CALL, exact_match
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from exact_match import CALL, exact_match


SCORING_VERSION = "functionchat_exact_v2"  # v1=600항목, v2=670항목(dialog call 70턴 추가)
# dialog 는 45개 시나리오를 200개 평가 턴으로 펼친 것이다 (상류도 턴 단위로 평가한다).
# 그중 call 70턴만 exact-match 로 채점되고 나머지 130턴은 판정 모델이 필요하다.
REQUIRED_DATASETS = ("singlecall", "call_decision")
# dialog 는 2026-08-23 에 추가됐다. 그 이전 산출물에는 없으므로 선택적으로 읽어
# 하위 호환을 유지한다 — 없으면 v1(600항목)로, 있으면 v2(670항목)로 채점한다.
OPTIONAL_DATASETS = ("dialog",)
RAW_DATASETS = REQUIRED_DATASETS + OPTIONAL_DATASETS
INTEGRITY_FIELDS = (
    "model",
    "request_timeout",
    "task_timeout",
    "max_retries",
    "max_tokens",
    "native_tool_calling",
    "sdk_max_retries",
    "openai_sdk_version",
)


def safe_model_name(model: str) -> str:
    return model.replace("/", "_").replace("-", "_").replace(":", "_")


def score_items(items: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    measured = passed = failed = generation_errors = 0
    not_measured: Dict[str, int] = {}
    for item in items:
        output_type = item.get("type_of_output")
        if output_type != CALL:
            key = str(output_type or "unknown")
            not_measured[key] = not_measured.get(key, 0) + 1
            continue
        # **API 실패를 모델 실패로 세지 않는다.** 러너는 호출이 끝내 실패하면 error 를
        # 남기고 model_output 을 비운 채 항목을 저장한다. 그대로 채점하면 타임아웃
        # 하나가 모델 오답 하나로 둔갑한다.
        #
        # 응답은 정상인데 툴 호출이 없는 것(raw_response 있음, error 없음)은 진짜 모델
        # 실패이므로 그대로 채점한다. 둘을 가르는 것이 error/raw_response 다.
        if item.get("error") is not None or item.get("raw_response") is None:
            generation_errors += 1
            continue
        measured += 1
        if exact_match(dict(item), item.get("model_output")):
            passed += 1
        else:
            failed += 1
    return {
        "accuracy": passed / measured if measured else None,
        "measured": measured,
        "passed": passed,
        "failed": failed,
        # API 실패로 채점에서 제외된 항목. 0 이 아니면 게이트가 발행을 막는다.
        "generation_errors": generation_errors,
        "not_measured": dict(sorted(not_measured.items())),
    }


def _identity(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _shared_integrity(raw_by_dataset: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    metadata = {
        name: dict(data.get("metadata") or {}) for name, data in raw_by_dataset.items()
    }
    shared: Dict[str, Any] = {}
    for field in INTEGRITY_FIELDS:
        values = {name: meta.get(field) for name, meta in metadata.items()}
        if any(field not in meta for meta in metadata.values()):
            raise ValueError(f"raw metadata.{field} missing: {values}")
        if len({_identity(value) for value in values.values()}) != 1:
            raise ValueError(f"raw metadata.{field} disagrees across datasets: {values}")
        shared[field] = next(iter(values.values()))
    return shared


def build_summary(
    raw_by_dataset: Mapping[str, Mapping[str, Any]],
    coverage: Mapping[str, Any],
    track: str,
) -> Dict[str, Any]:
    missing = [name for name in REQUIRED_DATASETS if name not in raw_by_dataset]
    if missing:
        raise ValueError(f"raw dataset artifacts missing: {missing}")

    present = [name for name in RAW_DATASETS if name in raw_by_dataset]
    integrity = _shared_integrity(raw_by_dataset)
    by_dataset = {
        name: score_items(raw_by_dataset[name].get("results") or [])
        for name in present
    }
    measured = sum(entry["measured"] for entry in by_dataset.values())
    passed = sum(entry["passed"] for entry in by_dataset.values())
    failed = sum(entry["failed"] for entry in by_dataset.values())

    declared_not_measured = coverage.get("not_measured") or {}
    decision_declared = dict(declared_not_measured.get("call_decision") or {})
    decision_observed = by_dataset["call_decision"]["not_measured"]
    if decision_declared != decision_observed:
        raise ValueError(
            "CallDecision not-measured counts disagree: "
            f"coverage={decision_declared}, raw={decision_observed}"
        )
    dialog_declared = dict(declared_not_measured.get("dialog") or {})
    # call_decision 과 마찬가지로 선언값을 관측값과 대조한다. 예전에는 dialog 만
    # 그냥 믿었고, 러너가 시나리오 수(45)를 적는 바람에 판정 필요 항목이 130 대신
    # 45 로 집계돼 total_items 가 551(실제 636)로 발행됐다.
    if "dialog" in by_dataset:
        dialog_observed = by_dataset["dialog"]["not_measured"]
        if dialog_declared != dialog_observed:
            raise ValueError(
                "Dialog not-measured counts disagree: "
                f"coverage={dialog_declared}, raw={dialog_observed}"
            )
    not_measured_total = sum(decision_declared.values()) + sum(dialog_declared.values())

    return {
        "benchmark": "kakao/FunctionChat-Bench (call exact match)",
        "model": integrity["model"],
        "track": track,
        # dialog 유무로 버전이 갈린다. 600항목 산출물을 v2 로 표기하면 안 된다.
        "scoring_version": (
            SCORING_VERSION if "dialog" in by_dataset else "functionchat_exact_v1"
        ),
        "native_tool_calling": integrity["native_tool_calling"],
        "harness_integrity": integrity,
        "overall": {
            "accuracy": passed / measured if measured else None,
            "measured": measured,
            "passed": passed,
            "failed": failed,
        },
        "by_dataset": by_dataset,
        "not_measured": {
            "score": None,
            "status": "judge_missing",
            "in_score": False,
            "reason": "These output types require an LLM judge and are outside this exact-match track.",
            "total_items": not_measured_total,
            "by_dataset": {
                "call_decision": decision_declared,
                "dialog": dialog_declared,
            },
        },
        "coverage": dict(coverage.get("datasets") or {}),
        "source": dict(coverage.get("source") or {}),
    }


def _load(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _write_atomic(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _results_dir(args: argparse.Namespace) -> Path:
    if args.results_dir:
        return args.results_dir.resolve()
    base = Path(os.environ.get("MODEL_TEST_BASE") or Path(__file__).resolve().parents[3])
    timestamp = args.timestamp or os.environ.get("EVAL_TIMESTAMP")
    if not args.model or not timestamp:
        raise ValueError("--model and --timestamp (or EVAL_TIMESTAMP) are required")
    return base / "results" / safe_model_name(args.model) / timestamp / "language" / args.track


def parse_args(argv: List[str] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model")
    parser.add_argument("--timestamp")
    parser.add_argument("--track", default="functionchat")
    parser.add_argument("--results-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


# 데이터셋별 기대 항목 수. FunctionChat-Bench @ 5ddb0b5 의 고정 크기다
# (singlecall = 25줄 x 4질의 x 5툴셋, call_decision 의 call 유형 = 100).
# 부분 실행을 완주로 착각하지 않기 위한 앵커다.
EXPECTED_MEASURED = {"singlecall": 500, "call_decision": 100, "dialog": 70}

EXIT_CODE_HELP = """exit codes:
  0  summary produced and publishable
  1  scoring completed but the summary is unusable (nothing measured / incomplete / total failure)
  2  invocation, configuration, input-reading, or internal error"""


def validate_summary(summary: dict) -> tuple:
    """발행 가능 여부를 판정한다. (failures, warnings) 를 돌려준다.

    failures 가 비어있지 않으면 그 요약은 점수로 읽으면 안 된다. 채점 자체가 성공해도
    (예: 인증 실패로 전 항목이 죽었는데 형식상 600건이 '측정' 된 경우) 여기서 잡는다.
    """
    failures = []
    warnings = []

    overall = summary.get("overall") or {}
    measured = overall.get("measured")
    passed = overall.get("passed")

    if not measured:
        failures.append("overall.measured 가 0 이다 — 측정된 항목이 없다")
    elif passed == 0:
        # 인증 실패/엔드포인트 오류의 전형적 서명. 진짜 0점과 구분이 안 되므로 발행을 막는다.
        failures.append(
            f"측정 {measured}건이 전부 실패했다 (passed=0) — 모델 성능이 아니라 "
            "인프라 장애일 가능성이 높다"
        )

    for name, expected in EXPECTED_MEASURED.items():
        entry = (summary.get("by_dataset") or {}).get(name)
        if entry is None:
            # dialog 는 선택적이다 (v1 산출물에는 없다). 필수 데이터셋만 실패로 본다.
            if name in REQUIRED_DATASETS:
                failures.append(f"by_dataset.{name} 이 없다")
            continue
        got = entry.get("measured")
        if got != expected:
            failures.append(
                f"by_dataset.{name}.measured = {got}, 기대값 {expected} — 부분 실행이다"
            )

    for name, entry in sorted((summary.get("by_dataset") or {}).items()):
        n_err = (entry or {}).get("generation_errors") or 0
        if n_err:
            failures.append(
                f"by_dataset.{name}: 생성 실패 {n_err}건 — API 오류를 모델 실패로 "
                "세지 않으려고 채점에서 제외했다. 완전 측정이 아니다"
            )

    if summary.get("native_tool_calling") is not True:
        # 텍스트 모드는 조용한 성능 저하 경로다. 점수는 유효하지만 다른 런과 비교하면 안 된다.
        warnings.append(
            "native_tool_calling 이 True 가 아니다 — 프롬프트 주입 경로로 측정됐다. "
            "native 런과 직접 비교하지 말 것"
        )

    return failures, warnings


def main(argv: List[str] = None) -> int:
    try:
        args = parse_args(argv)
        results_dir = _results_dir(args)
        raw = {}
        for name in RAW_DATASETS:
            path = results_dir / f"{name}.json"
            if path.exists():
                raw[name] = _load(path)
            elif name in REQUIRED_DATASETS:
                raise FileNotFoundError(f"required raw artifact missing: {path}")
        coverage = _load(results_dir / "coverage.json")
        summary = build_summary(raw, coverage, args.track)
        for name, entry in summary["by_dataset"].items():
            print(
                f"[functionchat-scoring] {name}: {entry['passed']}/{entry['measured']} "
                f"accuracy={entry['accuracy']:.6f}"
            )
        overall = summary["overall"]
        print(
            f"[functionchat-scoring] overall: {overall['passed']}/{overall['measured']} "
            f"accuracy={overall['accuracy']:.6f}; "
            f"not_measured={summary['not_measured']['total_items']}"
        )
        failures, warnings = validate_summary(summary)
        for warning in warnings:
            print(f"[functionchat-scoring] WARN: {warning}", file=sys.stderr)
        for failure in failures:
            print(f"[functionchat-scoring] FAIL: {failure}", file=sys.stderr)

        summary["publish_status"] = {
            "publishable": not failures,
            "failures": list(failures),
            "warnings": list(warnings),
            "gate_scoring_version": summary.get("scoring_version"),
        }
        if not args.dry_run:
            # 발행 불가여도 산출물은 남긴다 — 진단에 필요하다.
            _write_atomic(results_dir / "summary.json", summary)
            print(f"[functionchat-scoring] wrote {results_dir / 'summary.json'}")

        if failures:
            print(
                f"[functionchat-scoring] NOT PUBLISHABLE: {len(failures)}건의 검증 실패",
                file=sys.stderr,
            )
            return 1
        return 0
    except Exception as exc:
        print(f"[functionchat-scoring] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
