"""무엇: KoSGD 읽기 · 입력: 원본/선정 경로 · 출력: USER SourceRow/선정 · 계약 §6."""

import json
from pathlib import Path

from jeveval.types import SourceRow


def read_rows(source_cfg: dict, root: Path, *, set_name="kosgd") -> list[SourceRow]:
    """USER 위치·frames와 대상까지의 대화, 대화의 서비스 목록을 보존한다."""
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
                    fields["dialogue"] = [{k: t[k] for k in ("speaker", "utterance")}
                                          for t in dialogue["turns"][:index + 1]]
                    fields["services"] = list(dialogue["services"])
                    rows.append(SourceRow(set_name, f"{did}#{index}", fields))
    return rows


def read_selection(pool_cfg: dict, root: Path) -> list[dict]:
    """감사 JSON에서 지정된 selected_turns만 반환한다."""
    return json.loads((root / pool_cfg["path"]).read_text(encoding="utf-8"))[pool_cfg["field"]]


def read_exclusions(pool_cfg, root):
    """선정 제외 목록은 대화 ID로 읽는다. 다른 턴도 같은 제외 단위다."""
    from jeveval.io.paths import inside
    from jeveval.data.exclusions import dialogue_ids
    excluded = set()
    for rule in pool_cfg.get("exclude", []):
        if set(rule) != {"path", "field", "by"} or rule["by"] not in {"dialogue_id", "state_ref"}:
            raise ValueError("invalid selection exclusion rule")
        data = json.loads(inside(root, rule["path"]).read_text(encoding="utf-8"))
        if rule["by"] == "state_ref" and (rule["field"] != "cases" or data.get("schema") != "t0_fixture/1"):
            raise ValueError("T0 exclusion requires fixture cases")
        excluded.update(dialogue_ids(data[rule["field"]], rule["by"]))
    return excluded


def read_prefixes(source_cfg, root, selected):
    """파일에 라벨이 있어도 speaker/utterance만 투영한다. 정답 reader는 호출하지 않는다."""
    from jeveval.types.kosgd_requests import DialoguePrefix
    wanted = {r["dialogue_id"]: r["turn_index"] for r in selected}
    if len(wanted) != len(selected):
        raise ValueError("duplicate pilot dialogue")
    found, seen = {}, set()
    paths = sorted((Path(root) / source_cfg["dir"]).glob(source_cfg["dialogues_glob"]))
    for path in paths:
        for d in json.loads(path.read_text(encoding="utf-8")):
            did = d["dialogue_id"]
            if did in seen:
                raise ValueError("duplicate source dialogue")
            seen.add(did)
            if did not in wanted:
                continue
            index = wanted[did]
            if type(index) is not int or not 0 <= index < len(d["turns"]):
                raise ValueError("invalid pilot turn")
            turns = tuple((t["speaker"], t["utterance"]) for t in d["turns"][:index + 1])
            if turns[-1][0] != "USER" or any(type(s) is not str or type(u) is not str for s, u in turns):
                raise ValueError("invalid pilot prefix")
            found[did] = DialoguePrefix(did, index, turns)
    if set(found) != set(wanted):
        raise ValueError("pilot source incomplete")
    return [found[r["dialogue_id"]] for r in selected]
