#!/bin/bash
# Isolated Bash 3.2 fixtures: no real runners, credentials, sockets, or repo results.
# Variable paths are replaced with @BASE@ in the literal dry-run expectation.
# Clock prefixes are checked structurally; argv/env/cwd/session are exact assertions.
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ORCH=$(cd "$HERE/.." && pwd)
REPO=$(cd "$ORCH/.." && pwd)
PYTHON3=$(command -v python3)
ARTIFACTS=$(mktemp -d "${TMPDIR:-/tmp}/lane_full.XXXXXX")
ARTIFACTS=$(cd "$ARTIFACTS" && pwd)
PASS=0 FAIL=0
printf 'ARTIFACTS=%s\n' "$ARTIFACTS"

put_stubs() {
  # All executable evaluation entry points delegate to this recording stub.
  cat > "$FX/bin/record" <<'STUB'
#!/bin/bash
set -u
stage=$1; shift
base=$MODEL_TEST_BASE
out="$base/dump/$EVAL_TIMESTAMP.$stage"
mkdir -p "$out"
printf '%s\n' "$@" > "$out/argv"
pwd > "$out/cwd"
env | LC_ALL=C sort > "$out/env"
printf '%s %s\n' "$EVAL_TIMESTAMP" "$stage" >> "$base/calls"
printf 'STUB_OUT %s\n' "$stage"
printf 'STUB_ERR %s\n' "$stage" >&2
rd=$(cat "$base/model_dir")
if [ ! -f "$base/no_outputs" ]; then
  case "$stage" in
    functionchat) mkdir -p "$base/results/$rd/$EVAL_TIMESTAMP/language/functionchat" ;;
    multimodal)
      p="$base/results/$rd/$EVAL_TIMESTAMP/vision/multimodal/koffvqa"
      mkdir -p "$p"
      touch -t 202001010000 "$p/z_old_gen.xlsx"
      touch -t 202101010000 "$p/a_new_gen.xlsx" ;;
  esac
fi
rcfile="$base/rc/$EVAL_TIMESTAMP.$stage"
if [ -f "$rcfile" ]; then exit "$(cat "$rcfile")"; fi
STUB
  cat > "$FX/bin/python" <<'STUB'
#!/bin/bash
set -u
case "$1" in
  */configs/load_model_config.py)
    printf 'export MODEL=fixture/model\nexport BASE_URL_CHAT=%s\nexport BASE_URL_V1=%s\n' "$BASE_URL_CHAT_OVERRIDE" "$BASE_URL_V1_OVERRIDE"
    exit 0 ;;
  -m)
    case "$2" in
      shared.functionchat.judge.run_judge) stage=functionchat_judge ;;
      shared.multimodal.benches.koffvqa_api_judge) stage=koffvqa_judge ;;
      *) exit 98 ;;
    esac ;;
  derive_multimodal_publish.py) stage=derive ;;
  *) exit 98 ;;
esac
exec "$MODEL_TEST_BASE/bin/record" "$stage" "$@"
STUB
  cat > "$FX/bin/curl" <<'STUB'
#!/bin/bash
set -u
printf 'preflight\n' >> "$MODEL_TEST_BASE/preflight"
while [ "$#" -gt 0 ]; do
  if [ "$1" = -o ]; then printf '{"data":[{"id":"fixture/model"}]}' > "$2"; shift 2
  else shift; fi
done
printf 200
STUB
  chmod +x "$FX/bin/record" "$FX/bin/python" "$FX/bin/curl"
}

fixture() {
  # Every case has a complete temporary orchestration copy and fake base.
  FX="$ARTIFACTS/$1"
  mkdir -p "$FX/bin" "$FX/.venv/bin" "$FX/configs" "$FX/shared" "$FX/rc" "$FX/dump" "$FX/home"
  cp -R "$ORCH" "$FX/orchestration"
  cp "$REPO/shared/results_dir.sh" "$FX/shared/results_dir.sh"
  ln -s "$PYTHON3" "$FX/bin/python3"
  printf 'export PATH="%s/bin:/usr/bin:/bin"\n' "$FX" > "$FX/.venv/bin/activate"
  printf 'fixture_model\n' > "$FX/model_dir"
  printf 'OPENAI_API_KEY_7=synthetic-model-key\nTAUBENCH_USER_API_KEY=synthetic-judge-key\n' > "$FX/.env"
  cp "$ORCH/lanes/qwen35fp8_full.conf" "$FX/orchestration/lanes/full.conf"
  ln -s ../run_lane.sh "$FX/orchestration/lanes/full.sh"
  LANE=full
  put_stubs
  local stage path
  for stage in nlu functionchat taubench multimodal; do
    case "$stage" in multimodal) path=vsm/multimodal/run_all.sh ;; *) path=vsm/$stage/run_$stage.sh ;; esac
    mkdir -p "$FX/$(dirname "$path")"
    printf '#!/bin/bash\nexec "$MODEL_TEST_BASE/bin/record" %s "$@"\n' "$stage" > "$FX/$path"
  done
}

run_lane() {
  # env -i plus only synthetic inherited pollution; cwd is outside the fake repo.
  (cd "$ARTIFACTS" && env -i HOME="$FX/home" PATH="$FX/bin:/usr/bin:/bin" LC_ALL=C \
    PYTHONDONTWRITEBYTECODE=1 MODEL_TEST_BASE="$FX" LANE_DRY_RUN="${1:-0}" \
    AGENT_REQUEST_TIMEOUT=999 AGENT_TASK_TIMEOUT=9999 NUM_CONCURRENT=99 TAUBENCH_MODE=standard TAUBENCH_TRIALS=9 \
    TAUBENCH_MAX_CONCURRENCY=9 KRETA_WORKERS=9 KRETA_RESUME=1 \
    /bin/bash "$FX/orchestration/lanes/$LANE.sh") > "$FX/stdout" 2>&1
  RC=$?
}

has() { grep -F -- "$2" "$1" >/dev/null; }
exact() { grep -Fx -- "$2" "$1" >/dev/null; }
absent() { ! grep -E -- "$2" "$1" >/dev/null; }
expect_rc() { [ "$RC" -eq "$1" ] || { cat "$FX/stdout"; return 1; }; }
set_rc() { printf '%s\n' "$3" > "$FX/rc/20261015_full_r$1.$2"; }
all_calls() {
  local rep stage
  for rep in "$@"; do
    for stage in nlu functionchat taubench multimodal functionchat_judge koffvqa_judge derive; do
      printf '20261015_full_r%s %s\n' "$rep" "$stage"
    done
  done
}

f1() {
  fixture F1
  rm "$FX/.env"
  # A helper invocation would leave evidence even if no model directories exist.
  printf '\nprintf unexpected > "$MODEL_TEST_BASE/helper_called"\n' >> "$FX/shared/results_dir.sh"
  run_lane 1
  expect_rc 0 || return 1
  # 4a: all three functionchat/taubench pairs in dry_run.txt now carry env
  # REQUEST=300 and TASK=900; TASK must exceed REQUEST to pass runner validation.
  sed "s|@BASE@|$FX|g" "$HERE/fixtures_full/dry_run.txt" > "$FX/expected"
  diff -u "$FX/expected" "$FX/stdout" || return 1
  [ ! -e "$FX/helper_called" ] && [ ! -e "$FX/preflight" ] &&
    [ ! -e "$FX/logs" ] && [ ! -e "$FX/results" ] && [ ! -e "$FX/calls" ]
}

f2() {
  fixture F2
  mkdir -p "$FX/results/FiXtUrE_model/20261015_full_r1"
  run_lane
  expect_rc 2 && [ ! -e "$FX/calls" ] &&
    has "$FX/logs/resume_orch/orchestrator.log" '세션 존재 — 재개는 RESUME_FROM'
}

failure_case() {
  # An exact ordered call list proves both continuation and early stopping.
  local name=$1 stage=$2 code=$3 expected_rc=$4 stop=$5
  fixture "$name"
  set_rc 1 "$stage" "$code"
  run_lane
  expect_rc "$expected_rc" || return 1
  if [ "$stop" = yes ]; then
    all_calls 1 | sed "/ $stage\$/q" > "$FX/expected_calls"
  elif [ "$stage" = koffvqa_judge ]; then
    # A failed KOFFVQA judge leaves nothing to derive: derive is skipped for that rep only.
    all_calls 1 2 3 | sed '/^20261015_full_r1 derive$/d' > "$FX/expected_calls"
  else
    all_calls 1 2 3 > "$FX/expected_calls"
  fi
  diff -u "$FX/expected_calls" "$FX/calls" || return 1
  has "$FX/logs/resume_orch/orchestrator.log" "[20261015_full_r1] $stage 종료 rc=$code"
}

f3() {
  failure_case F3_nlu nlu 1 1 yes || return 1
  has "$FX/stdout" 'nlu 실패 — qwen3.5-FP8 레인 중단 (원인 확인 후 수동 재개)' || return 1
  failure_case F3_functionchat functionchat 2 2 yes || return 1
  failure_case F3_multimodal multimodal 1 1 yes || return 1
  failure_case F3_tau taubench 1 0 no || return 1
  has "$FX/stdout" 'taubench 실패 rc=1 — 계속' || return 1
  local stage code
  for stage in functionchat_judge koffvqa_judge derive; do
    failure_case "F3_$stage" "$stage" 1 1 no || return 1
    has "$FX/stdout" '=== qwen3.5 27B FP8 전 트랙 3회 레인 종료 (판정 실패 1건) ===' || return 1
  done
  for stage in nlu functionchat taubench multimodal functionchat_judge koffvqa_judge derive; do
    for code in 3 130; do
      failure_case "F3_${stage}_$code" "$stage" "$code" "$code" yes || return 1
    done
  done
  fixture F3_accumulated
  set_rc 1 functionchat_judge 1; set_rc 2 koffvqa_judge 2; set_rc 3 derive 1
  run_lane
  expect_rc 1 && has "$FX/stdout" '레인 종료 (판정 실패 3건)'
}

f4() {
  fixture F4
  printf 'RESUME_FROM=r2:multimodal\nKRETA_RESUME=1\n' >> "$FX/orchestration/lanes/full.conf"
  mkdir -p "$FX/results/FiXtUrE_model/20261015_full_r2/language/functionchat"
  printf 'FiXtUrE_model\n' > "$FX/model_dir"
  run_lane 1
  expect_rc 0 || return 1
  [ "$(grep -c '^SKIP=' "$FX/stdout")" -eq 10 ] || return 1
  [ "$(grep -c 'KRETA_RESUME=1' "$FX/stdout")" -eq 1 ] || return 1
  run_lane
  expect_rc 0 || return 1
  { all_calls 2 | sed '1,3d'; all_calls 3; } > "$FX/expected_calls"
  diff -u "$FX/expected_calls" "$FX/calls" || return 1
  [ "$(grep -c 'skip (resume)' "$FX/stdout")" -eq 10 ] || return 1
  local dir
  for dir in "$FX/dump/"*; do
    case "$dir" in
      */20261015_full_r2.multimodal) exact "$dir/env" 'KRETA_RESUME=1' || return 1 ;;
      *) absent "$dir/env" '^KRETA_RESUME=' || return 1 ;;
    esac
  done
  exact "$FX/dump/20261015_full_r2.functionchat_judge/argv" "$FX/results/FiXtUrE_model/20261015_full_r2/language/functionchat"
}

check_stage_env() {
  local dir=$1 stage=${1##*.} ts
  ts=$(basename "$dir"); ts=${ts%.*}
  exact "$dir/cwd" "$FX" && exact "$dir/env" "EVAL_TIMESTAMP=$ts" || return 1
  absent "$dir/env" '^(NUM_CONCURRENT|KRETA_RESUME)=' || return 1
  # 4a: replace blanket timeout absence with explicit values only for the two
  # consuming stages; inherited pollution must still be absent everywhere else.
  case "$stage" in
    functionchat|taubench)
      exact "$dir/env" "AGENT_REQUEST_TIMEOUT=${2:-300}" &&
        exact "$dir/env" "AGENT_TASK_TIMEOUT=${3:-900}" || return 1 ;;
    *) absent "$dir/env" '^AGENT_(REQUEST|TASK)_TIMEOUT=' || return 1 ;;
  esac
  if [ "$stage" = taubench ]; then
    exact "$dir/env" TAUBENCH_MODE=solo && exact "$dir/env" TAUBENCH_TRIALS=1 &&
      exact "$dir/env" TAUBENCH_MAX_CONCURRENCY=4 || return 1
  else absent "$dir/env" '^TAUBENCH_(MODE|TRIALS|MAX_CONCURRENCY)=' || return 1; fi
  if [ "$stage" = multimodal ]; then exact "$dir/env" KRETA_WORKERS=4 || return 1
  else absent "$dir/env" '^KRETA_WORKERS=' || return 1; fi
  case "$stage" in
    *_judge|derive) exact "$dir/env" "PYTHONPATH=$FX" || return 1 ;;
    *) absent "$dir/env" '^PYTHONPATH=' || return 1 ;;
  esac
}

check_stage_argv() {
  local ts=$1 stage=$2
  case "$stage" in
    nlu) printf '%s\n' --model fixture/model --endpoint http://192.168.0.7:18023/v1/chat/completions ;;
    functionchat|taubench) printf '%s\n' fixture/model http://192.168.0.7:18023/v1/chat/completions ;;
    multimodal) printf '%s\n' fixture/model http://192.168.0.7:18023/v1 ;;
    functionchat_judge)
      printf '%s\n' -m shared.functionchat.judge.run_judge --results-dir "$FX/results/fixture_model/$ts/language/functionchat" ;;
    koffvqa_judge)
      printf '%s\n' -m shared.multimodal.benches.koffvqa_api_judge --predfile \
        "$FX/results/fixture_model/$ts/vision/multimodal/koffvqa/a_new_gen.xlsx" \
        --target-model fixture/model --judge-model openai/gpt-4.1-mini \
        --judge-base-url https://openrouter.ai/api/v1 --judge-api-key synthetic-judge-key --seed 0 ;;
    derive)
      printf '%s\n' derive_multimodal_publish.py --base . --write --source \
        "$FX/results/fixture_model/$ts/vision/multimodal/koffvqa_api_judge" ;;
  esac > "$FX/expected_argv"
  diff -u "$FX/expected_argv" "$FX/dump/$ts.$stage/argv"
}

f5() {
  fixture F5
  local rep stage dir
  for rep in 1 2 3; do
    mkdir -p "$FX/logs/20261015_full_r$rep"
    for stage in nlu functionchat taubench multimodal functionchat_judge koffvqa_judge derive; do
      printf 'SENTINEL\n' > "$FX/logs/20261015_full_r$rep/$stage.log"
    done
  done
  run_lane
  expect_rc 0 || return 1
  all_calls 1 2 3 > "$FX/expected_calls"
  diff -u "$FX/expected_calls" "$FX/calls" || return 1
  for dir in "$FX/dump/"*; do check_stage_env "$dir" || return 1; done
  while read -r ts stage; do
    check_stage_argv "$ts" "$stage" || return 1
    printf 'SENTINEL\nSTUB_OUT %s\nSTUB_ERR %s\n' "$stage" "$stage" > "$FX/expected_log"
    diff -u "$FX/expected_log" "$FX/logs/$ts/$stage.log" || return 1
    has "$FX/stdout" "[$ts] $stage 시작: " && has "$FX/stdout" "[$ts] $stage 종료 rc=0" || return 1
  done < "$FX/calls"
  absent "$FX/stdout" 'synthetic-judge-key' || return 1
  fixture F5_conditional
  touch "$FX/no_outputs"
  run_lane
  expect_rc 0 || return 1
  all_calls 1 2 3 | sed '/_judge$/d; / derive$/d' > "$FX/expected_calls"
  diff -u "$FX/expected_calls" "$FX/calls" || return 1
  fixture F5_derive_resume
  printf 'RESUME_FROM=r3:derive\n' >> "$FX/orchestration/lanes/full.conf"
  run_lane
  expect_rc 0 && [ ! -e "$FX/calls" ] && has "$FX/stdout" 'derive skip (condition)'
}

f6() {
  local setting count=0
  # 4a: reject invalid full timeout pairs before activation/preflight.
  for setting in UNKNOWN=x KRETA_WORKERS=9 KRETA_WORKERS=0 KRETA_RESUME=2 \
    RESUME_FROM=r0:x RESUME_FROM=r4:nlu RESUME_FROM=r2:unknown RESUME_FROM=r2:nlu:extra \
    AGENT_TASK_TIMEOUT=120 AGENT_TASK_TIMEOUT=300 AGENT_TASK_TIMEOUT=x \
    AGENT_REQUEST_TIMEOUT=900 AGENT_REQUEST_TIMEOUT=0 AGENT_REQUEST_TIMEOUT=x \
    REPS=0 REPS=-1 REPS=x STOP_LABEL=; do
    count=$((count + 1))
    fixture "F6_$count"
    printf '%s\n' "$setting" >> "$FX/orchestration/lanes/full.conf"
    run_lane
    expect_rc 2 && [ ! -e "$FX/calls" ] && [ ! -e "$FX/preflight" ] || return 1
  done
}

f7() {
  # 4a: conf overrides must reach both consuming stages, not just dry-run text.
  fixture F7
  printf 'REPS=1\nAGENT_REQUEST_TIMEOUT=350\nAGENT_TASK_TIMEOUT=1000\n' >> "$FX/orchestration/lanes/full.conf"
  run_lane
  expect_rc 0 || return 1
  local dir
  for dir in "$FX/dump/"*; do check_stage_env "$dir" 350 1000 || return 1; done
}


run_case() {
  if "$2"; then PASS=$((PASS + 1)); printf 'PASS %s\n' "$1"
  else FAIL=$((FAIL + 1)); printf 'FAIL %s (artifacts: %s)\n' "$1" "$FX"; fi
}
run_case F1 f1
run_case F2 f2
run_case F3 f3
run_case F4 f4
run_case F5 f5
run_case F6 f6
run_case F7 f7
printf 'SUMMARY {"pass":%s,"fail":%s,"inconclusive":0}\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
