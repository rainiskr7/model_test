"""1차 검색 임베딩 로딩 — retrieval 태스크의 frozen 후보 생성용(계획안 1.3).

임베딩 모델을 '실행 인자'로 받아 임베딩×리랭커 궁합을 본다.
임베딩 평가 하니스(../../embedding_model/eval)와 동일 모델군을 재사용.
"""

from __future__ import annotations

from evalcommon.torch_utils import torch_dtype as _torch_dtype

from .config import FIRST_STAGE_EMBEDDERS, SETTINGS


def load_embedder(key: str):
    from sentence_transformers import SentenceTransformer
    import torch
    if key not in FIRST_STAGE_EMBEDDERS:
        raise KeyError(f"알 수 없는 임베더: {key} (가능: {list(FIRST_STAGE_EMBEDDERS)})")
    model = SentenceTransformer(
        FIRST_STAGE_EMBEDDERS[key],
        device="cuda" if torch.cuda.is_available() else "cpu",
        trust_remote_code=True,
        model_kwargs={"torch_dtype": _torch_dtype(SETTINGS.precision)},
    )
    if hasattr(model, "max_seq_length"):
        model.max_seq_length = SETTINGS.max_doc_len
    return model
