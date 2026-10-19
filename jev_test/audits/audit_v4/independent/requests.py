"""동결 문구와 원본 state로 봉투를 독립 직렬화한다. jeveval import 없음."""

import hashlib
import json
from string import ascii_uppercase, ascii_lowercase, digits

from .frozen import TABLES, TASK_SHA256


def wire(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def approved(task, name, payload):
    actual = {q["id"]: (q["label"], q["role"], q["type"], q.get("options")) for q in task["questions"]}
    return actual == TABLES[name] and hashlib.sha256(payload).hexdigest() == TASK_SHA256[name]


def questions(task, options):
    return {q["id"]: dict(type=q["type"], instructions=q["instructions"],
                         criteria=options if q["type"] == "choice" else q["criteria"]) for q in task["questions"]}


def envelope(state, questions, cfg, b1, qid=None):
    text = wire(state).decode()
    if cfg["kind"] == "systemone":
        return wire(dict(model=cfg["served_name"], state=text, questions=questions)), None
    q = questions[qid]
    ids = sorted(q["criteria"]) if q["type"] == "choice" else ["true", "false"]
    labels = list(ascii_uppercase + ascii_lowercase + digits)[:len(ids)]
    mapping = dict(zip(labels, ids))
    options = "\n".join(f"{label}. [{option}] {q['criteria'][option]}" for label, option in mapping.items())
    user = b1["user_template"].format(state=text, instructions=q["instructions"], options=options)
    params = dict(b1["params"], top_logprobs=len(ids))
    body = dict(model=cfg["served_name"], messages=[dict(role="system", content=b1["system"]),
                dict(role="user", content=user)], **params,
                allowed_token_ids=[cfg["b1"]["label_token_ids"][label] for label in labels])
    return wire(body), mapping
