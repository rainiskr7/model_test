"""무엇: blob 텍스트와 JSON escape 해제. 입력: bytes·경로 목록. 출력: 정규화 view별 문자열."""

import json

from .sources import normalized, strings


def views(payload, paths):
    text = payload.decode("utf-8")
    if any(ord(c) < 32 and not c.isspace() for c in text):
        raise ValueError("binary text")
    yield "raw", 0, normalized(text)
    suffixes = {p.rsplit(".", 1)[-1].lower() for p in paths if "." in p}
    for suffix in sorted(suffixes & {"json", "jsonl"}):
        values = [json.loads(text)] if suffix == "json" else [json.loads(line) for line in text.splitlines() if line.strip()]
        index = 0
        for value in values:
            for string in strings(value):
                yield suffix, index, normalized(string)
                index += 1
