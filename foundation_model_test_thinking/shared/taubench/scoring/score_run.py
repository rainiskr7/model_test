#!/usr/bin/env python3
"""tau2-bench의 upstream reward records를 ``summary.json``으로 변환한다."""

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


SCORING_VERSION = "taubench_state_v1"
JUDGE_BASES = frozenset({"NL_ASSERTION", "COMMUNICATE"})
PROGRAMMATIC_BASES = frozenset({"DB", "ENV_ASSERTION", "ACTION"})
DECLARED_INVENTORY = {
    "telecom": {
        "total_records": 4592,
        "reward_basis_counts": {"ENV_ASSERTION": 4524, "ACTION+ENV_ASSERTION": 66},
    },
    "banking_knowledge": {
        "total_records": 98,
        "reward_component_counts": {"DB": 88, "ACTION": 9},
    },
    "retail": {"total_records": 116},
    "airline": {"total_records": 52},
}


def safe_model_name(model: str) -> str:
    return model.replace("/", "_").replace("-", "_").replace(":", "_")


def classify_reward_basis(basis: Iterable[str]) -> tuple[str, Optional[str]]:
    values = frozenset(str(value) for value in basis)
    if values & JUDGE_BASES:
        return "not_measured", "llm_judge_required"
    if not values:
        return "not_measured", "reward_basis_missing"
    if not values <= PROGRAMMATIC_BASES:
        return "not_measured", "unsupported_reward_basis"
    return "measured", None


def _task_basis(task: Mapping[str, Any]) -> list[str]:
    criteria = task.get("evaluation_criteria") or {}
    return sorted(str(value) for value in criteria.get("reward_basis") or [])


def _successful_call_observability(simulations: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    latencies: list[float] = []
    for simulation in simulations:
        for message in simulation.get("messages") or []:
            value = message.get("generation_time_seconds")
            if message.get("role") == "assistant" and isinstance(value, (int, float)):
                latencies.append(float(value))
    return {
        "successful_calls": len(latencies),
        "latency_seconds": {
            "average": sum(latencies) / len(latencies) if latencies else None,
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "failed_request_attempts": None,
        "absorbed_timeouts": None,
    }


def _validate_upstream_integrity(
    raw: Mapping[str, Any], manifest: Mapping[str, Any]
) -> dict[str, Any]:
    """Upstream results.info에 실제로 보존된 실행 설정을 대조한다."""
    info = raw.get("info") or {}
    agent = info.get("agent_info") or {}
    user = info.get("user_info") or {}
    args = agent.get("llm_args") or {}
    integrity = manifest.get("harness_integrity") or {}
    expected = {
        # 하드코딩하지 않는다 — 매니페스트가 기록한 모드에서 파생시킨다.
        # (2026-08-19: solo 로 고정돼 있어 standard 모드 런의 채점이 통째로 막혔다.
        #  런은 정상 완주했는데 채점기가 거부했다.)
        "agent_implementation": integrity.get("agent_implementation", "llm_agent_solo"),
        "user_implementation": integrity.get("user_implementation", "dummy_user"),
        "agent_model": integrity.get("model_sent_to_litellm"),
        "request_timeout": integrity.get("request_timeout"),
        "litellm_num_retries": 0,
        "max_tokens": integrity.get("max_tokens"),
    }
    observed = {
        "agent_implementation": agent.get("implementation"),
        "user_implementation": user.get("implementation"),
        "agent_model": agent.get("llm"),
        "request_timeout": args.get("timeout"),
        "litellm_num_retries": args.get("num_retries"),
        "max_tokens": args.get("max_tokens"),
    }
    if observed != expected:
        raise ValueError(
            f"upstream results.info integrity mismatch: expected={expected}, observed={observed}"
        )
    if "temperature" in args:
        raise ValueError("upstream results show that temperature was sent")
    return {
        **observed,
        "temperature_sent": False,
        "source": "tau2 results.info.agent_info/user_info",
    }


def score_domain(
    domain: str,
    raw: Optional[Mapping[str, Any]],
    runnable_tasks: int,
    unavailable_reason: Optional[str] = None,
) -> dict[str, Any]:
    if runnable_tasks == 0:
        return {
            "status": "not_measured",
            "reason": unavailable_reason or "zero runnable tasks",
            "pass_rate": None,
            "runnable_tasks": 0,
            "result_records": 0,
            "measured": 0,
            "passed": 0,
            "failed": 0,
            "task_results": [],
        }
    if raw is None:
        raise ValueError(f"missing upstream results for runnable domain {domain}")

    tasks = {str(task["id"]): task for task in raw.get("tasks") or []}
    task_results: list[dict[str, Any]] = []
    passed = failed = measured = 0
    not_measured = Counter()
    simulations = list(raw.get("simulations") or [])
    for simulation in simulations:
        task_id = str(simulation.get("task_id"))
        basis = _task_basis(tasks.get(task_id) or {})
        status, reason = classify_reward_basis(basis)
        reward_info = simulation.get("reward_info") or {}
        reward = reward_info.get("reward")
        record: dict[str, Any] = {
            "task_id": task_id,
            "reward_basis": basis,
            "evaluation_status": status,
            "upstream_reward": reward,
            "termination_reason": simulation.get("termination_reason"),
        }
        if status != "measured":
            record["not_measured_reason"] = reason
            not_measured[str(reason)] += 1
        elif not isinstance(reward, (int, float)):
            record["evaluation_status"] = "not_measured"
            record["not_measured_reason"] = "upstream_reward_missing"
            not_measured["upstream_reward_missing"] += 1
        else:
            # upstream reward만 사용하며 environment state를 재계산하지 않는다.
            did_pass = float(reward) == 1.0
            record["passed"] = did_pass
            measured += 1
            if did_pass:
                passed += 1
            else:
                failed += 1
        task_results.append(record)

    terminations = Counter(str(sim.get("termination_reason")) for sim in simulations)
    model_attr, env_attr = _classify_incompletions(simulations)

    # pass_rate_strict: 모델 귀책 미완주를 실패로 세는 분모. 서빙 의사결정용이다
    # ("이 모델을 붙이면 몇 %가 실제로 끝나는가"). upstream 의 pass_rate 를 덮어쓰지
    # 않는다 — 두 숫자는 서로 다른 질문에 답한다.
    #
    # 환경 귀책 오류가 하나라도 있으면 계산하지 않는다. 그 런은 모델과 무관한 이유로
    # 커버리지가 깨진 것이라 strict 분모가 의미를 갖지 않는다.
    strict_denominator = measured + sum(model_attr.values())
    if sum(env_attr.values()):
        pass_rate_strict = None
        strict_reason = (
            "환경 귀책 오류가 있어 계산하지 않는다: " + str(dict(sorted(env_attr.items())))
        )
    elif strict_denominator:
        pass_rate_strict = passed / strict_denominator
        strict_reason = None
    else:
        pass_rate_strict = None
        strict_reason = "완주한 시뮬레이션이 없다"

    return {
        "status": "measured" if measured else "not_measured",
        "reason": None if measured else "no upstream records had a runnable numeric reward",
        "pass_rate": passed / measured if measured else None,
        "pass_rate_source": "tau2 results.simulations[].reward_info.reward",
        "pass_rate_strict": pass_rate_strict,
        "pass_rate_strict_denominator": strict_denominator,
        "pass_rate_strict_reason": strict_reason,
        "pass_rate_strict_definition": (
            "passed / (measured + 모델 귀책 미완주). upstream pass_rate 와 달리 모델이 "
            "스스로 망가져 못 끝낸 태스크를 실패로 센다. 환경 귀책 오류가 있으면 null."
        ),
        "incompletion_attribution": {
            "model": dict(sorted(model_attr.items())),
            "environment": dict(sorted(env_attr.items())),
        },
        "runnable_tasks": runnable_tasks,
        "result_records": len(simulations),
        "measured": measured,
        "passed": passed,
        "failed": failed,
        "not_measured_result_records": dict(sorted(not_measured.items())),
        "termination_reasons": dict(sorted(terminations.items())),
        "request_observability": _successful_call_observability(simulations),
        "task_results": task_results,
    }


def build_summary(
    raw_by_domain: Mapping[str, Mapping[str, Any]],
    manifest: Mapping[str, Any],
    track: str,
) -> dict[str, Any]:
    if manifest.get("status") != "completed":
        raise ValueError("run manifest is not completed")
    split = dict(manifest.get("split") or {})
    task_ids = list(split.get("task_ids") or [])
    runnable_task_count = split.get("runnable_task_count")
    if runnable_task_count != len(task_ids):
        raise ValueError(
            "split runnable_task_count disagrees with task_ids: "
            f"{runnable_task_count} != {len(task_ids)}"
        )
    not_measured_tasks = list(split.get("not_measured_tasks") or [])
    not_measured_task_count = split.get("not_measured_task_count")
    if not_measured_task_count != len(not_measured_tasks):
        raise ValueError(
            "split not_measured_task_count disagrees with not_measured_tasks: "
            f"{not_measured_task_count} != {len(not_measured_tasks)}"
        )
    if split.get("task_count") != runnable_task_count + not_measured_task_count:
        raise ValueError("split task_count disagrees with runnable/not-measured counts")
    if not split.get("name"):
        raise ValueError("split name is missing")
    telecom_raw = raw_by_domain.get("telecom")
    upstream_task_ids = sorted(
        str(task["id"]) for task in (telecom_raw or {}).get("tasks") or []
    )
    if sorted(str(value) for value in task_ids) != upstream_task_ids:
        raise ValueError(
            "manifest split ids disagree with tasks actually loaded by tau2: "
            f"manifest={len(task_ids)}, upstream={len(upstream_task_ids)}"
        )

    domain_scope = manifest.get("domain_scope") or {}
    domains = {
        "telecom": score_domain(
            "telecom", telecom_raw, int(runnable_task_count or 0)
        ),
        "banking_knowledge": score_domain(
            "banking_knowledge",
            None,
            0,
            (domain_scope.get("banking_knowledge") or {}).get("reason")
            or "banking_knowledge has no supported no-user mode",
        ),
        "retail": score_domain("retail", None, 0, "LLM judge required"),
        "airline": score_domain("airline", None, 0, "LLM judge required"),
    }
    measured = sum(entry["measured"] for entry in domains.values())
    passed = sum(entry["passed"] for entry in domains.values())
    failed = sum(entry["failed"] for entry in domains.values())
    harness_integrity = dict(manifest.get("harness_integrity") or {})
    harness_integrity["upstream_result_evidence"] = _validate_upstream_integrity(
        telecom_raw or {}, manifest
    )
    harness_integrity["manifest_only_not_in_upstream_info"] = [
        "task_timeout",
        "framework_max_retries",
        "max_concurrency",
        "package_versions",
    ]
    return {
        # 모드에 따라 다른 것을 잰다. solo 는 상류가 "Advanced: Ablation Studies" 로
        # 문서화한 사용자 없는 변형이고, standard 는 실제 tau2 프로토콜(3자)이다.
        # 라벨을 고정하면 ablation 결과가 정식 결과로 읽힌다.
        "benchmark": (
            "sierra-research/tau2-bench (state/action, no user simulator — upstream solo ablation)"
            if (manifest.get("harness_integrity") or {}).get("mode", "solo") == "solo"
            else "sierra-research/tau2-bench (state/action, agent-user-tools)"
        ),
        "model": manifest.get("model"),
        "track": track,
        "scoring_version": SCORING_VERSION,
        "score_provenance": "upstream tau2 reward_info.reward; no local reward recomputation",
        "harness_integrity": harness_integrity,
        "split": split,
        "overall": {
            "pass_rate": passed / measured if measured else None,
            "measured": measured,
            "passed": passed,
            "failed": failed,
        },
        "by_domain": domains,
        "not_measured": {
            "selected_split": {
                "count": int(not_measured_task_count or 0),
                "reason": "chosen split tasks whose reward basis is not judge-free",
                "tasks": not_measured_tasks,
            },
            "banking_knowledge": {
                "count": DECLARED_INVENTORY["banking_knowledge"]["total_records"],
                "reason": "judge-free rewards exist, but the domain rejects no-user solo mode",
            },
            "retail": {
                "count": DECLARED_INVENTORY["retail"]["total_records"],
                "reason": "NL_ASSERTION reward basis requires an LLM judge",
            },
            "airline": {
                "count": DECLARED_INVENTORY["airline"]["total_records"],
                "reason": "COMMUNICATE reward basis is outside this no-judge track",
            },
        },
        "source_inventory": DECLARED_INVENTORY,
        "source": dict(manifest.get("source") or {}),
    }


def _load(path: Path) -> dict[str, Any]:
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


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model")
    parser.add_argument("--timestamp")
    parser.add_argument("--track", default="taubench")
    parser.add_argument("--results-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


EXIT_CODE_HELP = """exit codes:
  0  summary produced and publishable
  1  scoring completed but the summary is unusable (nothing measured / incomplete coverage)
  2  invocation, configuration, input-reading, or internal error"""


# tau2 는 완주하지 못한 시뮬레이션을 원인과 무관하게 전부 termination_reason=
# "infrastructure_error" 로 묶는다. 그래서 서버 장애와 "모델이 스스로 망가진 것" 이
# 구분되지 않는다. 구조화된 info.error_type 으로 갈라낸다.
#
# **화이트리스트다.** 여기 없는 유형은 전부 환경 귀책으로 남긴다 — 오분류가 없는
# 모델 결함을 만들어내는 방향으로는 절대 기울지 않게 한다.
#
# 2026-08 실측에서 관측된 error_type 전체와 귀책 판단:
#   ContextWindowExceededError  5x   모델 — 스스로 장황해져 자기 컨텍스트를 넘겼다
#   TypeError                  40x   하네스 — 상류 DummyUser 생성자 불일치
#   BadRequestError            40x   서빙 — system 전용 요청 거부
#   InternalServerError        40x   서버 5xx
#   Timeout                    21x   환경 — 모델이 느린 탓일 수도 있으나 서버 부하와
#                                    구분할 수 없으므로 모델에 귀책시키지 않는다
#   APIError                    9x   환경
MODEL_ATTRIBUTABLE_ERROR_TYPES = frozenset({"ContextWindowExceededError"})


def _classify_incompletions(simulations) -> tuple:
    """완주 실패를 (모델 귀책, 환경 귀책) 으로 가른다."""
    model_attr = Counter()
    env_attr = Counter()
    for sim in simulations:
        if str(sim.get("termination_reason")) != "infrastructure_error":
            continue
        etype = str(((sim.get("info") or {}).get("error_type")) or "unknown")
        if etype in MODEL_ATTRIBUTABLE_ERROR_TYPES:
            model_attr[etype] += 1
        else:
            env_attr[etype] += 1
    return model_attr, env_attr


def validate_summary(summary: dict) -> tuple:
    """발행 가능 여부를 판정한다. (failures, warnings) 를 돌려준다.

    tau2 는 시뮬레이션이 인프라 오류로 죽어도 "Successfully completed all simulations!"
    를 찍고 0 으로 나간다. 2026-08-19 에 telecom test 40/40 이 infrastructure_error 로
    끝났는데도 전체 파이프라인이 성공으로 보였다. 그 구멍을 여기서 막는다.
    """
    failures = []
    warnings = []

    overall = summary.get("overall") or {}
    if overall.get("pass_rate") is None or not overall.get("measured"):
        failures.append(
            "overall.pass_rate 가 없다 — 보상값을 낸 태스크가 하나도 없다"
        )

    for domain, entry in (summary.get("by_domain") or {}).items():
        if not isinstance(entry, dict):
            continue
        runnable = entry.get("runnable_tasks")
        measured = entry.get("measured")
        if not runnable:
            # 실행 범위 밖 도메인이다 (retail/airline 은 판정 모델 필요, banking_knowledge 는
            # solo 모드를 거부한다). 의도적 미측정이지 장애가 아니다 — 게이트 대상이 아니다.
            continue
        if entry.get("status") == "not_measured":
            failures.append(
                f"by_domain.{domain}.status = not_measured "
                f"({entry.get('reason') or '사유 미기록'})"
            )
        elif runnable and measured != runnable:
            failures.append(
                f"by_domain.{domain}: {runnable}건 중 {measured}건만 측정됐다 — 부분 실행이다"
            )

        infra = (entry.get("termination_reasons") or {}).get("infrastructure_error")
        if infra:
            failures.append(
                f"by_domain.{domain}: infrastructure_error {infra}건 — 모델 실패가 아니라 "
                "하네스/서빙 장애다"
            )

    return failures, warnings


def main(argv: Optional[list[str]] = None) -> int:
    try:
        args = parse_args(argv)
        results_dir = _results_dir(args)
        manifest = _load(results_dir / "run_manifest.json")
        raw = {"telecom": _load(results_dir / "upstream" / "telecom" / "results.json")}
        summary = build_summary(raw, manifest, args.track)
        failures, warnings = validate_summary(summary)
        for warning in warnings:
            print(f"[taubench/score] WARN: {warning}", file=sys.stderr)
        for failure in failures:
            print(f"[taubench/score] FAIL: {failure}", file=sys.stderr)

        if args.dry_run:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            # 발행 불가여도 산출물은 남긴다 — 진단에 필요하다. 종료코드로만 막는다.
            _write_atomic(results_dir / "summary.json", summary)
            print(f"[taubench/score] wrote {results_dir / 'summary.json'}")

        if failures:
            print(
                f"[taubench/score] NOT PUBLISHABLE: {len(failures)}건의 검증 실패",
                file=sys.stderr,
            )
            return 1
        return 0
    except Exception as exc:
        print(f"[taubench/score] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
