"""무엇: 순차 실행·resume 상태기계 · 입력: 항목·주입 전송/길이/잠 · 출력: RunSummary · 계약 §4–5·§8-6."""

from collections import Counter, defaultdict

from jeveval.client.attempt import to_attempt_record
from jeveval.client.systemone import systemone_url
from jeveval.io import records
from jeveval.types import B1Config, Item, ModelConfig, RetryPolicy, RunSummary, TaskSpec
from .outcome import call_record, final_record
from .plan_calls import plan_calls
from .policy import decide
from .resume_check import check_resume
from .stage_inputs import attempts_path, final_path


def _plans(items, task, cfg, b1_config):
    """항목 순서를 유지하되 중복 항목/빈 호출 계획은 쓰기 전에 거부한다."""
    grouped, seen = [], set()
    for item in items:
        logical_id = f"{item.set}:{item.group_id}:{item.item_id}"
        if logical_id in seen:
            raise ValueError("duplicate item logical_id")
        seen.add(logical_id)
        plans = plan_calls(item, task, cfg, b1_config)
        if not plans or any(p.logical_id != logical_id for p in plans):
            raise ValueError("invalid item call plans")
        grouped.append((logical_id, plans))
    return grouped


def _execute_call(plan, history, *, cfg, measurer, post, sleep, session_id,
                  headers, timeout, policy, path):
    """시도를 fsync한 뒤에만 대기/다음 호출로 진행하며 기록 예산을 누적한다."""
    if plan.local_errors:
        return call_record(plan, [], None, cfg, policy.max_attempts), 0, 0
    length = measurer.measure(plan)
    recovered = bool(history and (history[-1].terminal or len(history) == policy.max_attempts))
    sent = 0
    url = systemone_url(cfg.base_url) if plan.kind == "systemone" else cfg.base_url + "/v1/chat/completions"
    if not recovered:
        for number in range(len(history) + 1, policy.max_attempts + 1):
            result = post(url, plan.body, timeout, headers=headers)
            sent += 1
            decision = decide(result, number, policy)
            attempt = to_attempt_record(result, call_id=plan.call_id, logical_id=plan.logical_id,
                attempt=number, session_id=session_id, terminal=decision.terminal,
                request_sha256=plan.request_sha256)
            records.append_record(path, attempt)
            history.append(attempt)
            if decision.terminal:
                break
            sleep(decision.wait_s)
    return call_record(plan, history, length, cfg, policy.max_attempts), sent, int(recovered)


def run_stage(*, items: list[Item], task: TaskSpec, cfg: ModelConfig,
              b1_config: B1Config | None, measurer, run_dir, stage, post, sleep,
              session_id: str, policy: RetryPolicy, headers: dict | None = None,
              timeout: float = 600) -> RunSummary:
    """prepare_stage 통과가 전제다. 재시도 예산·대기는 policy(configs/policy.yaml). 반환은 RunSummary만."""
    final_file, attempt_file = final_path(run_dir, stage), attempts_path(run_dir, stage)
    if cfg.base_url is None:
        raise ValueError("base_url is required")
    finals, _ = records.read_finals(final_file)
    attempts, _ = records.read_attempts(attempt_file)
    grouped = _plans(items, task, cfg, b1_config)
    errors = check_resume([p for _, plans in grouped for p in plans], attempts, finals, policy.max_attempts)
    if errors:
        raise ValueError("; ".join(errors))
    records.ensure_file(attempt_file)
    records.ensure_file(final_file)
    completed, history = {f.logical_id for f in finals}, defaultdict(list)
    for attempt in attempts:
        history[attempt.call_id].append(attempt)
    skipped = n_calls = n_sent = n_recovered = 0
    statuses = Counter()
    for logical_id, plans in grouped:
        if logical_id in completed:
            skipped += 1
            continue
        calls = []
        for plan in plans:
            call, sent, recovered = _execute_call(plan, history[plan.call_id], cfg=cfg,
                measurer=measurer, post=post, sleep=sleep, session_id=session_id,
                headers=headers, timeout=timeout, policy=policy, path=attempt_file)
            calls.append(call)
            n_calls += 1
            n_sent += sent
            n_recovered += recovered
        final = final_record(logical_id, plans, calls)
        records.append_record(final_file, final)
        statuses[final.status] += 1
    return RunSummary(len(items), skipped, n_calls, n_sent, n_recovered, dict(statuses))
