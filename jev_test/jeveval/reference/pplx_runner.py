"""무엇: pplx 버전별 호출 층 · 입력: 로컬 모델/systemone 요청 · 출력: 응답 · 계약 §8-6 H·I.

P1은 가짜 참조 모듈 seam만 검증한다. 실제 autojev에 고정 logit을 넣는 검사는 P0다.
"""


def load_v1(checkpoint, *, device="cuda", reference=None):
    from jeveval.io.reference import local_checkpoint, source_module

    path = local_checkpoint(checkpoint)
    if reference is None:
        reference = source_module(path / "inference.py", "_jeveval_pplx_v1_reference")
    return reference.Decider.from_pretrained(str(path), device=device)


def respond_v1(decider, request):
    """Decider.predict는 이미 temperature를 적용한 Answer를 반환한다."""
    answers = {qid: decider.predict(request["state"], question, images=request.get("images", ()))
               for qid, question in request["questions"].items()}
    return dict(model=request["model"], answers=answers)


def load_v11(checkpoint, *, device="cuda", reference=None):
    from jeveval.io.reference import local_checkpoint

    path = local_checkpoint(checkpoint)
    if reference is None:
        from autojev import model as reference
    return reference.DecisionModel(checkpoint=path, device=device)


def respond_v11(model, request, *, server=None):
    """8개 batching·temperature·softmax·answer 변환은 서버 predict에 모두 위임한다."""
    if server is None:
        from autojev import server
    body = server.EvaluationRequest(**request)
    return server.predict(model, body)
