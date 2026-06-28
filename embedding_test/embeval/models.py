"""모델 로딩 — 권장 프롬프트(recommended) vs 통제(controlled) 두 모드 지원.

계획안 5절: Qwen3/BGE-M3의 query/passage prefix 가 검색 점수를 크게 좌우하므로
"각 모델 권장 설정"과 "통제 설정" 결과를 분리 기록한다.

- recommended: mteb의 모델 레지스트리(`mteb.get_model`)를 우선 사용한다.
  레지스트리에 모델 메타가 있으면 권장 query/passage 프롬프트가 자동 주입된다.
- controlled : SentenceTransformer 를 프롬프트 없이 로드해 모든 모델을 동일 조건으로 비교한다.

두 모드 모두 mteb 평가 루프와 호환되는 객체(.encode 보유)를 반환한다.
"""

from __future__ import annotations

from evalcommon.torch_utils import torch_dtype as _torch_dtype, device as _device

from .config import MODELS, SETTINGS, ModelSpec, model_backend, resolve_spec


def load_model(model_key: str, prompt_mode: str):
    """평가용 모델 객체를 반환한다.

    prompt_mode: "recommended" | "controlled"
    backend(local|endpoint)는 configs/models/<key>.yaml 로 결정(없으면 local).
    local 식별값(hf_name/revision/uses_prompts)도 yaml 이 SSOT(resolve_spec).
    """
    if model_key not in MODELS:
        raise KeyError(f"알 수 없는 모델 키: {model_key} (config.MODELS: {list(MODELS)})")
    spec = resolve_spec(model_key)

    backend, endpoint_cfg = model_backend(model_key)
    if backend == "endpoint":
        return _load_endpoint(spec, endpoint_cfg)
    if backend != "local":
        raise ValueError(f"알 수 없는 backend: {backend} (local|endpoint)")

    if prompt_mode == "recommended":
        return _load_recommended(spec)
    if prompt_mode == "controlled":
        return _load_controlled(spec)
    raise ValueError(f"prompt_mode 는 'recommended'|'controlled' 여야 함: {prompt_mode}")


def _load_endpoint(spec: ModelSpec, endpoint_cfg: dict):
    """OpenAI 호환 /v1/embeddings 엔드포인트를 mteb 인코더 인터페이스로 래핑."""
    return EndpointEmbedder(spec, endpoint_cfg)


def _load_recommended(spec: ModelSpec):
    """mteb 레지스트리 우선. 메타가 있으면 권장 프롬프트가 자동 적용된다.

    주의(코덱스 리뷰 반영): prompt 의존 모델(Qwen3/kanana)이 레지스트리에 없으면
    조용히 plain SentenceTransformer 로 폴백하면 instruction 이 사라져 "recommended"
    측정이 controlled 와 같아진다 → 측정 왜곡. 따라서 uses_prompts 모델은 하드 실패시킨다.
    """
    import mteb

    dtype = _torch_dtype(SETTINGS.precision)
    try:
        # 최신 시그니처: SentenceTransformer 로 kwargs 전달(dtype/trust_remote_code 보존)
        model = mteb.get_model(
            spec.hf_name, revision=spec.revision,
            trust_remote_code=True, model_kwargs={"torch_dtype": dtype},
        )
    except TypeError:
        # 구버전 시그니처: kwargs 미지원 → 최소 인자로 재시도
        try:
            model = mteb.get_model(spec.hf_name, revision=spec.revision)
        except Exception as exc:
            model = _recommended_fallback(spec, exc)
    except Exception as exc:
        model = _recommended_fallback(spec, exc)

    _apply_seq_len(model)
    return model


def _recommended_fallback(spec: ModelSpec, exc: Exception):
    """레지스트리 미등록 시: prompt 의존 모델이면 하드 실패, 아니면 plain 로드 허용."""
    if spec.uses_prompts:
        raise RuntimeError(
            f"[models] recommended 모드: '{spec.hf_name}' 가 mteb 레지스트리에 없어 "
            f"권장 query/passage 프롬프트(instruction)를 적용할 수 없음. plain 폴백 시 "
            f"측정이 controlled 와 동일해져 왜곡됨 → 중단. "
            f"mteb 버전 업데이트 또는 모델 prompts 수동 설정 후 재실행. (원인: {exc})"
        ) from exc
    print(f"[models] '{spec.hf_name}' 레지스트리 미등록 → plain SentenceTransformer "
          f"폴백(uses_prompts=False라 안전). 원인: {exc}")
    return _load_sentence_transformer(spec, with_prompts=False)


def _load_controlled(spec: ModelSpec):
    """모든 모델 프롬프트 없이 동일 조건으로 로드(공정 비교)."""
    return _load_sentence_transformer(spec, with_prompts=False)


def _load_sentence_transformer(spec: ModelSpec, *, with_prompts: bool):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(
        spec.hf_name,
        revision=spec.revision,
        device=_device(),
        trust_remote_code=True,
        model_kwargs={"torch_dtype": _torch_dtype(SETTINGS.precision)},
    )
    _apply_seq_len(model)
    if not with_prompts:
        # 명시적으로 프롬프트 비활성(통제 모드). 모델에 디폴트 프롬프트가 있어도 무시.
        if hasattr(model, "prompts"):
            model.prompts = {}
        if hasattr(model, "default_prompt_name"):
            model.default_prompt_name = None
    return model


def _apply_seq_len(model) -> None:
    """max_seq_length 를 세 모델 동일 고정(계획안 5절 RAG truncation)."""
    target = SETTINGS.max_seq_length
    # SentenceTransformer
    if hasattr(model, "max_seq_length"):
        try:
            model.max_seq_length = target
            return
        except Exception:
            pass
    # mteb 래퍼: 내부 SentenceTransformer 보유 케이스
    inner = getattr(model, "model", None)
    if inner is not None and hasattr(inner, "max_seq_length"):
        try:
            inner.max_seq_length = target
        except Exception:
            pass


class EndpointEmbedder:
    """OpenAI 호환 /v1/embeddings 서버를 mteb 인코더로 노출(backend: endpoint).

    mteb 평가 루프는 model.encode(sentences, **kwargs) -> np.ndarray 를 사용한다.
    프롬프트 모드는 서버 측 설정을 따르므로 여기서는 적용하지 않는다(run_config 에 기록).
    """

    def __init__(self, spec: ModelSpec, endpoint_cfg: dict):
        import os
        from openai import OpenAI

        base_url = endpoint_cfg.get("base_url")
        if not base_url:
            raise ValueError(f"[models] endpoint backend 인데 base_url 이 없음: {spec.hf_name}")
        api_key = os.environ.get(endpoint_cfg.get("api_key_env", "OPENAI_API_KEY")) or "EMPTY"
        self.spec = spec
        self.model_id = endpoint_cfg.get("model_id") or spec.hf_name
        self.normalize = bool(endpoint_cfg.get("normalize_embeddings", True))
        self.client = OpenAI(base_url=base_url.rstrip("/"), api_key=api_key)

    def encode(self, sentences, batch_size: int = 32, **_kwargs):
        import numpy as np

        if isinstance(sentences, str):
            sentences = [sentences]
        texts = [s if isinstance(s, str) else self._to_text(s) for s in sentences]
        vecs: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            resp = self.client.embeddings.create(model=self.model_id, input=chunk)
            # 서버가 순서를 보장하지 않을 수 있어 index 로 정렬 후 추출.
            for d in sorted(resp.data, key=lambda x: getattr(x, "index", 0)):
                vecs.append(d.embedding)
        arr = np.asarray(vecs, dtype="float32")
        if self.normalize and arr.size:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            arr = arr / np.clip(norms, 1e-12, None)
        return arr

    # mteb retrieval 평가기는 query/corpus 인코딩을 구분해 호출한다(있으면).
    def encode_queries(self, queries, batch_size: int = 32, **kw):
        return self.encode(queries, batch_size=batch_size, **kw)

    def encode_corpus(self, corpus, batch_size: int = 32, **kw):
        # corpus 항목은 {"title","text"} dict 이거나 str.
        texts = [self._to_text(c) for c in corpus]
        return self.encode(texts, batch_size=batch_size, **kw)

    @staticmethod
    def _to_text(v) -> str:
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            title = v.get("title", "")
            text = v.get("text", "")
            return (title + "\n" + text).strip() if title else text
        return str(v)
