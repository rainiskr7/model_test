# R8 serving smoke

Run from any cwd with Bash 3.2 or later:

```bash
N=/Users/rainis/Desktop/workspace/source/model_test/foundation_model_test_non_thinking
bash "$N/orchestration/smoke/run_smoke.sh" qwen35fp8 --out /tmp/qwen35fp8-smoke.json
```

Optional positional tracks are `harness nlu functionchat taubench multimodal`.
The model conf uses the same `orchestration.laneconf` parser/resolver as the lane.
It is read literally from `orchestration/models` using the kmmlu scope and the
explicit root/orchestration/tracks directory; only the session requirement is
skipped for smoke. HOST_ENV wins over HOST_DEFAULT when nonempty.
Duplicate keys, even identical values or unselected scopes, are errors. Replace
an existing assignment instead of appending an override. Whitespace and CR are
preserved; only column-zero comments and matching outer quotes are recognized.
Context records the resolved CONFIG and KEYVAR as well as endpoint and tokenizer.
CONFIG is resolved by the existing config loader (including native
tool calling and serving constraints). The selected KEYVAR is read from N/.env;
its value is supplied only through the child environment / HTTP header.

Every run retains a fresh `/tmp/serving-smoke-*` BASE. Detailed records are
`B/logs/smoke/$T/<track>.json`, runner output is beside them, and artifacts are
under B/results. stdout and optional `--out` contain a JSON summary including B.
The output path must be outside N; its parent must already exist. Remove B when
finished reviewing it. No production lane, lock, or evaluation session is opened.

| Track | Scope | Selected input | Successful runner rc | HTTP upper bound |
| --- | --- | --- | --- | --- |
| harness | preflight | model list, local non-thinking template, 1-token chat | 0 | 2 |
| nlu | full-run | carwash prompt + existing answer contract | 0 + manifest/raw checks | 2 |
| functionchat | full-run | direct module --limit 1, each of three datasets | 0 + three raw checks | 4 |
| taubench | preflight | dependency/commit, model list, 1-token chat | 0 | 2 |
| multimodal | full-run | K-DTCBench --limit 1 | 1 only for sole 240-count shortfall | 4 |

Tracks run sequentially, normal request concurrency 1. Functionchat bypasses the
shell wrapper, performs its own model-list check, and does not run the external
judge. A detected functionchat timeout blocks subsequent tracks as INCONCLUSIVE:
terminating the client cannot prove remote work has stopped. No OpenRouter user
model, KRETA, or koffvqa judge is called. Full-run here means the selected input's
request-to-artifact path, not a complete/publishable benchmark or an accuracy gate.
taubench preflight does not test the tau environment/tool loop.

Data, configs, shared (needed by the functionchat file loader), and .venv* are
read-through symlinks. Results/logs/cache/tmp are real B directories. Bytecode is
disabled. KRETA_OUTPUT_ROOT also points inside B. K-DTCBench caches are copied
with symlinks dereferenced from ~/.cache/huggingface/{datasets,hub}; lock files are
not copied. HF cache paths are all inside B, offline flags are set, and revision
62128c281b7fcbd5af77593a6b65aa385554cb71 is pinned. Missing dependencies/cache give
INCONCLUSIVE; there is no download fallback. The multimodal request bound includes
the current SDK's two retries; a larger SDK default is rejected as INCONCLUSIVE.

Overall exit: any FAIL = 1; otherwise any INCONCLUSIVE = 77; otherwise 0.
Malformed CLI arguments and model-conf ConfigError return 2. Configuration
errors print `smoke: <message>` on stderr; the message body matches the lane
(e.g. `duplicate key: HOST_DEFAULT`). No summary is written for ConfigError.
Missing setup prerequisites return 77. HOST format validation remains smoke-only.

```bash
bash "$N/orchestration/tests/test_smoke_offline.sh"
bash "$N/tests/run_pytests.sh" orchestration -k smoke
```

The shell test uses a stdlib loopback HTTP server with synthetic credentials and
the real runner modules. A forbidden bind returns 77. The pytest alternative
patches only network transports/launch to run the real modules in memory, with
socket connect forbidden. It tests artifacts and corruptions, but is not a claim
that C6.1's HTTP integration passed. Neither test contacts an operational server.
