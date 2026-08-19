#!/usr/bin/env python3
"""설치된 tau2 의 DummyUser 생성자를 고친다 (업스트림 버그, 멱등).

tau2-bench @ c339866 (origin/main) 에서 solo 모드가 아예 못 돈다:

  - #175 (tau2 1.0.0) 이 runner/build.py 에 user_kwargs 를 도입해 모든 user 를
    tools/instructions/llm/llm_args(+persona_config) 로 생성한다 (build.py:168-177).
  - #202 가 그 뒤 DummyUser.__init__ 을 무인자로 바꿨다 (user_simulator.py:272).

결과: build_user() 가 DummyUser 를 검증한 직후(build.py:165) 받을 수 없는 kwargs 로
생성해 `DummyUser.__init__() got an unexpected keyword argument 'tools'` 로 전부 죽는다.
telecom test 분할 40/40 이 infrastructure_error 로 끝났다 (2026-08-19 실측).

패치는 **받아서 무시**한다. DummyUser 는 원래 모든 인자를 버리고 llm="dummy" 만 쓰며
generate_next_message 는 NotImplementedError 를 던진다 — 즉 응답을 생성하지 않는 널
사용자다. 인자를 통과시키지 않고 무시하는 쪽이 #202 의 의도를 그대로 보존한다.
채점 의미론에 영향 없음.

clone 은 건드리지 않는다 (install.sh 가 dirty source 설치를 거부하므로 SHA 핀이 유지된다).
"""
import sys, pathlib, re

OLD = "    def __init__(self):\n        super().__init__(llm=\"dummy\")\n"
NEW = "    def __init__(self, **_ignored_upstream_kwargs):\n        super().__init__(llm=\"dummy\")\n"

def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_dummy_user.py <site-packages/tau2/user/user_simulator.py>", file=sys.stderr)
        return 2
    p = pathlib.Path(sys.argv[1])
    if not p.is_file():
        print(f"ERROR: not found: {p}", file=sys.stderr)
        return 1
    src = p.read_text()
    if NEW in src:
        print("[taubench/patch] DummyUser already patched (idempotent no-op)")
        return 0
    # DummyUser 클래스 본문 안의 생성자만 바꾼다 (UserSimulator 것을 건드리면 안 된다).
    i = src.find("class DummyUser(")
    if i == -1:
        print("ERROR: class DummyUser not found — upstream layout changed; re-verify the patch.", file=sys.stderr)
        return 1
    head, tail = src[:i], src[i:]
    if OLD not in tail:
        print("ERROR: expected DummyUser.__init__ body not found — upstream may have fixed it. Re-verify.", file=sys.stderr)
        return 1
    tail = tail.replace(OLD, NEW, 1)
    p.write_text(head + tail)
    print(f"[taubench/patch] DummyUser.__init__ now accepts and ignores upstream kwargs: {p}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
