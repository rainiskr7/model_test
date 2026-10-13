"""무엇: B1 프롬프트 구성 · 입력: 설정·렌더·질문·호출 ID · 출력: B1Call · 계약 §2-5."""

from copy import deepcopy

from jeveval.types import B1Call, B1Config, BoundQuestion, Rendered


def build_b1_call(config: B1Config, rendered: Rendered, question: BoundQuestion,
                  call_qid: str) -> B1Call:
    """라벨 토큰 ID는 후속 client에서 채우며 문구·매개변수는 설정을 사용한다."""
    if question.type == "score":
        raise NotImplementedError("score is out of scope")
    if question.type == "noul":
        ids, descriptions = ["true", "false"], question.criteria
    elif question.type == "choice":
        ids, descriptions = sorted(question.options), question.options
    else:
        raise ValueError("expected noul or choice")
    if len(ids) > len(config.labels):
        raise ValueError("not enough B1 labels")
    labels = config.labels[:len(ids)]
    label_map = dict(zip(labels, ids))
    lines = [f"{label}. [{option}] {descriptions[option]}" for label, option in label_map.items()]
    user = rendered.state + "\n\n질문: " + question.instructions + "\n" + "\n".join(lines) + "\n답:"
    messages = [{"role": "system", "content": config.system}, {"role": "user", "content": user}]
    params = deepcopy(config.params)
    params["top_logprobs"] = len(ids)
    return B1Call(call_qid, messages, labels, label_map, params)
