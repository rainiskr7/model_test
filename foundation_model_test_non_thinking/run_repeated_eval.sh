#!/usr/bin/env bash
# 같은 모델을 같은 규약으로 여러 번 돌린다.
#
# 왜 필요한가: 발행 계층(shared/publish/claims.py)은 반복 3회 이상이라야
# `repeatability_observed` 등급을 주고, 그 아래에서는 모델 간 우열을 발행하지
# 않는다. 1회 런은 `snapshot` 이라 저장·표시·역사 인용만 된다.
#
# 반복이 왜 필요한지는 이 저장소에서 실측됐다 — 같은 모델, 같은 문항인데:
#   functionchat qwen  5런 통과 건수 553 로 동일한데 **통과 항목 10개가 뒤집혔다**
#   functionchat gemma 3런 536/534/537
#   K-DTCBench   gemma4 3런 206/205/205 · diffusiongemma 3런 194/193/194
# 건수만 보면 완벽한 재현으로 읽히는 경우가 있으므로 항목 집합을 대조해야 한다.
#
# Usage:
#   ./run_repeated_eval.sh <model_config> [반복횟수] [-- run_full_eval 추가인자...]
# 예:
#   ./run_repeated_eval.sh google_gemma_4_26B_A4B_it 3

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODEL_CONFIG="${1:?'model config 이름이 필요하다 (configs/models/<name>.yaml)'}"
REPEATS="${2:-3}"
shift 2 2>/dev/null || shift $# 
[ "${1:-}" = "--" ] && shift

if ! [[ "$REPEATS" =~ ^[0-9]+$ ]] || [ "$REPEATS" -lt 1 ]; then
  echo "반복 횟수는 1 이상의 정수여야 한다: $REPEATS" >&2; exit 2
fi
if [ "$REPEATS" -lt 3 ]; then
  echo "[repeat] 경고: 반복 ${REPEATS}회로는 claims 계층이 snapshot 으로 남긴다." >&2
  echo "         모델 간 우열을 발행하려면 3회 이상이 필요하다." >&2
fi

# **오래된 세션 파일을 물려받지 않는다.** 물려받으면 새 런이 옛 세션 디렉토리에
# 섞여 들어가고, 한 디렉토리가 여러 실행에 걸쳐 조립된다. harness 에서 실제로
# 그 결과 한 런 안에 5-shot 과 0-shot 이 섞인 산출물이 만들어졌다.
if [ -f .eval_session ]; then
  echo "[repeat] 기존 .eval_session ($(cat .eval_session)) 을 무시한다 — 반복마다 새 세션을 쓴다."
fi

BASE_TS="$(date +%Y%m%d_%H%M%S)"
FAILED=()
for i in $(seq 1 "$REPEATS"); do
  TS="${BASE_TS}_r${i}"
  RESULT_GLOB="results/*/${TS}"
  if compgen -G "$RESULT_GLOB" > /dev/null; then
    echo "[repeat] $TS 이미 존재 — 이어붙이면 두 실행이 한 디렉토리에 섞인다. 중단." >&2
    exit 1
  fi
  echo "=============================================================="
  echo "[repeat] $i/$REPEATS  EVAL_TIMESTAMP=$TS"
  echo "=============================================================="
  # 하위 스크립트가 .eval_session 을 보지 않도록 명시적으로 넘긴다.
  if EVAL_TIMESTAMP="$TS" bash ./run_full_eval.sh "$MODEL_CONFIG" "$@"; then
    echo "[repeat] $i/$REPEATS 완료"
  else
    rc=$?
    echo "[repeat] $i/$REPEATS 실패 (rc=$rc) — 나머지 반복은 계속한다" >&2
    FAILED+=("$TS(rc=$rc)")
  fi
done

echo
echo "=============================================================="
echo "[repeat] 반복 종료. 실패 ${#FAILED[@]}건 ${FAILED[*]:-}"
echo "[repeat] 아래 보고로 클레임 등급을 확인하라 — 반복이 실제로 한 코호트로"
echo "         묶였는지, 항목이 뒤집혔는지는 보고에만 나온다."
echo "  python3 ../report_nlu_tracks.py"
echo "  python3 ../report_agent_tracks.py"
echo "  python3 ./report_taubench_tracks.py"
echo "  python3 ../report_harness_tracks.py"
echo "=============================================================="
[ ${#FAILED[@]} -eq 0 ] || exit 1
