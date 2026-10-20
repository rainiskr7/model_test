"""무엇: 64비트 창 색인·정확 대조·구간 병합. 입력: 정규화 문자열. 출력: 원문 없는 일치 위치."""

from hashlib import sha256

import numpy as np


def window_hash(text):
    return int.from_bytes(sha256(text.encode("utf-8")).digest()[:8], "little")


class WindowIndex:
    def __init__(self, documents, length=12, hash_fn=window_hash):
        if type(length) is not int or length < 1:
            raise ValueError("positive window length required")
        self.documents, self.length, self.hash_fn = documents, length, hash_fn
        if len(documents) >= 2**32 or any(len(d.text) >= 2**32 for d in documents):
            raise ValueError("source index limit")
        count = sum(max(0, len(d.text) - length + 1) for d in documents)
        self.array = np.empty(count, dtype=[("hash", "<u8"), ("doc", "<u4"), ("pos", "<u4")])
        cursor = 0
        for doc, value in enumerate(documents):
            for pos in range(max(0, len(value.text) - length + 1)):
                self.array[cursor] = hash_fn(value.text[pos:pos + length]), doc, pos
                cursor += 1
        self.array.sort(order=["hash", "doc", "pos"])

    def matches(self, text, *, max_candidates=2_000_000):
        """같은 원문·blob 위치 차이를 유지하는 연속 창만 병합한다. 제한 초과는 실패다."""
        length, candidates, intervals = self.length, 0, {}
        hashes = self.array["hash"]
        for start in range(0, max(0, len(text) - length + 1), 32768):
            end = min(start + 32768, len(text) - length + 1)
            query = np.fromiter((self.hash_fn(text[p:p + length]) for p in range(start, end)),
                                dtype=np.uint64, count=end - start)
            lows, highs = np.searchsorted(hashes, query, side="left"), np.searchsorted(hashes, query, side="right")
            for offset, low, high in zip(range(start, end), lows, highs):
                candidates += int(high - low)
                if candidates > max_candidates:
                    raise ValueError("candidate limit")
                for hit in self.array[int(low):int(high)]:
                    doc, source = int(hit["doc"]), int(hit["pos"])
                    if self.documents[doc].text[source:source + length] != text[offset:offset + length]:
                        continue
                    spans = intervals.setdefault((doc, source - offset), [])
                    if spans and offset <= spans[-1][1]:
                        spans[-1][1] = offset + length
                    else:
                        spans.append([offset, offset + length])
        result = []
        for (doc, delta), spans in sorted(intervals.items()):
            for start, end in spans:
                result.append(dict(source_ids=[dict(id=i, field=f) for i, f in self.documents[doc].origins],
                                   source_start=start + delta, blob_start=start, length=end - start))
        return result
