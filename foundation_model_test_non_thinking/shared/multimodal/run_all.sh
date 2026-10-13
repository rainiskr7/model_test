#!/bin/bash
# vsm/multimodal 전체 비전 트랙 일괄 실행 (한 모델, 한 timestamp)
#
# Usage:
#   ./run_all.sh MODEL [BASE_URL]
#
# 결과 위치:
#   results/<safe_model>/<timestamp>/vision/multimodal/{kreta,k_dtcbench,k_mmbench,mtvqa_kr,koffvqa,ko_vlm_benchmark}/
#   results/<safe_model>/<timestamp>/vision/customB/{b3_structured_output,b4_latency_profile}/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# benches/paths.py 가 MODEL_TEST_BASE 를 우선하므로 여기서도 같은 뿌리를 쓴다.
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
MODEL="${1:?'MODEL required: ./run_all.sh MODEL [BASE_URL]'}"
BASE_URL="${2:-http://172.16.1.81:18090/v1}"

# 동일 timestamp 공유: EVAL_TIMESTAMP env > .eval_session 파일 > 새로 생성
if [ -z "${EVAL_TIMESTAMP:-}" ]; then
  # 세션 파일은 결과가 쓰이는 뿌리와 같은 곳에 둔다. 다른 곳에 두면
  # MODEL_TEST_BASE 를 쓸 때 세션 정체성과 results 루트가 갈린다.
  if [ -f "$BASE_DIR/.eval_session" ]; then
    export EVAL_TIMESTAMP="$(cat "$BASE_DIR/.eval_session")"
  else
    export EVAL_TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
    echo "$EVAL_TIMESTAMP" > "$BASE_DIR/.eval_session"
    echo "[eval_session] 새 세션 생성: $EVAL_TIMESTAMP"
  fi
fi
echo "[run_all] EVAL_TIMESTAMP=$EVAL_TIMESTAMP"
echo "[run_all] MODEL=$MODEL BASE_URL=$BASE_URL"

# 각 벤치는 끝까지 실행하되 실패를 잊지 않고 마지막에 nonzero로 반환한다.
FAILURES=0
run_checked() {
  local label="$1"
  shift
  if ! "$@"; then
    echo "[run_all] $label 실패 — 계속"
    FAILURES=$((FAILURES + 1))
  fi
}

# SKIP_BENCHES: 모델 config(또는 serving_profile)가 지정한 제외 벤치 목록.
# 해당 모델에서 숫자가 의미를 갖지 못하는 벤치를 아예 안 돌려, 잘못 비교될
# 결과가 생기지 않게 한다. 미설정 시 아무것도 건너뛰지 않는다(기존 동작).
skip_bench() {
  local name="$1" s
  # set -f: unquoted 확장에서 벤치 이름에 '*' 같은 문자가 섞였을 때 glob 으로
  # 번지는 것을 막는다. word splitting 은 그대로 필요하므로 quote 는 안 한다.
  local had_noglob=1
  case "$-" in *f*) ;; *) had_noglob=0; set -f ;; esac
  for s in ${SKIP_BENCHES:-}; do
    if [ "$s" = "$name" ]; then
      [ "$had_noglob" -eq 0 ] && set +f
      return 0
    fi
  done
  [ "$had_noglob" -eq 0 ] && set +f
  return 1
}
if [ -n "${SKIP_BENCHES:-}" ]; then
  echo "[run_all] SKIP_BENCHES=$SKIP_BENCHES"
fi

# 2026-07-20: KRETA 를 맨 앞으로 옮겼다(원래는 K-MMBench 다음, 5번째).
#   이유 = 직전 런에서 KMMLU 가 chat-template 오염으로 폐기됐고, 같이 재실행하는
#   KRETA(direct) 결과를 조기에 확인하기 위함. 원복하려면 이 블록을 아래
#   K-MMBench 다음 자리로 되돌리면 된다.
# SKIP_BENCHES 에 벤치 이름(kreta k_dtcbench koffvqa mtvqa_kr k_mmbench b4_latency_profile)을 주면 그 벤치를 건너뛴다.
#   끝난 벤치를 덮어쓰지 않고 중단된 세션을 이어갈 때 쓴다. 마지막 sanity check 는 건너뛴 벤치의 기존 결과도 검사한다.
if skip_bench kreta; then
  echo "=== KRETA — SKIP (SKIP_BENCHES) ==="
else
echo "=== KRETA (mode=${KRETA_SETTING:-default}) ==="
# KRETA 프롬프트 모드: KRETA_SETTING env 로 override (기본 default).
#   direct → 글자만 답(빠름, Spark/느린 HW 권장) / default → 추론 후 답.
#   KRETA_RESUME=1 → 같은 세션의 checkpoint 를 이어 쓴다(run_kreta_resume.sh: 오류 행만 재요청).
#   run_kreta.sh 는 시작 시 checkpoint 를 지우므로 중단된 세션을 이어갈 때 반드시 1 을 준다.
#   resume 이 실패하면 1회 더 시도하고, 그래도 실패하면 다른 벤치처럼 실패로 세고 계속한다.
case "${KRETA_RESUME:-0}" in
  0) run_checked "KRETA" bash "$SCRIPT_DIR/run_kreta.sh" "$MODEL" "${KRETA_SETTING:-default}" "$BASE_URL" ;;
  1)
    if ! bash "$SCRIPT_DIR/run_kreta_resume.sh" "$MODEL" "${KRETA_SETTING:-default}" "$BASE_URL"; then
      echo "[run_all] KRETA resume 실패 — 1회 재시도"
      run_checked "KRETA(resume)" bash "$SCRIPT_DIR/run_kreta_resume.sh" "$MODEL" "${KRETA_SETTING:-default}" "$BASE_URL"
    fi
    ;;
  *) echo "[run_all] KRETA_RESUME 은 0 또는 1 이어야 한다: '${KRETA_RESUME}'" >&2; exit 2 ;;
esac
fi

# 이하 가장 가벼운 것부터
if skip_bench k_dtcbench; then
  echo "=== K-DTCBench — SKIP (SKIP_BENCHES) ==="
else
  echo "=== K-DTCBench (240) ==="
  run_checked "K-DTCBench" bash "$SCRIPT_DIR/run_k_dtcbench.sh" "$MODEL" "$BASE_URL"
fi

if skip_bench koffvqa; then
  echo "=== KOFFVQA — SKIP (SKIP_BENCHES) ==="
else
  echo "=== KOFFVQA (275, Rubric judge) ==="
  run_checked "KOFFVQA" bash "$SCRIPT_DIR/run_koffvqa.sh" "$MODEL" "$BASE_URL"
fi

if skip_bench mtvqa_kr; then
  echo "=== MTVQA-KR — SKIP (SKIP_BENCHES) ==="
else
  echo "=== MTVQA-KR (한국어 서브셋) ==="
  run_checked "MTVQA-KR" bash "$SCRIPT_DIR/run_mtvqa_kr.sh" "$MODEL" "$BASE_URL"
fi

if skip_bench k_mmbench; then
  echo "=== K-MMBench — SKIP (SKIP_BENCHES) ==="
else
  echo "=== K-MMBench (4,329) ==="
  run_checked "K-MMBench" bash "$SCRIPT_DIR/run_k_mmbench.sh" "$MODEL" "$BASE_URL"
fi

# KO-VLM-Benchmark — stub (외부 코드 OpenAI-compat 미지원, 별도 작업 필요)
echo "=== KO-VLM-Benchmark (stub — skip) ==="
bash "$SCRIPT_DIR/run_ko_vlm_benchmark.sh" 2>&1 | head -3 || true

if skip_bench b4_latency_profile; then
  # diffusion 계열: canvas 단위 블록 확정이라 토큰이 버스트로 도착 →
  # TTFT 는 유효하나 ITL/throughput 은 AR 모델과 같은 축에서 비교 불가.
  echo "=== B-4 Latency Profile — SKIP (SKIP_BENCHES) ==="
else
  echo "=== B-4 Latency Profile (50 reps × 4 conditions) ==="
  run_checked "B-4" bash "$SCRIPT_DIR/run_b4_latency_profile.sh" "$MODEL" "$BASE_URL"
fi

echo "=== B-3 Structured Output (data/structured_output/manifest.json 필요) ==="
B3_MANIFEST="$SCRIPT_DIR/data/structured_output/manifest.json"
if [ ! -f "$B3_MANIFEST" ]; then
  echo "[run_all] B-3 manifest 없음 — 스킵 (data/structured_output/ 채우면 활성화)"
else
  B3_PREFLIGHT_OK=$(python "$SCRIPT_DIR/benches/b3_preflight.py" "$B3_MANIFEST" "$SCRIPT_DIR/data/structured_output")
  if [ "$B3_PREFLIGHT_OK" = "OK" ]; then
    run_checked "B-3" bash "$SCRIPT_DIR/run_b3_structured_output.sh" "$MODEL" "$BASE_URL"
  else
    echo "[run_all] B-3 스킵 (preflight 실패 — 이미지 준비 후 재실행)"
    FAILURES=$((FAILURES + 1))
  fi
fi

# ============================================================
# 공통 가드: 모든 트랙 종료 후 결과 JSON 의 total/count 검증.
# "성공 exit + 의미 없는 0건 결과" 함정 (B-3 이미지 누락, KRETA stale 등) 사전 탐지.
# ============================================================
echo
echo "=== 결과 sanity check (count==0 탐지) ==="
RESULTS_ROOT="$BASE_DIR/results"
# 경로 해석에 쓸 인터프리터를 먼저 정한다. bare `python` 은 이 저장소의
# 실행 환경(macOS·리눅스 모두)에 없을 수 있고, 없으면 DEST 를 만들기도 전에
# 스크립트가 죽는다.
PY="${PY:-}"
if [ -z "$PY" ]; then
  for candidate in "$BASE_DIR/.venv/bin/python" python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
  done
fi
[ -n "$PY" ] || { echo "[run_all] python 인터프리터를 찾지 못함 — 중단"; exit 1; }

# Linux에서도 기존 git 경로의 실제 casing을 재사용한다. 문자열 치환으로 따로
# 계산하면 macOS(대소문자 무시)에서는 같은 디렉토리를 가리키지만 리눅스에서는
# Python 러너가 쓰는 경로와 갈라져 산출물이 두 디렉토리로 흩어진다.
SAFE_MODEL="$("$PY" -c 'import sys; sys.path.insert(0, sys.argv[1]); from paths import results_model_dir_name; print(results_model_dir_name(sys.argv[2], sys.argv[3]))' "$SCRIPT_DIR/benches" "$BASE_DIR" "$MODEL")" || { echo "[run_all] results 모델 경로 해석 실패 — 중단"; exit 1; }
SESSION_DIR="$RESULTS_ROOT/$SAFE_MODEL/$EVAL_TIMESTAMP"
if ! "$PY" "$SCRIPT_DIR/benches/session_sanity.py" "$SESSION_DIR" "$MODEL" "$SCRIPT_DIR/benches"
then
  echo "[run_all] sanity check 실패 감지됨"
  FAILURES=$((FAILURES + 1))
fi

echo "[run_all] all benchmarks done (failures=$FAILURES)"
if [ "$FAILURES" -ne 0 ]; then
  exit 1
fi
exit 0
