#!/bin/bash
# tau2-bench를 고정 commit으로 확인하고 전용 venv에만 설치한다.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
DATA_DIR="$BASE_DIR/data"
TAU2_DIR="$DATA_DIR/tau2-bench"
TAU2_BENCH_SHA="${TAU2_BENCH_SHA:-c3398666e6559e3a063da3fc04b5acf7f941464e}"
TAU2_VENV="${TAU2_VENV:-$BASE_DIR/.venv-taubench}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "$DATA_DIR"
if [ ! -d "$TAU2_DIR/.git" ]; then
  git clone https://github.com/sierra-research/tau2-bench.git "$TAU2_DIR"
  git -C "$TAU2_DIR" checkout "$TAU2_BENCH_SHA"
fi

ACTUAL_SHA="$(git -C "$TAU2_DIR" rev-parse HEAD)"
if [ "$ACTUAL_SHA" != "$TAU2_BENCH_SHA" ]; then
  echo "ERROR: tau2-bench commit mismatch: expected $TAU2_BENCH_SHA, got $ACTUAL_SHA" >&2
  echo "The installer will not modify an existing clone." >&2
  exit 1
fi
if [ -n "$(git -C "$TAU2_DIR" status --short)" ]; then
  echo "ERROR: tau2-bench clone has local changes; refusing to install from a dirty source." >&2
  exit 1
fi

"$PYTHON_BIN" -m venv "$TAU2_VENV"
"$TAU2_VENV/bin/python" -m pip install --upgrade pip
# voice 경로는 쓰지 않지만 tau2가 module scope에서 import하므로 Python 3.13 shim이 필요하다.
"$TAU2_VENV/bin/python" -m pip install audioop-lts
"$TAU2_VENV/bin/python" -m pip install "$TAU2_DIR"

# 업스트림 버그: build.py 가 DummyUser 를 받을 수 없는 kwargs 로 생성해 solo 모드가 전부 죽는다.
# clone 은 건드리지 않고(SHA 핀 유지) 설치본만 고친다. 자세한 근거는 patch_dummy_user.py 참조.
SITE_PACKAGES="$("$TAU2_VENV/bin/python" -c 'import tau2,pathlib;print(pathlib.Path(tau2.__file__).parent)')"
"$TAU2_VENV/bin/python" "$SCRIPT_DIR/patch_dummy_user.py" "$SITE_PACKAGES/user/user_simulator.py"

echo "[taubench/install] pin tau2-bench @ $TAU2_BENCH_SHA"
echo "[taubench/install] isolated venv: $TAU2_VENV"
echo "[taubench/install] done"
