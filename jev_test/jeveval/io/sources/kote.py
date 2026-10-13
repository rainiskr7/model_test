"""무엇: KOTE 읽기 · 입력: parquet 경로 · 출력: SourceRow/라벨 이름 · 계약 §6."""

import json
from pathlib import Path

import pyarrow.parquet as pq

from jeveval.types import SourceRow


def read_rows(source_cfg: dict, root: Path) -> list[SourceRow]:
    """원본 ID 열 대신 물리 행 위치를 쓰며 labels는 Python 목록이다."""
    fields = pq.read_table(root / source_cfg["file"]).to_pylist()
    return [SourceRow("kote_escalation", str(i), row) for i, row in enumerate(fields)]


def read_label_names(source_cfg: dict, root: Path) -> list[str]:
    """Hugging Face의 info.features.labels.feature.names를 읽는다."""
    metadata = pq.read_schema(root / source_cfg["file"]).metadata or {}
    try:
        names = json.loads(metadata[b"huggingface"])["info"]["features"]["labels"]["feature"]["names"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("missing KOTE label names metadata") from exc
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ValueError("invalid KOTE label names")
    if len(set(names)) != len(names):
        raise ValueError("duplicate KOTE label names")
    return names
