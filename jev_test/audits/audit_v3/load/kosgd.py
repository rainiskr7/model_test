"""Read and validate dialogue structure without interpreting act values."""

from common.io import read_json, required_files
from config import KOSGD_DIR, SCHEMA_PATH


def read_dialogues(paths):
    dialogues = {}
    for path in paths:
        rows = read_json(path)
        if not isinstance(rows, list):
            raise ValueError(f"Expected dialogue list: {path}")
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("dialogue_id"), str):
                raise ValueError(f"Invalid dialogue object: {path}")
            key = row["dialogue_id"]
            if not key or key in dialogues:
                raise ValueError(f"Empty/duplicate dialogue_id: {key!r}")
            turns = row.get("turns")
            if not isinstance(turns, list) or not turns:
                raise ValueError(f"Invalid turns: {key}")
            for index, turn in enumerate(turns):
                where = f"{key}#{index}"
                if not isinstance(turn, dict) or turn.get("speaker") not in ("USER", "SYSTEM"):
                    raise ValueError(f"Invalid speaker: {where}")
                if not isinstance(turn.get("utterance"), str):
                    raise ValueError(f"Invalid utterance: {where}")
                if not isinstance(turn.get("frames"), list):
                    raise ValueError(f"Invalid frames: {where}")
                for frame in turn["frames"]:
                    if not isinstance(frame, dict) or not isinstance(frame.get("service"), str):
                        raise ValueError(f"Invalid service: {where}")
                    if not isinstance(frame.get("actions"), list):
                        raise ValueError(f"Invalid actions: {where}")
                    for action in frame["actions"]:
                        if not isinstance(action, dict) or not isinstance(action.get("act"), str):
                            raise ValueError(f"Invalid act: {where}")
                        # R6 deliberately retains malformed INFORM_INTENT values.
                    if turn["speaker"] == "USER":
                        state = frame.get("state")
                        if not isinstance(state, dict) or not isinstance(state.get("active_intent"), str):
                            raise ValueError(f"USER state.active_intent must be a string: {where}")
                    # SYSTEM frames need not have state.
            dialogues[key] = row
    return dialogues


def load():
    paths = required_files(KOSGD_DIR, "dialogues_*.json", expected=34)
    dialogues = read_dialogues(paths)
    schema = read_json(SCHEMA_PATH)
    if not isinstance(schema, list) or len(schema) != 21:
        raise ValueError("KoSGD schema must contain 21 services")
    return dialogues, schema, paths + [SCHEMA_PATH]
