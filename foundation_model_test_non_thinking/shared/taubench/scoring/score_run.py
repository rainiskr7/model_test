#!/usr/bin/env python3
"""tau2-bench의 upstream reward records를 ``summary.json``으로 변환한다."""

import argparse
import json
import os
import sys
import tempfile
from collections import Counter

try:  # 패키지로 임포트될 때
    from .passk import pass_hat_k_table
except ImportError:  # 파일 하나만 단독 로드할 때 (테스트 로더)
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(0, str(_Path(__file__).resolve().parent))
    from passk import pass_hat_k_table
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
        # 실측 97 (tasks.json 고유 id 97개). 예전에는 98 로 적혀 있어 자기 구성요소
        # 합(88+9=97)과도 어긋났다.
        "total_records": 97,
        "reward_component_counts": {"DB": 88, "ACTION": 9},
    },
    "retail": {"total_records": 116},
    "airline": {"total_records": 52},
}


def safe_model_name(model: str) -> str:
    return model.replace("/", "_").replace("-", "_").replace(":", "_")


def classify_task(task: Mapping[str, Any]) -> tuple[str, Optional[str]]:
    """태스크가 판정 없이 채점 가능한지 가린다. **선언이 아니라 내용을 본다.**

    러너의 requires_judge() 와 같은 규칙이다. 둘이 어긋나면 러너는 실행하는데
    채점기가 not_measured 로 버리는 사태가 난다 — 2026-08-23 retail 첫 런에서
    실제로 발생했다 (29건을 돌려놓고 0건 측정으로 집계).

    - COMMUNICATE 는 판정이 아니다 (evaluator_communicate.py 는 부분문자열 매칭).
    - NL_ASSERTION 은 선언돼 있어도 nl_assertions 가 비면 판정을 부르지 않는다
      (evaluator_nl_assertions.py:37 이 빈 목록에 대해 1.0 을 돌려준다).
    """
    criteria = task.get("evaluation_criteria") or {}
    values = frozenset(str(v) for v in criteria.get("reward_basis") or [])
    if not values:
        return "not_measured", "reward_basis_missing"
    if "NL_ASSERTION" in values and criteria.get("nl_assertions"):
        return "not_measured", "llm_judge_required"
    unknown = values - PROGRAMMATIC_BASES - JUDGE_BASES
    if unknown:
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
    user_args = user.get("llm_args") or {}
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
    user_observed = _validate_user_protocol(user, user_args, integrity)
    return {
        **observed,
        "temperature_sent": False,
        "user_protocol": user_observed,
        "source": "tau2 results.info.agent_info/user_info",
    }


def _validate_user_protocol(
    user: Mapping[str, Any],
    user_args: Mapping[str, Any],
    integrity: Mapping[str, Any],
) -> dict[str, Any]:
    """사용자 시뮬레이터의 실제 요청 설정을 매니페스트와 대조한다.

    모델 비교가 성립하려면 **후보만 달라야 한다.** 상류 제출 요건도 "모든
    도메인에서 동일한 agent 모델과 사용자 시뮬레이터를 identical arguments 로"
    를 요구한다. 예전 러너는 사용자 인자를 후보 인자에서 복사했기 때문에 후보
    설정이 바뀌면 사용자 프로토콜도 따라 바뀌었다 — 같은 gpt-4.1-mini 인데 한쪽은
    timeout 600s/8192 tokens, 다른 쪽은 120s/16384 tokens 로 돌아간 실측이 있다.
    구버전 산출물은 매니페스트에 사용자 인자가 없으므로 관측값만 남기고 통과시킨다.
    """

    # 모델·타임아웃·토큰만 보면 "고정" 이 아니다. 러너는 사용자에게 temperature 와
    # api_base 도 보낸다 — 엔드포인트가 다르면 같은 alias 라도 다른 백엔드이고,
    # temperature 가 다르면 사용자 발화가 결정론적이지 않다. 둘 다 대조 대상이다.
    observed = {
        "user_model": user.get("llm"),
        "user_request_timeout": user_args.get("timeout"),
        "user_max_tokens": user_args.get("max_tokens"),
        "user_temperature": user_args.get("temperature"),
        "user_api_base": user_args.get("api_base"),
    }
    declared_timeout = integrity.get("user_request_timeout")
    declared_max_tokens = integrity.get("user_max_tokens")
    if declared_timeout is None and declared_max_tokens is None:
        observed["pinned"] = False
        observed["reason"] = (
            "사용자 인자를 기록하지 않는 구버전 러너가 만든 산출물이다. "
            "다른 런과 같은 사용자 프로토콜이었다는 증거가 없다."
        )
        return observed
    # 사용자 **모델**이 비교의 핵심이다. 인자만 대조하고 모델을 빼면, 시뮬레이터가
    # 통째로 바뀌어도 pinned 로 통과한다. 이 트랙은 사용자 시뮬레이터 교체만으로
    # 같은 모델 점수가 0.475 -> 0.900 으로 뛴 전례가 있다.
    expected = {
        "user_model": integrity.get("user_model_sent_to_litellm"),
        "user_request_timeout": declared_timeout,
        "user_max_tokens": declared_max_tokens,
    }
    actual = {
        "user_model": observed["user_model"],
        "user_request_timeout": observed["user_request_timeout"],
        "user_max_tokens": observed["user_max_tokens"],
    }
    # 선언한 적 없는 항목은 대조하지 않되, 관측값은 남겨 코호트가 읽을 수 있게 한다.
    for key in ("user_temperature", "user_api_base"):
        declared = integrity.get(key)
        if declared is not None:
            expected[key] = declared
            actual[key] = observed[key]
    observed["pinned"] = True
    if actual != expected:
        # **예외를 던지지 않는다.** build_summary 안에서 터지면 main 이 exit 2 로
        # 끝나며 summary.json 을 아예 쓰지 않는다. 이 파일의 원칙은 "발행 불가여도
        # 산출물은 남긴다 — 진단에 필요하다" 이고, 후보도 아닌 사용자 시뮬레이터
        # 설정 때문에 진단 근거를 없애는 것은 그 원칙과 어긋난다.
        # 게이트(validate_summary)가 이 필드를 읽어 발행을 막는다.
        observed["mismatch"] = {"declared": expected, "observed": actual}
    return observed


def _trials_per_task(task_results):
    """과제별 시행 수의 분포. 값이 하나면 균일하게 돌린 것이다."""

    counts = Counter(str(record["task_id"]) for record in task_results)
    return sorted(set(counts.values())) if counts else []


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
        task_obj = tasks.get(task_id) or {}
        basis = _task_basis(task_obj)
        status, reason = classify_task(task_obj)
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
    candidate_attr, env_attr, unclassified_attr = _classify_incompletions(simulations)

    # pass_rate_strict: 모델 귀책 미완주를 실패로 세는 분모. 서빙 의사결정용이다
    # ("이 모델을 붙이면 몇 %가 실제로 끝나는가"). upstream 의 pass_rate 를 덮어쓰지
    # 않는다 — 두 숫자는 서로 다른 질문에 답한다.
    #
    # 환경 귀책 오류가 하나라도 있으면 계산하지 않는다. 그 런은 모델과 무관한 이유로
    # 커버리지가 깨진 것이라 strict 분모가 의미를 갖지 않는다.
    strict_denominator = measured + sum(candidate_attr.values())
    blocking = {**dict(env_attr), **dict(unclassified_attr)}
    if blocking:
        pass_rate_strict = None
        strict_reason = (
            "후보 귀책으로 확정되지 않은 미완주가 있어 계산하지 않는다: "
            + str(dict(sorted(blocking.items())))
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
        # 키는 "<error_type>@<actor>" 다. actor 는 traceback 에서 뽑는다.
        "incompletion_attribution": {
            "candidate": dict(sorted(candidate_attr.items())),
            "environment": dict(sorted(env_attr.items())),
            "unclassified": dict(sorted(unclassified_attr.items())),
        },
        "runnable_tasks": runnable_tasks,
        "result_records": len(simulations),
        # 반복 시행이면 시뮬레이션 수와 과제 수가 다르다. 커버리지는 **과제** 단위로
        # 봐야 한다 — 20과제를 4회 돌린 것을 "80과제를 쟀다" 로 세면 게이트가
        # 무의미해진다. Pass^k 도 과제별 성공 횟수에서 나온다.
        "distinct_tasks": len({str(record["task_id"]) for record in task_results}),
        "distinct_tasks_measured": len({
            str(record["task_id"])
            for record in task_results
            if record.get("evaluation_status") == "measured"
        }),
        "trials": _trials_per_task(task_results),
        "pass_hat_k": pass_hat_k_table(task_results),
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
    # 실행 도메인은 매니페스트의 split.domain 이 말해준다 (기본 telecom — 기존 산출물 호환).
    run_domain = str((split or {}).get("domain") or "telecom")
    domain_raw = raw_by_domain.get(run_domain)
    upstream_task_ids = sorted(
        str(task["id"]) for task in (domain_raw or {}).get("tasks") or []
    )
    if sorted(str(value) for value in task_ids) != upstream_task_ids:
        raise ValueError(
            "manifest split ids disagree with tasks actually loaded by tau2: "
            f"manifest={len(task_ids)}, upstream={len(upstream_task_ids)}"
        )

    domain_scope = manifest.get("domain_scope") or {}
    # 실행 도메인을 먼저 넣고, **미실행 도메인만** 사유와 함께 채운다.
    # (예전에는 retail/airline 을 뒤에 무조건 넣어서, retail 을 실행하면 그 결과가
    #  하드코딩된 not_measured 로 덮어써졌다 — 2026-08-23 retail 첫 런에서 29건을
    #  돌려놓고 0건 측정으로 집계됐다.)
    # 실행하지 않은 도메인의 사유는 **"이번 런에서 고르지 않았다"** 뿐이다.
    # 예전에는 판정 필요 여부를 여기에 하드코딩했는데 그게 거짓이 됐다:
    #   airline = "LLM judge required for every task in the test split"
    # 실제 airline test 는 20건이고 전부 판정 불필요다(tbair 런이 20/20 측정).
    # 커밋 4cf6eb7 이 이미 "airline 은 판정이 필요 없다" 로 바로잡았는데 이 문자열만
    # 남아, telecom 을 돌릴 때마다 보고서에 거짓이 출력됐다. 도메인별 판정 필요
    # 여부는 그 도메인을 실제로 고를 때 resolve_task_split 이 내용으로 판정한다.
    # banking 은 매니페스트가 사유를 적었으면 그것을 쓴다 — 모드에 따라 다르다.
    _fallback_reasons = {
        name: (
            (domain_scope.get(name) or {}).get("reason") or "not selected for this run"
        )
        for name in ("banking_knowledge", "retail", "airline", "telecom")
    }
    domains = {
        run_domain: score_domain(
            run_domain, domain_raw, int(runnable_task_count or 0)
        )
    }
    for name, reason in _fallback_reasons.items():
        if name != run_domain:
            domains[name] = score_domain(name, None, 0, reason)

    # 완주와 "도메인을 다 쟀다"는 다르다. runnable 은 우리가 돌리기로 고른 판정
    # 불필요 부분집합이고, split.task_count 가 공식 크기다. 실측: retail test 는
    # 40 중 29 만 판정 없이 채점된다. 부분집합 점수를 도메인 이름으로 발행하면
    # 공식 split 성적으로 오독되므로, 자격을 산출물에 새긴다.
    official = split.get("task_count")
    entry = domains[run_domain]
    if official and runnable_task_count:
        entry["benchmark_eligible"] = int(runnable_task_count) == int(official)
        entry["coverage"] = {
            "measured": entry.get("measured"),
            "runnable_task_count": int(runnable_task_count),
            "official_task_count": int(official),
        }
        if not entry["benchmark_eligible"]:
            entry["coverage"]["reason"] = (
                "판정 불필요 부분집합만 측정했다 — 공식 도메인 점수가 아니다"
            )

    measured = sum(entry["measured"] for entry in domains.values())
    passed = sum(entry["passed"] for entry in domains.values())
    failed = sum(entry["failed"] for entry in domains.values())
    harness_integrity = dict(manifest.get("harness_integrity") or {})
    harness_integrity["upstream_result_evidence"] = _validate_upstream_integrity(
        domain_raw or {}, manifest
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
# 평가 대상(후보 모델)에게 귀책시킬 수 있는 error_type. 화이트리스트다.
CANDIDATE_ATTRIBUTABLE_ERROR_TYPES = frozenset({"ContextWindowExceededError"})

# 원인이 확정된 환경 귀책 유형. 여기에도 없으면 unclassified 로 남긴다 —
# "환경 탓" 이라고 단정하는 것도 근거 없는 주장이기 때문이다.
KNOWN_ENVIRONMENT_ERROR_TYPES = frozenset(
    {
        "Timeout",           # 모델이 느린 탓일 수도 있으나 서버 부하와 구분 불가
        "APIError",
        "InternalServerError",
        "BadRequestError",   # 서빙 제약 (예: system 전용 요청 거부)
        "TypeError",         # 하네스 코드 결함 (상류 DummyUser 생성자 불일치)
    }
)


def _failure_actor(sim: Mapping[str, Any]) -> str:
    """traceback 으로 어느 참가자의 호출에서 터졌는지 가린다.

    error_type 만으로는 알 수 없다. ContextWindowExceededError 는 후보 에이전트에서도,
    사용자 시뮬레이터에서도, 판정 모델에서도 날 수 있다. 오케스트레이터가
    self.agent.generate_next_message / self.user.generate_next_message 중 무엇을
    부르다 터졌는지가 traceback 에 남는다.
    """
    tb = str(((sim.get("info") or {}).get("error_traceback")) or "")
    has_agent = "self.agent.generate_next_message" in tb
    has_user = "self.user.generate_next_message" in tb
    if has_agent and not has_user:
        return "agent"
    if has_user and not has_agent:
        return "user"
    return "unknown"


def _classify_incompletions(simulations) -> tuple:
    """완주 실패를 (후보 귀책, 환경 귀책, 미분류) 로 가른다.

    후보 귀책은 **error_type 과 actor 가 둘 다 맞을 때만** 인정한다. 사용자
    시뮬레이터가 컨텍스트를 넘긴 것은 평가 대상의 결함이 아니라 우리 실험 설정의
    문제이므로 후보에게 씌우면 안 된다.
    """
    candidate = Counter()
    environment = Counter()
    unclassified = Counter()
    for sim in simulations:
        if str(sim.get("termination_reason")) != "infrastructure_error":
            continue
        etype = str(((sim.get("info") or {}).get("error_type")) or "unknown")
        actor = _failure_actor(sim)
        key = f"{etype}@{actor}"
        if etype in CANDIDATE_ATTRIBUTABLE_ERROR_TYPES:
            if actor == "agent":
                candidate[key] += 1
            elif actor == "user":
                # 사용자 시뮬레이터 쪽 초과 — 평가 대상 탓이 아니다.
                environment[key] += 1
            else:
                unclassified[key] += 1
        elif etype in KNOWN_ENVIRONMENT_ERROR_TYPES:
            environment[key] += 1
        else:
            unclassified[key] += 1
    return candidate, environment, unclassified


def validate_summary(summary: dict) -> tuple:
    """발행 가능 여부를 판정한다. (failures, warnings) 를 돌려준다.

    tau2 는 시뮬레이션이 인프라 오류로 죽어도 "Successfully completed all simulations!"
    를 찍고 0 으로 나간다. 2026-08-19 에 telecom test 40/40 이 infrastructure_error 로
    끝났는데도 전체 파이프라인이 성공으로 보였다. 그 구멍을 여기서 막는다.
    """
    failures = []
    warnings = []

    user_protocol = (
        ((summary.get("harness_integrity") or {}).get("upstream_result_evidence") or {})
        .get("user_protocol") or {}
    )
    if user_protocol.get("mismatch"):
        failures.append(
            "사용자 시뮬레이터 프로토콜이 선언과 다르다 — 다른 런과 비교할 수 없다: "
            f"{user_protocol['mismatch']}"
        )
    elif user_protocol and not user_protocol.get("pinned"):
        # 측정 자체는 유효하므로 거부하지 않는다. 다만 이 런은 다른 후보와
        # 나란히 놓을 수 없다 — 같은 사용자 프로토콜이었다는 증거가 없다.
        warnings.append(
            "사용자 시뮬레이터 인자가 기록돼 있지 않다 — 이 런은 모델 간 비교에 쓸 수 없다"
        )

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
        else:
            # 반복 시행이면 measured 는 시뮬레이션 수다. 커버리지는 과제 수로 본다.
            covered = entry.get("distinct_tasks_measured")
            covered = measured if covered is None else covered
            if runnable and covered != runnable:
                failures.append(
                    f"by_domain.{domain}: {runnable}개 과제 중 {covered}개만 측정됐다 — 부분 실행이다"
                )
            # 과제 하나에 측정 기록이 하나라도 있으면 통과시키면 안 된다. 4회 시행에서
            # 과제마다 1건만 살아남아도 "모든 과제를 쟀다"가 되고, Pass^k 는 죽은
            # 시행을 분모에서 빼므로 pass^1=100% 까지 나올 수 있다. 상류 검증기도
            # 과제마다 정확히 num_trials 건을 요구한다
            # (verify_trajectories_public.check_num_trials).
            declared_trials = (summary.get("harness_integrity") or {}).get("trials")
            observed_trials = entry.get("trials") or []
            if declared_trials and observed_trials and set(observed_trials) != {int(declared_trials)}:
                failures.append(
                    f"by_domain.{domain}: 시행 수가 과제마다 다르다 "
                    f"(선언 {declared_trials}, 관측 {observed_trials}) — Pass^k 를 낼 수 없다"
                )

        # 자격은 build_summary 가 이미 새겼다. 게이트는 읽기만 한다 — 검증 함수가
        # 요약을 변형하면 "무엇이 계산이고 무엇이 판정인가" 가 흐려진다.
        coverage = entry.get("coverage") or {}
        if entry.get("benchmark_eligible") is False and coverage.get("official_task_count"):
            warnings.append(
                f"by_domain.{domain}: 공식 split {coverage['official_task_count']}건 중 "
                f"{runnable}건만 대상이다 — 도메인 점수가 아니라 부분집합 점수로만 인용할 것"
            )

        infra = (entry.get("termination_reasons") or {}).get("infrastructure_error")
        if infra:
            # 귀책은 incompletion_attribution 이 말해준다. "전부 하네스 탓" 이라고
            # 단정하지 않는다 — 후보 모델이 스스로 컨텍스트를 넘긴 경우도 여기 섞인다.
            attr = entry.get("incompletion_attribution") or {}
            parts = [
                f"{k}={sum((attr.get(k) or {}).values())}"
                for k in ("candidate", "environment", "unclassified")
                if attr.get(k)
            ]
            detail = ", ".join(parts) if parts else "귀책 미기록"
            failures.append(
                f"by_domain.{domain}: 완주 실패 {infra}건 ({detail}) — 완전 측정이 아니다"
            )

    return failures, warnings


def main(argv: Optional[list[str]] = None) -> int:
    try:
        args = parse_args(argv)
        results_dir = _results_dir(args)
        manifest = _load(results_dir / "run_manifest.json")
        # 매니페스트가 실행 도메인을 안다. upstream/<domain>/results.json 을 읽는다.
        run_domain = str(
            ((manifest.get("split") or {}).get("domain")) or "telecom"
        )
        raw = {
            run_domain: _load(
                results_dir / "upstream" / run_domain / "results.json"
            )
        }
        summary = build_summary(raw, manifest, args.track)
        failures, warnings = validate_summary(summary)
        for warning in warnings:
            print(f"[taubench/score] WARN: {warning}", file=sys.stderr)
        for failure in failures:
            print(f"[taubench/score] FAIL: {failure}", file=sys.stderr)

        # **거부 상태를 산출물 자체에 새긴다.** 예전에는 종료코드로만 알렸는데 그 코드는
        # 호출이 끝나면 사라진다. 2026-08-23 에 게이트가 거부한 gemma telecom
        # 0.4615(18/39)가 요약 파일만 보고 최종 수치로 여러 번 인용됐다.
        summary["publish_status"] = {
            "publishable": not failures,
            "failures": list(failures),
            "warnings": list(warnings),
            "gate_scoring_version": SCORING_VERSION,
        }
        if args.dry_run:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            # 발행 불가여도 산출물은 남긴다 — 진단에 필요하다.
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
