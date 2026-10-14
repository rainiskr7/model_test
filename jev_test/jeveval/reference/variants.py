"""무엇: 참조 자신의 배치 변형 · 입력: T0Reference/요청들 · 출력: 원 응답 · 계약 §8-7 T-d."""

from copy import deepcopy


def clef_batch(runtime, requests):
    ref, model, processor = runtime.module, runtime.model, runtime.processor
    records = [ref.encode_record(processor.tokenizer, body, max_length=runtime.max_length,
                                 processor=processor) for body in requests]
    device = next(model.parameters()).device
    # 참조와 같은 inference_mode·float·softmax 경로를 사용한다.
    with ref.torch.inference_mode():
        logits = model(ref.collate_records(records, processor.tokenizer.pad_token_id, device))
        results = []
        for body, record, values in zip(requests, records, logits, strict=True):
            answers = {q.question_id: ref.systemone_answer(body["questions"][q.question_id],
                dict(zip(q.option_ids, v.float().softmax(-1).tolist(), strict=True)))
                for q, v in zip(record.questions, values, strict=True)}
            results.append(dict(model=body["model"], answers=answers,
                                usage=dict(input_tokens=len(record.input_ids), output_tokens=0)))
    return results


def v1_batch(runtime, requests, batch_size):
    rows, indices = [], []
    for i, body in enumerate(requests):
        for qid, question in body["questions"].items():
            row = dict(state=body["state"], question=question)
            if body.get("images"):
                row["images"] = body["images"]
            rows.append(row)
            indices.append((i, qid, question))
    values = runtime.model.model.predict(rows, batch_size=batch_size)
    results = [dict(model=b["model"], answers={}) for b in requests]
    for (index, qid, question), probabilities in zip(indices, values, strict=True):
        results[index]["answers"][qid] = runtime.answer_module.answer(question, probabilities)
    return results


def batch(runtime, requests, size):
    if runtime.family in ("clef", "clef_flash"):
        return clef_batch(runtime, requests)
    if runtime.family == "pplx_v1":
        return v1_batch(runtime, requests, size)
    raise ValueError("unsupported batch family")


def placed(body, qid, variant, companions):
    """v1.1은 대상 state·question을 보존하고 공개 predict에 질문 위치만 바꾼다."""
    count, position = (1, 0) if variant == "single" else (
        8 if variant.startswith("eight_") else 17, int(variant.rsplit("_", 1)[1]))
    others = [q for b in companions for q in b["questions"].values()]
    if not others:
        others = list(body["questions"].values())
    questions = {}
    for i in range(count):
        key = qid if i == position else f"companion_{i}"
        while key in questions or (i != position and key == qid):
            key += "_x"
        questions[key] = deepcopy(body["questions"][qid] if i == position else others[i % len(others)])
    return dict(deepcopy(body), questions=questions)
