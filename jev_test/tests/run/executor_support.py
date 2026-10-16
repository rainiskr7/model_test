"""무엇: 실행기 시험 도우미 · 입력: 합성 env/응답 · 출력: 실제 gate·실행기 연결 · 계약 §5·⑤d R3."""

from dataclasses import replace

from jeveval.run import executor
from jeveval.run.gate import prepare_stage
from jeveval.types import AttemptResult
from tests.run.stage_support import plan_for


def result(code=200, raw='{"answers":{"is_ready":{"type":"noul","noul":0.8}}}', **changes):
    """네트워크·시계 없이 client 한 번의 관측값을 만든다."""
    base = AttemptResult("2026-10-14T00:00:00.000Z", "2026-10-14T00:00:01.000Z",
                         1000, code, None, None, raw)
    return replace(base, **changes)


class Harness:
    """실제 gate와 실행기를 쓰되 전송·잠·길이만 주입한다."""

    def __init__(self, root, env, responses=()):
        """새 dev 단계의 부모와 fingerprint를 실제 gate로 준비한다."""
        prepare_stage(run_dir=root, stage="dev", fingerprint={"run_id": "synthetic"},
                      plan=plan_for(env.plan.logical_id), now="now")
        self.root, self.env = root, env
        self.responses, self.sent, self.waits, self.measured = list(responses), [], [], []

    def measure(self, plan):
        """측정된 호출 순서를 남긴다."""
        self.measured.append(plan.call_id)
        return self.env.length

    def post(self, url, body, timeout, headers=None):
        """시나리오 밖 전송은 즉시 실패한다."""
        self.sent.append((url, body, timeout, headers))
        return self.responses.pop(0)

    def run(self, **changes):
        """동일 프로세스/재개 세션 인자를 명시적으로 덮어쓸 수 있다."""
        args = dict(items=[self.env.item], task=self.env.task,
                    cfg=replace(self.env.cfg, base_url="http://127.0.0.1:1"),
                    b1_config=self.env.b1, measurer=self, run_dir=self.root, stage="dev",
                    post=self.post, sleep=self.waits.append, session_id="session-new", policy=self.env.policy)
        args.update(changes)
        return executor.run_stage(**args)


def pin_fixture_plans(monkeypatch, request_hash):
    """R3 허용: 원본 fixture를 바꾸지 않고 실제 계획의 해시/바이트만 메모리에서 치환한다."""
    original = executor.plan_calls

    def pinned(*args):
        """질문/렌더/ID는 실제 planner가 만들며 저장된 합성 해시에 맞춘다."""
        return [replace(p, request_sha256=request_hash, body=b"fixture request") for p in original(*args)]

    monkeypatch.setattr(executor, "plan_calls", pinned)
