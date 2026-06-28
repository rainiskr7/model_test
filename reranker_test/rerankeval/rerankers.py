"""리랭커 로딩/스코어링 — 백엔드 2종을 단일 인터페이스로 묶는다(하네스 핵심).

인터페이스: Reranker.score(query, documents) -> list[float] (높을수록 관련).

backend(스코어링 구현, yaml local_backend):
  "cross_encoder" : sentence_transformers.CrossEncoder (cross-encoder 계열 리랭커)
  "causal_lm"     : 생성형 리랭커 (yes/no 토큰 로그릿 softmax). 템플릿/토큰은 전적으로 yaml 로 주입
                    (코드에 모델 특화 기본값 없음 — 새 생성형 모델도 yaml 만으로 동작).

prompt_mode:
  "recommended" : 모델 권장 포맷(instruction/yes-no 프롬프트) 적용
  "controlled"  : 순수 (query, document) 쌍만 — 모든 모델 동일 조건(공정 비교)
"""

from __future__ import annotations

from evalcommon.torch_utils import torch_dtype as _torch_dtype, device as _device

from .config import SETTINGS, RerankerSpec, resolve_spec


def load_reranker(key: str, prompt_mode: str):
    spec = resolve_spec(key)  # configs/models/*.yaml 발견으로 구성된 spec
    if prompt_mode not in ("recommended", "controlled"):
        raise ValueError(f"prompt_mode: {prompt_mode}")
    recommended = (prompt_mode == "recommended")
    if spec.backend == "cross_encoder":
        return CrossEncoderReranker(spec, recommended)
    if spec.backend == "causal_lm":
        return CausalLMReranker(spec, recommended)
    raise ValueError(f"알 수 없는 스코어링 backend: {spec.backend} (cross_encoder|causal_lm)")


class CrossEncoderReranker:
    """CrossEncoder 계열 리랭커(configs/models 발견)."""

    def __init__(self, spec: RerankerSpec, recommended: bool):
        from sentence_transformers import CrossEncoder
        self.spec = spec
        self.recommended = recommended
        self.model = CrossEncoder(
            spec.hf_name, revision=spec.revision, max_length=SETTINGS.max_doc_len,
            device=_device(), trust_remote_code=True,
            automodel_args={"torch_dtype": _torch_dtype(SETTINGS.precision)},
        )

    def score(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        pairs = [[query, d] for d in documents]
        scores = self.model.predict(
            pairs, batch_size=SETTINGS.rerank_batch_size, show_progress_bar=False,
        )
        return [float(s) for s in scores]


_REQUIRED_PROMPT_KEYS = ("prefix", "suffix", "instruct", "body_template")


class CausalLMReranker:
    """생성형(causal-LM) 리랭커: 문서 관련 여부를 yes/no 토큰 로그릿 softmax 로 점수화.

    프롬프트 템플릿(prefix/suffix/instruct/body_template)과 yes/no 토큰은 전적으로 spec(=yaml)
    에서 온다. 코드에는 어떤 모델 특화 기본값도 두지 않는다(모델 비종속). 새 생성형 리랭커는
    configs/models/<key>.yaml 의 local.prompt 에 자기 템플릿을 적으면 그걸로 동작한다.
    ⚠️ 각 모델의 토큰/템플릿은 모델 카드와 대조 후 yaml 로 확정할 것.
    """

    def __init__(self, spec: RerankerSpec, recommended: bool):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.spec = spec
        self.recommended = recommended
        p = spec.prompt
        if not p or any(k not in p for k in _REQUIRED_PROMPT_KEYS):
            raise ValueError(
                f"[rerankers] causal_lm '{spec.hf_name}' 는 configs/models/{spec.key}.yaml 의 "
                f"local.prompt 에 {_REQUIRED_PROMPT_KEYS} 가 모두 필요합니다(코드에 기본 템플릿 없음 — "
                f"모델 비종속 원칙). 모델 카드의 reranking 프롬프트를 yaml 에 기입하세요.")
        self._prefix = p["prefix"]
        self._suffix = p["suffix"]
        self._instruct = p["instruct"]
        self._body_tmpl = p["body_template"]
        self.tok = AutoTokenizer.from_pretrained(
            spec.hf_name, revision=spec.revision, padding_side="left", trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            spec.hf_name, revision=spec.revision,
            torch_dtype=_torch_dtype(SETTINGS.precision), trust_remote_code=True,
        ).to(_device()).eval()
        self.yes_id = self.tok.convert_tokens_to_ids(spec.yes_token)
        self.no_id = self.tok.convert_tokens_to_ids(spec.no_token)
        # prefix/suffix 를 미리 토크나이즈하고 본문(body)만 잘라낸다(suffix=스코어 위치 보존).
        self._prefix_ids = self.tok.encode(self._prefix, add_special_tokens=False)
        self._suffix_ids = self.tok.encode(self._suffix, add_special_tokens=False)

    def _body(self, query: str, doc: str) -> str:
        instruct = self._instruct if self.recommended else ""
        return self._body_tmpl.format(instruct=instruct, query=query, document=doc)

    def score(self, query: str, documents: list[str]) -> list[float]:
        import torch
        if not documents:
            return []
        body_budget = SETTINGS.max_doc_len - len(self._prefix_ids) - len(self._suffix_ids)
        if body_budget <= 0:
            raise ValueError("max_doc_len 이 prefix+suffix 보다 작습니다 — config.max_doc_len 상향 필요.")

        out: list[float] = []
        bs = SETTINGS.rerank_batch_size
        for i in range(0, len(documents), bs):
            chunk = documents[i:i + bs]
            feats = []
            for d in chunk:
                body_ids = self.tok.encode(self._body(query, d), add_special_tokens=False,
                                           truncation=True, max_length=body_budget)
                feats.append({"input_ids": self._prefix_ids + body_ids + self._suffix_ids})
            # 좌측 패딩 → 모든 시퀀스의 마지막 토큰이 suffix 끝(스코어 위치)에 정렬됨
            enc = self.tok.pad(feats, padding=True, return_tensors="pt").to(self.model.device)
            with torch.no_grad():
                logits = self.model(**enc).logits[:, -1, :]
            yes, no = logits[:, self.yes_id], logits[:, self.no_id]
            prob_yes = torch.softmax(torch.stack([no, yes], dim=-1), dim=-1)[:, 1]
            out.extend(float(p) for p in prob_yes)
        return out
