"""무엇: KoSGD 읽기 · 입력: 원본/선정 경로 · 출력: USER SourceRow/선정 · 계약 §6."""

import json
from pathlib import Path

from jeveval.types import SourceRow


def read_rows(source_cfg: dict, root: Path) -> list[SourceRow]:
    """전체 턴 위치를 유지하고 USER만 읽는다. 발화 원문은 보관하지 않는다."""
    rows, seen = [], set()
    paths = sorted((root / source_cfg["dir"]).glob(source_cfg["dialogues_glob"]))
    if not paths:
        raise ValueError("no KoSGD dialogue files")
    for path in paths:
        for dialogue in json.loads(path.read_text(encoding="utf-8")):
            did = dialogue["dialogue_id"]
            if did in seen:
                raise ValueError(f"duplicate dialogue_id: {did}")
            seen.add(did)
            for index, turn in enumerate(dialogue["turns"]):
                if turn["speaker"] == "USER":
                    fields = dict(dialogue_id=did, turn_index=index, frames=turn["frames"])
                    rows.append(SourceRow("kosgd", f"{did}#{index}", fields))
    return rows


def read_selection(pool_cfg: dict, root: Path) -> list[dict]:
    """감사 JSON에서 지정된 selected_turns만 반환한다."""
    return json.loads((root / pool_cfg["path"]).read_text(encoding="utf-8"))[pool_cfg["field"]]
