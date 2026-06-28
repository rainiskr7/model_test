#!/usr/bin/env bash
# Two-way-capable rsync wrapper for syncing this model_test tree
# between two DGX Spark machines (192.168.0.7 ↔ 192.168.0.8).
#
# Usage:
#   ./sync.sh                # push:  here → other (default)
#   ./sync.sh pull           # pull:  other → here
#   ./sync.sh push --delete  # push and mirror (delete files on remote that don't exist here)
#   ./sync.sh --dry-run      # preview without transferring
#
# Tweak OTHER_HOST below if the remote IP/user changes.

set -euo pipefail

OTHER_HOST="rainis@192.168.0.8"
LOCAL_DIR="/home/rainis/Desktop/workplace/source/model_test/"
REMOTE_DIR="/home/rainis/Desktop/workplace/source/model_test/"

DIR="push"
RSYNC_EXTRA=()
for arg in "$@"; do
    case "$arg" in
        push|pull)    DIR="$arg" ;;
        --delete)     RSYNC_EXTRA+=("--delete") ;;
        --dry-run|-n) RSYNC_EXTRA+=("--dry-run") ;;
        *)            RSYNC_EXTRA+=("$arg") ;;
    esac
done

# What to skip:
#   __pycache__/, *.pyc          — Python 캐시 (자동 재생성)
#   .git/, *.tmp                 — VCS / 임시 파일
#   가상환경                      — .venv/, venv/, env/
#   HuggingFace 캐시              — ~/.cache/huggingface 는 별도 (이 트리 밖)
#
# 데이터셋(data/*)·평가 결과(results/)·외부 clone 저장소는 전부 동기화한다.
EXCLUDES=(
    --exclude '__pycache__/'
    --exclude '*.pyc'
    --exclude '.git/'
    --exclude '*.tmp'
    --exclude '*.swp'
    --exclude '.DS_Store'
    --exclude '.eval_session'

    # Python 가상환경
    --exclude '.venv/'
    --exclude 'venv/'
    --exclude 'env/'
    --exclude '*.egg-info/'
)

if [[ "$DIR" == "push" ]]; then
    SRC="$LOCAL_DIR"
    DST="$OTHER_HOST:$REMOTE_DIR"
    echo "→ Pushing  $SRC  →  $DST"
else
    SRC="$OTHER_HOST:$REMOTE_DIR"
    DST="$LOCAL_DIR"
    echo "← Pulling  $SRC  →  $DST"
fi

# -a: archive (recursive, perms, timestamps, symlinks)
# -h: human-readable sizes
# --info=progress2: single-line progress total
# --partial: keep partial files for resume on disconnect
# --update: skip files that are newer on destination (avoid clobbering recent edits)
rsync -ah --info=progress2 --partial --update \
    "${EXCLUDES[@]}" \
    "${RSYNC_EXTRA[@]}" \
    "$SRC" "$DST"

echo ""
echo "✓ done ($DIR)"
