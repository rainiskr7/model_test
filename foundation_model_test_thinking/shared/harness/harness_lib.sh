#!/bin/bash
# Shared by the runners in this repository; compatible with /bin/bash 3.2.
# No code runs when sourced. Lock fd 9 must be closed in evaluation children.
harness_lock() {
  local lock_path="$1" rc
  if ! { exec 9>"$lock_path"; }; then
    echo '[harness] lock file open failed' >&2
    return 4
  fi
  if command -v flock >/dev/null 2>&1; then
    HARNESS_LOCK_TOOL=flock
    flock -n -E 75 9; rc=$?
  elif [ -x /usr/bin/lockf ]; then
    HARNESS_LOCK_TOOL=lockf
    /usr/bin/lockf -s -t 0 9; rc=$?
  else
    echo '[harness] no supported lock tool' >&2
    return 4
  fi
  case "$rc" in
    0) echo "[harness] lock acquired ($HARNESS_LOCK_TOOL)"; return 0 ;;
    75) echo '[harness] 같은 세션을 다른 실행이 쓰는 중' >&2; return 3 ;;
    *) echo "[harness] lock error ($HARNESS_LOCK_TOOL rc=$rc)" >&2; return 4 ;;
  esac
}

# Collect before signalling: reparenting must not change the KILL target set.
harness_descendants() {
  local child
  case "${1:-}" in ''|*[!0-9]*|0|1) return ;; esac
  printf '%s\n' "$1"
  for child in $(pgrep -P "$1" 2>/dev/null); do
    harness_descendants "$child"
  done
}
harness_alive() {
  local stat
  kill -0 "$1" 2>/dev/null || return 1
  stat=$(ps -o stat= -p "$1" 2>/dev/null)
  case "$stat" in *Z*) return 1 ;; esac
  return 0
}
harness_stop_set() {
  local grace="$1" victims="$2" p live deadline
  case "$grace" in ''|*[!0-9]*) grace=10 ;; esac
  for p in $victims; do kill -TERM "$p" 2>/dev/null || :; done
  deadline=$((SECONDS + grace))
  while [ "$SECONDS" -lt "$deadline" ]; do
    live=0
    for p in $victims; do harness_alive "$p" && live=1; done
    [ "$live" = 0 ] && break
    sleep 0.1
  done
  for p in $victims; do
    harness_alive "$p" && { kill -KILL "$p" 2>/dev/null || :; }
  done
  return 0
}

# Inactive kobest/click/haerae/kbl must acquire real fixtures and expanded C2
# coverage before enabling them. group_subtasks is the membership authority.
harness_validate_structure() {
  python3 -I - "$1" "$2" <<'PY'
import json, math, sys

def fail(reason):
    print(reason)
    raise SystemExit(1)
try:
    with open(sys.argv[1], encoding='utf-8') as f:
        d = json.load(f)
except (ValueError, OSError):
    fail('json_parse')
if not isinstance(d, dict): fail('root_type')
task = sys.argv[2]
results = d.get('results')
if not isinstance(results, dict) or not isinstance(results.get(task), dict):
    fail('missing_task')
metrics = []
for key, value in results[task].items():
    if not isinstance(key, str) or ',' not in key: continue
    name, filt = key.split(',', 1)
    if not name or not filt or name.endswith('_stderr') or name in ('sample_len', 'alias'): continue
    metrics.append(value)
if not metrics: fail('missing_metric')
if any(type(v) not in (int, float) or not math.isfinite(v) for v in metrics):
    fail('nonfinite_metric')
config = d.get('config', {})
if not isinstance(config, dict): fail('config_type')
limit = config.get('limit')
if limit is not None and (type(limit) not in (int, float) or not math.isfinite(limit) or limit <= 0):
    fail('invalid_limit')
samples = d.get('n-samples')
if not isinstance(samples, dict) or not samples: fail('missing_samples')
for counts in samples.values():
    if not isinstance(counts, dict): fail('sample_type')
    original, effective = counts.get('original'), counts.get('effective')
    if type(original) is not int or type(effective) is not int or min(original, effective) <= 0:
        fail('sample_type')
    expected = original if limit is None else min(original, int(limit) if limit >= 1 else math.ceil(original * limit))
    if effective != expected: fail('sample_count')
groups = d.get('group_subtasks') or {}
if not isinstance(groups, dict): fail('group_type')
def leaves(node, visiting=None):
    visiting = set() if visiting is None else visiting
    if node in visiting: fail('group_cycle')
    children = groups.get(node, [])
    if not isinstance(children, list) or any(not isinstance(x, str) for x in children): fail('group_type')
    if not children: return {node}
    found = set()
    for child in children: found |= leaves(child, visiting | {node})
    return found
allowed_leaves = leaves(task)
allowed = {task} | (allowed_leaves & set(samples))
# Accept an enclosing group only if it contains no unrelated leaves.
for group in groups:
    if leaves(group) <= allowed_leaves: allowed.add(group)
if set(results) - allowed: fail('unrelated_task')
if set(samples) - allowed_leaves: fail('unrelated_samples')
print('ok')
PY
}
harness_validate_run_limit() {
  python3 -I - "$1" "${2:-}" <<'PY'
import json, math, sys
try:
    with open(sys.argv[1], encoding='utf-8') as f:
        actual = json.load(f).get('config', {}).get('limit')
    expected = None if sys.argv[2] == '' else float(sys.argv[2])
    if actual is not None and (type(actual) not in (int, float) or not math.isfinite(actual) or actual <= 0):
        raise ValueError()
    if expected is not None and (not math.isfinite(expected) or expected <= 0): raise ValueError()
except (OSError, ValueError, TypeError, AttributeError):
    print('invalid_limit'); sys.exit(1)
if actual != expected:
    print('run_limit_mismatch'); sys.exit(1)
print('ok')
PY
}

harness_preserve_dir() {
  local dir="$1" task="$2" dest suffix=0
  dest="$RESULTS_DIR/.failed_${task}_$(date +%Y%m%d_%H%M%S)_$$"
  while [ -e "$dest.$suffix" ]; do suffix=$((suffix + 1)); done
  mv "$dir" "$dest.$suffix"
}
harness_recover_task() {
  local task="$1" dir empty=0
  for dir in "$RESULTS_DIR/.tmp_${task}" "$RESULTS_DIR/.tmp_${task}."??????; do
    [ -d "$dir" ] || continue
    if compgen -G "$dir/*.json" >/dev/null; then
      harness_preserve_dir "$dir" "$task" || return 1
    elif [ "$dir" = "$RESULTS_DIR/.tmp_${task}" ]; then
      rm -rf "$dir" || return 1
    else
      empty=$((empty + 1))
    fi
  done
  [ "$empty" = 0 ] || echo "[harness] retained foreign tmp without JSON: task=$task count=$empty"
  return 0
}
harness_cleanup_tmp() {
  if [ -n "$HARNESS_TMP_DIR" ] && [ -d "$HARNESS_TMP_DIR" ]; then
    # json 이 없는 임시 폴더(실패한 실행의 빈 폴더)는 보존할 것이 없다 — 지운다.
    if [ "$PRESERVE_TMP" = 1 ] && compgen -G "$HARNESS_TMP_DIR/*.json" >/dev/null; then
      harness_preserve_dir "$HARNESS_TMP_DIR" "$TASK" || :
    else
      rm -rf "$HARNESS_TMP_DIR"
    fi
  fi
  HARNESS_TMP_DIR=""
}
harness_on_signal() {
  [ "$CANCELLING" = 0 ] || return
  CANCELLING=1
  trap '' INT TERM
  local victims=""
  [ -z "$LM_PID" ] || victims=$(harness_descendants "$LM_PID")
  harness_stop_set "${HARNESS_CANCEL_GRACE:-10}" "$victims"
  if [ -n "$LM_PID" ]; then wait "$LM_PID" 2>/dev/null || :; fi
  LM_PID=""
  # Retain any partial JSON for inspection; empty private scratch is disposable.
  if [ -n "$HARNESS_TMP_DIR" ] && compgen -G "$HARNESS_TMP_DIR/*.json" >/dev/null; then PRESERVE_TMP=1; fi
  echo "[harness] 취소됨: task=$TASK sig=$1"
  exit "$1"
}
