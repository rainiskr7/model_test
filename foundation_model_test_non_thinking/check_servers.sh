#!/usr/bin/env bash
# 평가 서버 점검 — 어떤 모델이 어느 키로 서빙 중인지.
#
# 왜 스크립트로 두는가: 손으로 확인하다 두 번 틀렸다.
#   1) 401 응답 JSON 을 그대로 파싱해 `data` 가 없으니 "모델 0개"로 읽었다.
#      → HTTP 상태를 보지 않으면 인증 실패와 빈 서버를 구분할 수 없다.
#   2) .env 변수명을 `^[A-Za-z_]+` 로 뽑아 `OPENAI_API_KEY_7` 이 `OPENAI_API_KEY_`
#      로 잘렸고, 그 이름으로 다시 찾으니 없어서 "키가 없다"고 결론지었다.
#      → 변수명에는 숫자가 들어간다.
#
# 키 값은 절대 출력하지 않는다.

set -uo pipefail
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$BASE_DIR/.env}"

read_key() {  # $1=변수명
  [ -f "$ENV_FILE" ] || return 1
  grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"'"'"' '
}

probe() {  # $1=호스트  $2=키 변수명
  local host="$1" var="$2" key body code
  key="$(read_key "$var")"
  if [ -z "$key" ]; then
    printf "  %-15s %-20s 키 없음 (%s 가 %s 에 없거나 비어 있다)\n" "$host" "$var" "$var" "$ENV_FILE"
    return 1
  fi
  body="$(mktemp)"
  code=$(curl -s -m 8 -o "$body" -w "%{http_code}" \
    -H "Authorization: Bearer $key" "http://$host/v1/models" 2>/dev/null)
  case "$code" in
    200)
      # 200 일 때만 목록을 신뢰한다.
      python3 -c "
import json, sys
try:
    models = [m.get('id') for m in (json.load(open('$body')).get('data') or [])]
except Exception as exc:
    print(f'  응답을 JSON 으로 읽지 못했다: {type(exc).__name__}'); raise SystemExit(1)
print(f'  {\"$host\":<15} {\"$var\":<20} HTTP 200  모델 {len(models)}개: {models or \"(없음)\"}')"
      ;;
    401|403) printf "  %-15s %-20s HTTP %s  인증 실패 — 이 키는 이 서버 것이 아니다\n" "$host" "$var" "$code" ;;
    000)     printf "  %-15s %-20s 무응답 — 서버가 내려갔거나 포트가 다르다\n" "$host" "$var" ;;
    *)       printf "  %-15s %-20s HTTP %s\n" "$host" "$var" "$code" ;;
  esac
  rm -f "$body"
}

echo "=== 평가 서버 점검 (키 값은 출력하지 않는다) ==="
echo "--- .env 에 정의된 키 (이름과 길이만) ---"
grep -E "^[A-Za-z_][A-Za-z0-9_]*=" "$ENV_FILE" 2>/dev/null | while IFS='=' read -r name rest; do
  v="$(echo "$rest" | tr -d '"'"'"' ')"
  printf "  %-24s 길이 %s\n" "$name" "${#v}"
done
echo "--- 엔드포인트 ---"
probe "192.168.0.7:18023" "OPENAI_API_KEY_7"
probe "192.168.0.8:18023" "OPENAI_API_KEY"
