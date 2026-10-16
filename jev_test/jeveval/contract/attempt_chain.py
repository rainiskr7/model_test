"""무엇: attempts 기록의 구조 불변식 · 입력: 읽은 AttemptRecord 목록 · 출력: 없음/ValueError(줄 번호) · 계약 §5-3·§8-1."""

from jeveval.types import AttemptRecord


def check_attempt_chain(records: list[AttemptRecord]) -> None:
    """호출마다 번호가 1부터 연속이고, terminal 뒤 시도가 없고, logical_id·request_sha256 이 바뀌지 않아야 한다."""
    previous = {}
    for number, record in enumerate(records, 1):
        last = previous.get(record.call_id)
        expected = last.attempt + 1 if last else 1
        if record.attempt != expected:
            raise ValueError(f"line {number}: duplicate or nonconsecutive attempt")
        if last and (last.terminal or last.logical_id != record.logical_id
                     or last.request_sha256 != record.request_sha256):
            raise ValueError(f"line {number}: attempt after terminal or changed call identity")
        previous[record.call_id] = record
