#!/bin/bash
# qwen3.8 27B BF16 — KMMLU 재측정 3회, chat + 생각 모드 끔 (2026-10-11).
# 근거: logs/kmmlu_protocol_diag_20261010/README.md — KMMLU 는 chat_nothink 고정(사용자 결정 10-10).
#   BF16 관문 통과: 6과목 진단 chat_nothink 0.580 vs completions 0.600 (McNemar p=0.34).
#   예전 KMMLU 3회(생각 블록 열린 chat)는 language/harness.thinkopen_20261010 으로 격리했다.
# 운영 harness 그대로: LM_EVAL_MODE=chat(기본), 토크나이저만 생각 끈 사본(템플릿 맨 앞 set enable_thinking=false).
# 서빙(audit_qwen_qwen3.8_27b_20261011_0956): 22c3, vLLM 0.28.0, qwen3 파서, enable_thinking=false, 템플릿 c3cf9e34.
# 감시: lane_guard.sh 의 'qwen38' 레인(패턴 run_qwen38_27b).
set -u
BASE=/Users/rainis/Desktop/workspace/source/model_test/foundation_model_test_non_thinking
cd "$BASE" || exit 1
# shellcheck disable=SC1091
source "$BASE/.venv/bin/activate"
export MODEL_TEST_BASE="$BASE"
export NUM_CONCURRENT=8   # 상한 — 넘기면 DGX Spark 다운
export LM_EVAL_MODE=chat
ORCH="$BASE/logs/resume_orch"
HOST="${QWEN38_HOST:-192.168.0.8:18023}"
TOK=/Users/rainis/Desktop/workplace/models/Qwen_Qwen3.8_27B_nothink
BASE_TS=kmmlu_nothink_20261011
read_key() { grep -E "^$1=" "$BASE/.env" | head -1 | cut -d= -f2- | tr -d '"'"'"' '; }
export OPENAI_API_KEY="$(read_key OPENAI_API_KEY)"
log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$ORCH/orchestrator.log"; }
export BASE_URL_CHAT_OVERRIDE=http://$HOST/v1/chat/completions
export BASE_URL_V1_OVERRIDE=http://$HOST/v1
eval "$(python "$BASE/configs/load_model_config.py" qwen_qwen3.8_27b 2>/dev/null)"
grep -q 'set enable_thinking = false' "$TOK/chat_template.jinja" || { log "qwen BF16 kmmlu: 생각 끈 사본이 아니다 — $TOK"; exit 1; }
body="$(mktemp)"; code="$(curl -s -m 10 -o "$body" -w "%{http_code}" -H "Authorization: Bearer $OPENAI_API_KEY" "$BASE_URL_V1/models")"
if [ "$code" != 200 ] || ! grep -q "\"id\":\"$MODEL\"" "$body"; then log "qwen BF16 kmmlu: preflight 실패 HTTP $code"; rm -f "$body"; exit 1; fi; rm -f "$body"
log "=== qwen3.8 BF16 KMMLU chat_nothink 3회 시작 MODEL=$MODEL host=$HOST tok=$TOK sessions=${BASE_TS}_r1..r3 ==="
for N in 1 2 3; do
  TS="${BASE_TS}_r${N}"
  mkdir -p "$BASE/logs/$TS"
  log "[$TS] harness 시작: run_harness.sh $MODEL $TOK $BASE_URL_CHAT (LM_EVAL_MODE=chat)"
  ( EVAL_TIMESTAMP="$TS" bash vsm/harness/run_harness.sh "$MODEL" "$TOK" "$BASE_URL_CHAT" ) >>"$BASE/logs/$TS/harness_${MODEL}.log" 2>&1   # 10-10: 같은 세션 이름을 쓰는 nemotron 레인과 로그가 섞이지 않게 모델명을 붙인다
  rc=$?
  log "[$TS] harness 종료 rc=$rc"
  [ "$rc" -ne 0 ] && { log "[$TS] harness 실패 — BF16 레인 중단 (원인 확인 후 수동 재개)"; exit "$rc"; }
done
log "=== qwen3.8 BF16 KMMLU 3회 레인 종료 ==="
