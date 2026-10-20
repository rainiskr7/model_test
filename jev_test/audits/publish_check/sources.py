"""무엇: 기존 reader 출력의 텍스트 투영. 입력: 전체 SourceRow. 출력: 중복 제거 필드·원문 manifest."""

from dataclasses import dataclass
from hashlib import sha256
import json
from unicodedata import normalize


SETS = ("kosgd", "fc_call_decision", "kmhas", "kote_escalation", "korfin_asc", "klue_mrc_answerable")
NORMALIZATION = "NFC; remove str.isspace(); Unicode codepoints"


def normalized(text):
    return "".join(c for c in normalize("NFC", text) if not c.isspace())


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def fields(name, row):
    value, identity = row.fields, row.row_id
    if name == "kosgd":
        for index, turn in enumerate(value["dialogue"]):
            yield f'{value["dialogue_id"]}#{index}', "utterance", turn["utterance"]
    elif name == "fc_call_decision":
        for index, message in enumerate(value["input_messages"]):
            for part, text in enumerate(strings(message["content"])):
                yield identity, f"message:{index}:{part}", text
        for index, text in enumerate(strings(value["input_tools"])):
            yield identity, f"tool:{index}", text
    elif name in ("kmhas", "kote_escalation"):
        yield identity, "text", value["text"]
    elif name == "korfin_asc":
        for key in ("SRC", "ASPECT"):
            yield identity, key, value[key]
    elif name == "klue_mrc_answerable":
        for key in ("context", "question"):
            yield identity, key, value[key]
        answers = value["answers"]
        for index, text in enumerate(strings(answers["text"] if isinstance(answers, dict) else answers)):
            yield identity, f"answer:{index}", text
    else:
        raise ValueError("unsupported source set")


@dataclass
class Document:
    text: str
    origins: list[tuple[str, str]]


def project(name, rows, length):
    docs, indices, seen_origins = [], {}, {}
    count = 0
    digest = sha256()
    for row in rows:
        count += 1
        for identity, field, text in fields(name, row):
            if not isinstance(text, str):
                raise ValueError("nontext source field")
            text = normalized(text)
            origin = (str(identity), field)
            if origin in seen_origins:
                if docs[seen_origins[origin]].text != text:
                    raise ValueError("source identity has conflicting text")
                continue
            digest.update(json.dumps([*origin, text], ensure_ascii=False).encode() + b"\n")
            if text not in indices:
                indices[text] = len(docs)
                docs.append(Document(text, []))
            seen_origins[origin] = indices[text]
            docs[indices[text]].origins.append(origin)
    if count == 0:
        raise ValueError("empty source rows")
    return docs, dict(rows=count, unique_fields=len(docs),
                      windows=sum(max(0, len(d.text) - length + 1) for d in docs),
                      projected_sha256=digest.hexdigest())


def source_sets(root, length):
    # Lazy imports keep synthetic extraction tests independent of real dataset access.
    from jeveval.io.set_config import entry
    from jeveval.io.sources import read_set_rows

    for name in SETS:
        selected = entry(root, name)
        rows = read_set_rows(name, selected.split_rules, root, selected=selected)
        docs, manifest = project(name, rows, length)
        del rows
        yield name, docs, manifest
        del docs, manifest, selected
