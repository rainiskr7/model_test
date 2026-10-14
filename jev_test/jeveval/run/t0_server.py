"""무엇: T0 서버 단일 시도 단계 · 입력: 확정 입력/인증 · 출력: 비공개 관측·지연 · 계약 §8-7 T-a/g."""

import os
from pathlib import Path

from jeveval.client import http
from jeveval.client.systemone import send_t0
from jeveval.io.t0_files import write_lines
from jeveval.io.t0_inputs import request_from
from jeveval.run.length import classify
from jeveval.t0.samples import observation
from jeveval.types import LengthInfo


def length_status(row, cfg, status):
    limit = cfg["limit"]["tokens"]
    if status != 200 or row.lengths is None or limit is None:
        return None
    states = [classify(LengthInfo(n, 0, limit, 0)) for n in row.lengths]
    return "ok" if all(s == "not_truncated" for s in states) else "truncated"


def execute(directory, bundle, base_url, *, timeout=600, post=http.post):
    cfg = bundle.metadata["config"]
    value = os.environ.get(cfg["auth_env"]) if cfg["auth_env"] else None
    if not value or any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ValueError("authentication unavailable")
    headers = {"Authorization": "Bearer " + value}
    records = []
    for row in bundle.rows:
        digest, attempt = send_t0(base_url, request_from(row.body), timeout, post=post, headers=headers)
        if digest != row.envelope_sha256:
            raise ValueError("sent T0 envelope mismatch")
        raw = attempt.response_raw
        if not isinstance(raw, str):
            # 비UTF-8도 원시 바이트는 비공개 진단에 보존하고 유효 JSON으로 간주하지 않는다.
            raw = ""
        record = observation(row, bundle.sha256, attempt.http_status, raw,
            error=attempt.transport_error, length_status=length_status(row, cfg, attempt.http_status)).to_dict()
        record.update(latency_ms=attempt.latency_ms, response_bytes=attempt.response_raw if not raw else None)
        records.append(record)
    write_lines(Path(directory) / "server.jsonl", dict(schema="t0_server/1", inputs_sha256=bundle.sha256), records)
    return dict(ok=True, cases=len(records))
