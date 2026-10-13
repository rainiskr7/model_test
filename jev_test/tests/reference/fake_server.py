"""무엇: v1.1 참조 서버 경계 대역 · 입력: 고정 logit 모델 · 출력: Answer · 계약 ⑥b-2 R1.

실제 autojev 검증이 아니다. predict의 batching/temperature 호출 모양만 재현한다.
"""

from types import SimpleNamespace


class EvaluationRequest:
    def __init__(self, **body):
        self.state, self.images = body["state"], body.get("images", [])
        self.questions = {key: Question(value) for key, value in body["questions"].items()}


class Question:
    def __init__(self, value):
        self.value = value

    def model_dump(self, *, exclude_none):
        assert exclude_none
        return {key: value for key, value in self.value.items() if value is not None}


class FixedModel:
    def __init__(self, logits, temperature):
        self.logits, self.temperature, self.batches = logits, temperature, []

    def prepare(self, rows):
        self.batches.append(rows)
        return SimpleNamespace(counts=[len(self.logits)] * len(rows), input_tokens=len(rows) * 3)

    def __call__(self, batch):
        import torch
        return torch.tensor([self.logits] * len(batch.counts), dtype=torch.float64)


def predict(model, body):
    import torch
    from autojev.model import answer

    questions = {key: q.model_dump(exclude_none=True) for key, q in body.questions.items()}
    identifiers = list(questions)
    rows = [{"state": body.state, "question": q, "images": list(body.images)} for q in questions.values()]
    answers, tokens = {}, 0
    with torch.inference_mode():
        for start in range(0, len(rows), 8):
            batch = model.prepare(rows[start:start + 8])
            distributions = (model(batch) / model.temperature).softmax(-1).cpu().tolist()
            for key, values, count in zip(identifiers[start:start + 8], distributions, batch.counts, strict=True):
                answers[key] = answer(questions[key], values[:count])
            tokens += batch.input_tokens
    return dict(model="reference-service", answers=answers, usage=dict(input_tokens=tokens, output_tokens=0))
