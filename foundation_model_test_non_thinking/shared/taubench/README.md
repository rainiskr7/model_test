# tau2-bench no-user track

This track drives the pinned upstream tau2 framework and converts its programmatic
state/action rewards into this repository's `summary.json` contract. It never starts
an LLM judge or an LLM user simulator.

Only canonical telecom text tasks are runnable. `llm_agent_solo` plus `dummy_user`
is supported there. The banking-knowledge environment explicitly rejects solo mode,
so banking knowledge is declared not measured even though most of its reward bases
are programmatic. Retail and airline remain not measured.

The established 4,592 telecom count is an aggregate over task/voice/ablation artifacts;
the pinned canonical `tasks.json` contains 2,285 runnable text tasks. The summary keeps
both facts separate and never presents the aggregate artifact count as unique executions.

The default telecom split is the upstream authors' official `test` split (40 tasks).
Set `TAUBENCH_SPLIT` to any name present in
`data/tau2-bench/data/tau2/domains/telecom/split_tasks.json` (`small`, `train`,
`test`, `base`, or `full`) to select another official split. An unknown name fails
with the available names instead of falling back. The split name, declared task count,
judge-free runnable count, and exact task IDs passed to tau2 are written to the summary.
Any selected task with `NL_ASSERTION` or `COMMUNICATE` is excluded from scoring and
reported explicitly as not measured, with its ID and count.

```bash
./shared/taubench/install.sh
TAUBENCH_SPLIT=test \
  ./shared/taubench/run_taubench.sh MODEL http://HOST:PORT/v1/chat/completions
```

The isolated environment defaults to `.venv-taubench`; the main `.venv` is untouched.
On Python 3.13 the installer adds `audioop-lts`: the voice path is unused, but tau2
imports its voice audio preprocessing module at module scope.
`AGENT_REQUEST_TIMEOUT`, `AGENT_TASK_TIMEOUT`, `AGENT_MAX_TOKENS`, and
`AGENT_TRACK_NAME` follow the other tracks. `AGENT_MAX_RETRIES` must remain `0`.
