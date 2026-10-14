"""무엇: T0 참조 로딩·공개 응답 · 입력: 로컬 checkpoint/요청 · 출력: T0Reference/응답 · 계약 §8-6 H·I."""

from jeveval.reference import clef_runner, pplx_runner
from jeveval.types.t0_io import T0Reference


def load(family, checkpoint, *, device="cuda", max_length=16384, reference=None,
         answer_module=None, server=None):
    if family in ("clef", "clef_flash"):
        module, model, processor = clef_runner.load(checkpoint, device=device, reference=reference)
        return T0Reference(family, model, module, processor, max_length=max_length)
    if family == "pplx_v1":
        from jeveval.io.reference import local_checkpoint, source_module
        path = local_checkpoint(checkpoint)
        module = reference or source_module(path / "inference.py", "_jeveval_pplx_v1_reference")
        model = pplx_runner.load_v1(path, device=device, reference=module)
        if answer_module is None:
            from autojev import model as answer_module
        return T0Reference(family, model, module, answer_module=answer_module)
    if family == "pplx_v1_1":
        model = pplx_runner.load_v11(checkpoint, device=device, reference=reference)
        if reference is None:
            from autojev import model as reference
        if server is None:
            from autojev import server
        return T0Reference(family, model, reference, server=server)
    raise ValueError("unsupported T0 family")


def respond(runtime, body):
    if runtime.family in ("clef", "clef_flash"):
        return clef_runner.respond(runtime.module, runtime.model, runtime.processor, body,
                                   max_length=runtime.max_length)
    if runtime.family == "pplx_v1":
        return pplx_runner.respond_v1(runtime.model, body)
    return pplx_runner.respond_v11(runtime.model, body, server=runtime.server)
