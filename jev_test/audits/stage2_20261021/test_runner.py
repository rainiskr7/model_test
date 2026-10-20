"""무엇: 보호 경로 차단 시험 · 입력: pytest 인자 · 출력: 결과/nodeid manifest · 계약 §9 C1."""

import json
import os
from pathlib import Path
import sys


def main():
    """실저장소 데이터 접근을 거부하고 tmp_path 합성 시험만 실행한다."""
    root = Path(__file__).resolve().parents[2]
    blocked = tuple(root / p for p in ("dataset", ".work", "results"))
    def guard(event, args):
        if event in ("socket.connect", "socket.bind", "socket.getaddrinfo"):
            raise PermissionError("network disabled by stage2 tests")
        if event not in ("open", "os.listdir", "os.scandir") or not args:
            return
        if not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        if any(path == p or p in path.parents for p in blocked):
            raise PermissionError("production data access forbidden by stage2 tests")
    sys.addaudithook(guard)
    sys.path.insert(0, str(root))
    import pytest
    class Manifest:
        def pytest_collection_finish(self, session):
            path = os.environ.get("JEV_NODEIDS_OUT")
            if path:
                Path(path).write_text(json.dumps({i.nodeid: [m.name for m in i.iter_markers()
                    if m.name in ("skip", "skipif", "xfail")] for i in session.items}, sort_keys=True))
    return pytest.main(sys.argv[1:], plugins=[Manifest()])


if __name__ == "__main__":
    raise SystemExit(main())
