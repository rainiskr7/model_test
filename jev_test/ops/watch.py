"""본시험 레인 감시: 서버 장애가 실패 최종 기록으로 굳기 전에 run 프로세스를 멈춘다.
argv: <attempts.jsonl 경로> <감시할 pid>. 마지막 3 시도가 모두 전송 오류·5xx 면 pid 에 TERM 을 보내고 3 으로 끝난다.
원문(response_raw)은 읽기만 하고 출력하지 않는다.
5초 관찰 보조 장치이며 실패 final 생성 전 중단을 보장하지 않는다."""
import json, os, signal, sys, time

BAD_N = 3


def bad(row):
    s = row.get("http_status")
    return row.get("transport_error") is not None or (isinstance(s, int) and s >= 500)


def size_of(path):
    try:
        return os.path.getsize(path)
    except FileNotFoundError:
        return 0


def tail_rows(path, n, start):
    """감시 시작 뒤에 붙은 줄만 본다 — 이어 돌릴 때 예전 장애 기록으로 다시 멈추지 않게."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(start, size - 400_000))
            lines = f.read().splitlines()[-n - 1:]
    except FileNotFoundError:
        return []
    rows = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return rows[-n:]


def alive(pid):
    try:
        os.kill(pid, 0); return True
    except ProcessLookupError:
        return False


def main(path, pid):
    start = size_of(path)
    while alive(pid):
        rows = tail_rows(path, BAD_N, start)
        if len(rows) == BAD_N and all(bad(r) for r in rows):
            print(f"watch: last {BAD_N} attempts failed "
                  f"{[(r.get('http_status'), r.get('transport_error')) for r in rows]} -> TERM {pid}", flush=True)
            os.kill(pid, signal.SIGTERM)
            return 3
        time.sleep(5)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], int(sys.argv[2])))
