"""무엇: Clef/Clef-Flash 얇은 호출 층 · 입력: 로컬 체크포인트/요청 · 출력: 원 응답 · 계약 §8-6 H·I."""


def load(checkpoint, *, device="cuda", reference=None):
    """참조 로더만 모델을 만든다. reference는 같은 API의 시험 주입 지점이다."""
    from jeveval.io.reference import local_checkpoint, source_module

    path = local_checkpoint(checkpoint)
    if reference is None:
        reference = source_module(path / "joint_schema_model.py", "_jeveval_clef_reference")
    model, processor = reference.load_release_model(path, device=device, local_files_only=True)
    return reference, model, processor


def respond(reference, model, processor, request, *, max_length=16384):
    """전체 요청을 그대로 전달한다. 잘림·반올림·choice 선택은 참조 구현 소유다."""
    return reference.systemone(model, processor, request, max_length=max_length)
