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
MODEL="${1:?'MODEL required: ./run_all.sh MODEL [BASE_URL]'}"
BASE_URL="${2:-http://172.16.1.81:18090/v1}"

# 동일 timestamp 공유: EVAL_TIMESTAMP env > .eval_session 파일 > 새로 생성
if [ -z "${EVAL_TIMESTAMP:-}" ]; then
  if [ -f "$SCRIPT_DIR/../../.eval_session" ]; then
    export EVAL_TIMESTAMP="$(cat "$SCRIPT_DIR/../../.eval_session")"
  else
    export EVAL_TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
    echo "$EVAL_TIMESTAMP" > "$SCRIPT_DIR/../../.eval_session"
    echo "[eval_session] 새 세션 생성: $EVAL_TIMESTAMP"
  fi
fi
echo "[run_all] EVAL_TIMESTAMP=$EVAL_TIMESTAMP"
echo "[run_all] MODEL=$MODEL BASE_URL=$BASE_URL"

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

# 가장 가벼운 것부터
echo "=== K-DTCBench (240) ==="
bash "$SCRIPT_DIR/run_k_dtcbench.sh" "$MODEL" "$BASE_URL" || echo "[run_all] K-DTCBench 실패 — 계속"

echo "=== KOFFVQA (275, Rubric judge) ==="
bash "$SCRIPT_DIR/run_koffvqa.sh" "$MODEL" "$BASE_URL" || echo "[run_all] KOFFVQA 실패 — 계속"

echo "=== MTVQA-KR (한국어 서브셋) ==="
bash "$SCRIPT_DIR/run_mtvqa_kr.sh" "$MODEL" "$BASE_URL" || echo "[run_all] MTVQA-KR 실패 — 계속"

echo "=== K-MMBench (4,330) ==="
bash "$SCRIPT_DIR/run_k_mmbench.sh" "$MODEL" "$BASE_URL" || echo "[run_all] K-MMBench 실패 — 계속"

echo "=== KRETA (mode=${KRETA_SETTING:-default}) ==="
# KRETA 프롬프트 모드: KRETA_SETTING env 로 override (기본 default).
#   direct → 글자만 답(빠름, Spark/느린 HW 권장) / default → 추론 후 답.
bash "$SCRIPT_DIR/run_kreta.sh" "$MODEL" "${KRETA_SETTING:-default}" "$BASE_URL" || echo "[run_all] KRETA 실패 — 계속"

# KO-VLM-Benchmark — stub (외부 코드 OpenAI-compat 미지원, 별도 작업 필요)
echo "=== KO-VLM-Benchmark (stub — skip) ==="
bash "$SCRIPT_DIR/run_ko_vlm_benchmark.sh" 2>&1 | head -3 || true

if skip_bench b4_latency_profile; then
  # diffusion 계열: canvas 단위 블록 확정이라 토큰이 버스트로 도착 →
  # TTFT 는 유효하나 ITL/throughput 은 AR 모델과 같은 축에서 비교 불가.
  echo "=== B-4 Latency Profile — SKIP (SKIP_BENCHES) ==="
else
  echo "=== B-4 Latency Profile (50 reps × 4 conditions) ==="
  bash "$SCRIPT_DIR/run_b4_latency_profile.sh" "$MODEL" "$BASE_URL" || echo "[run_all] B-4 실패 — 계속"
fi

echo "=== B-3 Structured Output (data/structured_output/manifest.json 필요) ==="
B3_MANIFEST="$SCRIPT_DIR/data/structured_output/manifest.json"
if [ ! -f "$B3_MANIFEST" ]; then
  echo "[run_all] B-3 manifest 없음 — 스킵 (data/structured_output/ 채우면 활성화)"
else
  # manifest 가 있어도 image 가 모두 존재해야 의미 있는 평가 가능.
  # 누락 시 total=0 인 "성공 exit + 0건 결과" 함정에 빠지므로 preflight 에서 fail-fast.
  B3_PREFLIGHT_OK=$(python - "$B3_MANIFEST" "$SCRIPT_DIR/data/structured_output" <<'PY'
import json, sys
from pathlib import Path
manifest_path = Path(sys.argv[1])
base_dir = Path(sys.argv[2])
items = json.loads(manifest_path.read_text())
missing = []
for it in items:
    img = it.get('image')
    if not img:
        continue
    full = base_dir / img
    if not full.exists():
        missing.append(str(full))
if missing:
    sys.stderr.write("[run_all] B-3 preflight 실패: 이미지 누락\n")
    for m in missing:
        sys.stderr.write(f"  - {m}\n")
    print("NO")
else:
    print("OK")
PY
)
  if [ "$B3_PREFLIGHT_OK" = "OK" ]; then
    bash "$SCRIPT_DIR/run_b3_structured_output.sh" "$MODEL" "$BASE_URL" || echo "[run_all] B-3 실패 — 계속"
  else
    echo "[run_all] B-3 스킵 (preflight 실패 — 이미지 준비 후 재실행)"
  fi
fi

# ============================================================
# 공통 가드: 모든 트랙 종료 후 결과 JSON 의 total/count 검증.
# "성공 exit + 의미 없는 0건 결과" 함정 (B-3 이미지 누락, KRETA stale 등) 사전 탐지.
# ============================================================
echo
echo "=== 결과 sanity check (count==0 탐지) ==="
RESULTS_ROOT="$SCRIPT_DIR/../../results"
SAFE_MODEL="${MODEL//\//_}"
SAFE_MODEL="${SAFE_MODEL//-/_}"
SAFE_MODEL="${SAFE_MODEL//:/_}"
SESSION_DIR="$RESULTS_ROOT/$SAFE_MODEL/$EVAL_TIMESTAMP"
python - "$SESSION_DIR" "$MODEL" "$SCRIPT_DIR/benches" <<'PY' || echo "[run_all] sanity check 에서 strong warning 감지됨"
import json, sys
from pathlib import Path

session = Path(sys.argv[1])
model_name = sys.argv[2]
benches_dir = Path(sys.argv[3])

# schema-aware validation (Pydantic 기반 — _schema.py 가 있으면 활용)
sys.path.insert(0, str(benches_dir))
try:
    from _schema import detect_and_validate
    HAS_SCHEMA = True
except Exception as e:
    print(f"[sanity] schema module 로드 실패 ({e}) — legacy 키 검사만")
    HAS_SCHEMA = False

warnings = []
if not session.exists():
    print(f"[sanity] WARN: session dir 없음 {session}")
    sys.exit(0)

for jf in session.rglob('*.json'):
    if jf.name in ('run_config.json', 'runs.json'):
        continue
    try:
        d = json.loads(jf.read_text())
    except Exception:
        continue
    rel = jf.relative_to(session)

    # 1차: schema 검증 (새 bench 표준)
    if HAS_SCHEMA and isinstance(d, dict):
        kind, msg = detect_and_validate(d, str(rel))
        if msg:
            warnings.append(f"  [{kind}] {msg}")
            continue
        if kind != "unknown":
            continue  # schema 통과 → legacy 검사 skip

    # 2차: legacy fallback (키 기반 — KRETA 같은 비표준 구조 등)
    if isinstance(d, dict):
        for k in ("total", "count", "n_samples", "num_samples"):
            v = d.get(k)
            if isinstance(v, (int, float)) and v == 0:
                warnings.append(f"  {rel}: {k}=0")
                break
        # KRETA results.json 의 모델별 키 구조에서 stale key 탐지
        if jf.parent.name == "kreta" and jf.name == "results.json":
            stale = [k for k in d.keys() if not k.startswith(model_name)]
            if stale:
                warnings.append(f"  {rel}: stale model key {stale}")

if warnings:
    print(f"[sanity] {len(warnings)} 건의 의심 결과:")
    for w in warnings:
        print(w)
    sys.exit(1)
else:
    print("[sanity] OK — 모든 트랙 결과 정상")
PY

echo "[run_all] all benchmarks done"
