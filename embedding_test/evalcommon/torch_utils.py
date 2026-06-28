"""torch/디바이스 공용 헬퍼. torch 는 함수 내부 지연 임포트."""

from __future__ import annotations


def torch_dtype(precision: str):
    import torch
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[precision]


def device() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def set_seed(seed: int) -> None:
    """재현성: random/numpy/torch 시드 고정(설치된 것만)."""
    import random
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except Exception:
        pass
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except Exception:
        pass


def free_model(*objs) -> None:
    """모델 객체 참조 해제 + CUDA 캐시 비우기(루프에서 OOM 방지)."""
    import gc
    for o in objs:
        del o
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
