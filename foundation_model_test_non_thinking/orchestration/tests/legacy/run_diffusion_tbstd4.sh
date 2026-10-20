#!/bin/bash
# diffusiongemma 26B A4B — taubench standard×4 (2026-10-11). gemma·qwen·nemotron std4 와 같은 조건으로 비교를 맞춘다.
# 서빙(audit_google_diffusiongemma_26B_A4B_it_20261011_1713.json): 22c3, vLLM 0.28.0, 원본 템플릿 9aeb7eac(--chat-template 없음), tool-call-parser gemma4,
#   enable_thinking=false, reasoning parser 없음. 템플릿 A/B(diffusion_nemotron_prep/template_ab/analysis) 사전 규칙 = 원본 유지(10-11).
#   서빙 제약(vllm_diffusion): temperature·seed 등 제거, 출력 상한 4096 — 결정론 없음, 산포 함께 보고.
# 조건: standard, trials 4, telecom 40, 후보 요청 300s(과제 600s), 사용자 openrouter/openai/gpt-4.1-mini 120s/16384,
#   동시 4 (qwen 과 같음 — gemma 는 1 이었다. 결과 비교 때 표시).
# 감시: lane_guard.sh 가 이 레인을 'diffusion' 으로 본다(LANEGUARD_LANES).
set -u
BASE=/Users/rainis/Desktop/workspace/source/model_test/foundation_model_test_non_thinking
cd "$BASE" || exit 1
# shellcheck disable=SC1091
source "$BASE/.venv/bin/activate"
export MODEL_TEST_BASE="$BASE"
export TAUBENCH_MAX_CONCURRENCY=4
ORCH="$BASE/logs/resume_orch"
HOST="${DIFF_HOST:-192.168.0.8:18023}"
TS=tbstd4_20261011
read_key() { grep -E "^$1=" "$BASE/.env" | head -1 | cut -d= -f2- | tr -d '"'"'"' '; }
export OPENAI_API_KEY="$(read_key OPENAI_API_KEY)"
export TAUBENCH_USER_API_KEY="$(read_key TAUBENCH_USER_API_KEY)"
log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$ORCH/orchestrator.log"; }
export BASE_URL_CHAT_OVERRIDE=http://$HOST/v1/chat/completions
export BASE_URL_V1_OVERRIDE=http://$HOST/v1
eval "$(python "$BASE/configs/load_model_config.py" google_diffusiongemma_26B_A4B_it 2>/dev/null)"
body="$(mktemp)"; code="$(curl -s -m 10 -o "$body" -w "%{http_code}" -H "Authorization: Bearer $OPENAI_API_KEY" "$BASE_URL_V1/models")"
if [ "$code" != 200 ] || ! grep -q "\"id\":\"$MODEL\"" "$body"; then log "diffusion tbstd4: preflight 실패 HTTP $code"; rm -f "$body"; exit 1; fi; rm -f "$body"
log "=== diffusiongemma taubench standard×4 시작 MODEL=$MODEL host=$HOST session=$TS ==="
mkdir -p "$BASE/logs/$TS"
log "[$TS] taubench_std4 시작: TAUBENCH_MODE=standard TRIALS=4 동시 4 사용자 gpt-4.1-mini"
( EVAL_TIMESTAMP="$TS" env TAUBENCH_MODE=standard TAUBENCH_USER_MODEL=openrouter/openai/gpt-4.1-mini \
    TAUBENCH_TRIALS=4 AGENT_REQUEST_TIMEOUT=300 TAUBENCH_MAX_CONCURRENCY=4 \
    bash vsm/taubench/run_taubench.sh "$MODEL" "$BASE_URL_CHAT" ) >>"$BASE/logs/$TS/taubench_std4.log" 2>&1
rc=$?
log "[$TS] taubench_std4 종료 rc=$rc"
log "=== diffusiongemma taubench standard×4 레인 종료 ==="
exit $rc
