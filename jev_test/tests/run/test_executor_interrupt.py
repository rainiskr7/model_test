"""무엇: 중단 위치별 resume · 입력: append 경계 장애 · 출력: 재전송/누락/예산 검증 · 계약 §8-6 N·⑤d R5."""

from dataclasses import replace

import pytest

from jeveval.io import records
from jeveval.types import AttemptRecord
from tests.run.executor_support import Harness, result


def test_terminal_fsync_before_final_recovers_identical_calls(tmp_path, env, monkeypatch):
    """terminal fsync 뒤 중단은 전송 0회로 중단 없는 final을 복구한다."""
    baseline = Harness(tmp_path / "baseline", env, [result()])
    baseline.run()
    expected = records.read_finals(baseline.root / "dev/final.jsonl")[0][0]
    h = Harness(tmp_path / "crashed", env, [result()])
    append = records.append_record

    def crash(path, row):
        """terminal 시도를 실제 fsync한 직후 프로세스 중단을 흉내 낸다."""
        append(path, row)
        if isinstance(row, AttemptRecord) and row.terminal:
            raise RuntimeError("after fsync")

    with monkeypatch.context() as patch:
        patch.setattr(records, "append_record", crash)
        with pytest.raises(RuntimeError, match="after fsync"):
            h.run()
    assert (h.root / "dev/final.jsonl").read_bytes() == b""
    summary = h.run(session_id="resumed")
    final = records.read_finals(h.root / "dev/final.jsonl")[0][0]
    assert summary.n_sent == 0 and summary.n_recovered == 1 and len(h.sent) == 1
    assert final == expected


def test_send_before_append_limit_reuses_unrecorded_number(tmp_path, env, monkeypatch):
    """기록 예산 한계: k+1 전송 뒤 append 전 중단은 같은 k+1을 한 번 더 보낸다."""
    h = Harness(tmp_path, env, [result(503), result(), result()])
    append = records.append_record

    def crash(path, row):
        """1번은 남기고 성공한 2번 전송을 기록하기 직전에 죽는다."""
        if isinstance(row, AttemptRecord) and row.attempt == 2:
            raise RuntimeError("before append")
        append(path, row)

    with monkeypatch.context() as patch:
        patch.setattr(records, "append_record", crash)
        with pytest.raises(RuntimeError, match="before append"):
            h.run()
    summary = h.run(session_id="resumed")
    rows = records.read_attempts(tmp_path / "dev/attempts.jsonl")[0]
    final = records.read_finals(tmp_path / "dev/final.jsonl")[0][0]
    assert [a.attempt for a in rows] == [1, 2]
    assert [a.session_id for a in rows] == ["session-new", "resumed"]
    assert len(h.sent) == 3 and summary.n_sent == 1 and h.waits == [1]
    assert final.status == "ok" and final.calls[0].attempts == 2


def test_b1_partial_terminal_resume_sends_only_remaining_calls(tmp_path, env, monkeypatch, b1_raw):
    """질문 사이 중단은 앞 terminal을 복구하고 남은 질문만 계획 순서로 보낸다."""
    raw = b1_raw([{"token": "A", "logprob": -1}, {"token": "B", "logprob": -2}])
    h = Harness(tmp_path, env, [result(raw=raw)] * 3)
    item = replace(env.item, questions=[replace(env.q, id=q) for q in ("a", "b", "c")])
    cfg = replace(env.bcfg, base_url="http://127.0.0.1:1")
    append = records.append_record

    def crash(path, row):
        """첫 질문 기록 뒤 중단한다."""
        append(path, row)
        if isinstance(row, AttemptRecord):
            raise RuntimeError("between calls")

    with monkeypatch.context() as patch:
        patch.setattr(records, "append_record", crash)
        with pytest.raises(RuntimeError):
            h.run(items=[item], cfg=cfg)
    summary = h.run(items=[item], cfg=cfg, session_id="resumed")
    assert summary.n_sent == 2 and summary.n_recovered == 1
    assert len(h.sent) == 3 and summary.by_status == {"ok": 1}
    assert len(records.read_finals(tmp_path / "dev/final.jsonl")[0]) == 1
