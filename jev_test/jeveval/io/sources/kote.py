"""무엇: KOTE 투표 읽기 · 입력: parquet/raw/투표 규칙 · 출력: SourceRow/라벨 이름 · 계약 §6 보정 7."""

from collections import Counter
import json
from pathlib import Path

import pyarrow.parquet as pq

from jeveval.types import SourceRow


def read_rows(source_cfg: dict, root: Path, votes_cfg: dict, *, set_name="kote_escalation") -> list[SourceRow]:
    """물리 행 ID와 원본 labels를 보존하고 raw 투표의 과반수 라벨을 붙인다."""
    n_raters, min_raters = votes_cfg["n_raters"], votes_cfg["min_raters"]
    if type(min_raters) is not int or not 1 <= min_raters <= n_raters:
        raise ValueError("KOTE min_raters must be an integer in 1..n_raters")
    names = set(read_label_names(source_cfg, root))
    raw = json.loads((root / source_cfg["votes"]).read_text(encoding="utf-8"))
    fields = pq.read_table(root / source_cfg["file"]).to_pylist()
    for row in fields:
        votes = _row_votes(row, raw, names, n_raters)
        row["votes"] = votes
        row["labels_majority"] = sorted(n for n, count in votes.items() if count >= min_raters)
    return [SourceRow(set_name, str(i), row) for i, row in enumerate(fields)]


def _row_votes(row, raw, names, n_raters):
    """ID·문장·평가자 수·감정 이름을 대조한 뒤 평가자당 한 표씩 센다."""
    raw_id = str(row["ID"])
    if raw_id not in raw:
        raise ValueError(f"KOTE raw missing ID: {raw_id}")
    record = raw[raw_id]
    if record["text"] != row["text"]:
        raise ValueError(f"KOTE text mismatch for ID: {raw_id}")
    raters = record["labels"]
    if len(raters) != n_raters:
        raise ValueError(f"KOTE rater count mismatch for ID: {raw_id}")
    counts = Counter()
    for labels in raters.values():
        unique = set(labels)
        if not unique <= names:
            raise ValueError(f"KOTE unknown emotion for ID: {raw_id}")
        counts.update(unique)
    return dict(counts)


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
