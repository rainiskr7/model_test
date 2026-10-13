"""Question constructors and request serialization."""

import json


def noul(instructions):
    return {"type": "noul", "instructions": instructions}


def choice(instructions, criteria):
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def serialize(state, questions):
    # Byte-for-byte behavior of length_audit/common/request.py.
    return json.dumps({"state": state, "questions": questions}, ensure_ascii=False)
