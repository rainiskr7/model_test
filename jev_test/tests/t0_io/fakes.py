"""무엇: 세 참조 API의 독립 가짜 · 입력: 합성 요청 · 출력: 고정 비대칭 확률 · 계약 §8-7 시험."""

from contextlib import nullcontext
from types import SimpleNamespace


def probabilities(question):
    if question["type"] == "noul":
        return [.3, .7]
    size = len(question["criteria"])
    return [.7] + [.3 / (size - 1)] * (size - 1)


def answer(question, values):
    kind = question["type"]
    if kind == "noul":
        return dict(type=kind, noul=round(values[1], 4))
    keys = list(question["criteria"]) if kind == "choice" else [str(i) for i in range(len(values))]
    probs = dict(zip(keys, [round(v, 4) for v in values], strict=True))
    result = dict(type=kind, confidence=round(max(values), 4), probabilities=probs)
    if kind == "choice":
        result["choice"] = keys[values.index(max(values))]
    else:
        result.update(score=round(sum(i * v for i, v in enumerate(values)), 4),
                      legend=dict(zip(keys, question["criteria"], strict=True)))
    return result


def response(body):
    return dict(model=body["model"], answers={qid: answer(q, probabilities(q))
                for qid, q in body["questions"].items()})


class Tensor:
    def __init__(self, values):
        self.values = values

    def float(self):
        return self

    def softmax(self, axis):
        assert axis == -1
        return self

    def tolist(self):
        return self.values


class ClefModel:
    def parameters(self):
        return iter([SimpleNamespace(device="cpu", dtype="float32")])

    def __call__(self, records):
        return [[Tensor(probabilities(q.question)) for q in r.questions] for r in records]


def encode_record(tokenizer, body, max_length, processor):
    questions = []
    for qid, q in body["questions"].items():
        keys = ["false", "true"] if q["type"] == "noul" else (
            list(q["criteria"]) if q["type"] == "choice" else [str(i) for i in range(len(q["criteria"]))])
        questions.append(SimpleNamespace(question_id=qid, option_ids=keys, question=q))
    return SimpleNamespace(input_ids=list(body["state"]), questions=questions)


def collate_records(records, pad_token_id, device):
    return records


def systemone_answer(question, probs):
    return answer(question, list(probs.values()))


def systemone(model, processor, body, max_length):
    return dict(response(body), usage=dict(input_tokens=len(body["state"]), output_tokens=0))


def load_release_model(path, device, local_files_only):
    assert local_files_only is True and path.is_dir()
    return ClefModel(), SimpleNamespace(tokenizer=SimpleNamespace(pad_token_id=0))


class DecisionModel:
    dtype = "float32"

    def __init__(self, checkpoint=None, device="cpu"):
        self.calls = []

    def predict(self, rows, batch_size):
        self.calls.append((rows, batch_size))
        return [probabilities(r["question"]) for r in rows]


class Decider:
    def __init__(self):
        self.model = DecisionModel()

    @classmethod
    def from_pretrained(cls, path, device):
        return cls()

    def predict(self, state, question, images=()):
        return answer(question, probabilities(question))


class EvaluationRequest:
    def __init__(self, **body):
        self.body = body


def predict(model, body):
    model.calls.append(body.body)
    return response(body.body)


def module():
    import sys
    value = SimpleNamespace(**vars(sys.modules[__name__]))
    value.torch = SimpleNamespace(inference_mode=nullcontext)
    return value
