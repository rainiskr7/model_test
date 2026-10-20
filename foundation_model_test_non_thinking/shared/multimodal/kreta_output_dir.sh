#!/bin/bash
# run_kreta.sh / run_kreta_resume.sh 가 source 하는 공용 헬퍼 — KRETA 답안(checkpoint) 폴더.
#
# 왜 있는가: upstream infer_gpt.py 는 답안을 ./output/<MODEL>_<SETTING>.jsonl 에, evaluate.py 는
# 한 폴더의 jsonl 을 일괄 채점한다. 모든 실행이 한 폴더를 쓰던 시절, 러너의 "stale 정리"가 다른
# 모델의 진행 중 checkpoint 를 지웠다 (2026-08-30: gemma r1·diffusion r1 KRETA 유실).
# 지금은 실행마다 <root>/<safe_model>/<session>/<setting>/ 를 쓰고, 그 폴더에 writer 잠금을 건다.
#
# 규칙:
#   - KRETA_OUTPUT_ROOT 는 루트만 바꾼다. 그 아래 3단계는 항상 붙는다 — 두 레인이 같은 env 를
#     상속해도 한 폴더로 합쳐지지 않는다.
#   - MODEL 에 '/' 나 선행 '.' 이 있으면 정리 단계 **전에** 거부한다. upstream 이 파일명을 MODEL 로
#     만들어 폴더 밖이나 하위 폴더에 쓰게 되고, evaluate.py 는 한 단계만 읽어 그 답안을 못 본다.
#   - 폴더 안 `.writer.lock/` (mkdir 원자성) 에 PID 를 둔다. 살아 있는 PID 가 잡고 있으면 아무것도
#     지우기 전에 중단한다. 죽은 PID 면 stale 로 보고 넘겨받는다.

kreta_reject_bad_model_name() {  # $1=MODEL
  case "$1" in
    "")        echo "[multimodal/kreta] ERROR: MODEL 이 비어 있다"; return 1 ;;
    */*|.*)    echo "[multimodal/kreta] ERROR: MODEL 이름에 '/' 나 선행 '.' 을 쓸 수 없다: '$1' — checkpoint 파일명이 답안 폴더 밖으로 나간다"; return 1 ;;
  esac
  return 0
}

kreta_output_dir() {  # $1=root $2=safe_model $3=session $4=setting → stdout
  printf '%s/%s/%s/%s\n' "$1" "$2" "$3" "$4"
}

kreta_acquire_writer_lock() {  # $1=out_dir — 성공 시 EXIT trap 으로 해제
  local dir="$1" lock="$1/.writer.lock" pid
  mkdir -p "$dir" || return 1
  if ! mkdir "$lock" 2>/dev/null; then
    pid="$(cat "$lock/pid" 2>/dev/null)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "[multimodal/kreta] ERROR: 같은 답안 폴더에 다른 실행(PID $pid)이 쓰고 있다 — 아무것도 지우지 않고 중단: $dir"
      return 1
    fi
    echo "[multimodal/kreta] stale writer lock 제거 (PID '${pid:-?}' 없음): $lock"
    rm -rf "$lock" && mkdir "$lock" || return 1
  fi
  echo "$$" > "$lock/pid" || return 1
  KRETA_WRITER_LOCK="$lock"
  # shellcheck disable=SC2064
  trap 'rm -rf "$KRETA_WRITER_LOCK"' EXIT
  return 0
}

kreta_copy_artifacts() {  # $1=out_dir $2=dest — 파일만 복사 (lock 디렉터리 제외)
  find "$1" -maxdepth 1 -type f -exec cp {} "$2/" \;
}
