#!/bin/bash
# kakao/FunctionChat-Bench를 중앙 data/에 고정 commit으로 clone한다.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${MODEL_TEST_BASE:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
DATA_DIR="$BASE_DIR/data"
FUNCTIONCHAT_BENCH_SHA="${FUNCTIONCHAT_BENCH_SHA:-5ddb0b5bb37d6423e1f3381ef693cda811a7847e}"

mkdir -p "$DATA_DIR"
cd "$DATA_DIR"
if [ ! -d "FunctionChat-Bench" ]; then
  git clone https://github.com/kakao/FunctionChat-Bench.git
fi
( cd FunctionChat-Bench && git checkout "$FUNCTIONCHAT_BENCH_SHA" )
echo "[functionchat/install] pin FunctionChat-Bench @ $FUNCTIONCHAT_BENCH_SHA"
echo "[functionchat/install] done (provider SDK requirements are intentionally not installed)"
