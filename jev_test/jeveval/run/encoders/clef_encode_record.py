"""무엇: Clef·Clef-Flash systemone 길이 측정 · 입력: 로컬 체크포인트 사본(토크나이저 + joint_schema_model.py)·CallPlan · 출력: LengthInfo · 계약 §4-3·§8-6 H·I."""

from jeveval.io.reference import source_module
from jeveval.io.tokenizers import load_offline, verified_directory
from jeveval.run.length import token_end
from jeveval.types import CallPlan, LengthInfo, ModelConfig

REFERENCE_FILE = "joint_schema_model.py"
UNBOUNDED = 1 << 31


def _offsets(encoded, text: str, count: int) -> list[tuple[int, int]]:
    """state 하나만 토큰화했으므로 offsets 는 이미 state 시작 기준이다. 개수·범위만 검사한다."""
    offsets = encoded["offset_mapping"]
    if len(offsets) != count:
        raise ValueError("offset count differs from token count")
    result = []
    for left, right in offsets:
        if type(left) is not int or type(right) is not int or not 0 <= left <= right <= len(text):
            raise ValueError("invalid token offsets")
        result.append((left, right))
    return result


class ClefEncodeRecord:
    """참조 구현(joint_schema_model.encode_record)을 그대로 불러 잰다 — 프롬프트 틀·잘림 규칙을 다시 구현하지 않는다 (H·I).

    길이 ℓ = encode_record(max_length 무제한) 의 input_ids 수, 고정부 = max_state_tokens=0 일 때의 수,
    대상 끝 = render(state) 를 같은 토크나이저로 잰 offsets 에서 target_end_char 를 덮는 마지막 토큰.
    참조는 state_ids[:max_length - fixed_length] 로 꼬리를 자르므로 run/length.classify 의 구분과 맞는다.
    """

    def __init__(self, cfg: ModelConfig):
        """tokenizer.files_sha256 에 joint_schema_model.py 가 있어야 한다 — 그 해시가 fingerprint 에 들어간다."""
        directory = verified_directory(cfg.tokenizer)
        if REFERENCE_FILE not in cfg.tokenizer["files_sha256"]:
            raise ValueError(f"tokenizer.files_sha256 must list {REFERENCE_FILE}")
        self.tokenizer = load_offline(directory)
        self.reference = source_module(directory / REFERENCE_FILE, "_jeveval_clef_encoder")
        self.limit = cfg.limit["tokens"]

    def _length(self, body: dict, **kwargs) -> int:
        record = self.reference.encode_record(self.tokenizer, body, max_length=UNBOUNDED,
                                              processor=None, **kwargs)
        return len(record.input_ids)

    def measure(self, plan: CallPlan) -> LengthInfo:
        """systemone 텍스트 요청만. 참조의 state 렌더링이 요청의 state 와 같지 않으면 거부한다."""
        if plan.kind != "systemone" or plan.request is None:
            raise ValueError("clef encoder requires a systemone request")
        if self.limit is None:
            raise ValueError("limit.tokens must not be null")
        body = plan.request.to_dict()
        if body.get("images") or body.get("videos"):
            raise NotImplementedError("media requests are out of scope")
        state = self.reference.render(body["state"])
        if state != plan.rendered.state:
            raise ValueError("reference state rendering differs from request")
        end = plan.rendered.target_end_char
        if type(end) is not int or not 0 <= end <= len(state):
            raise ValueError("target end must be inside state")
        total, fixed = self._length(body), self._length(body, max_state_tokens=0)
        encoded = self.tokenizer(state, add_special_tokens=False, return_offsets_mapping=True)
        count = len(encoded["input_ids"])
        if count != total - fixed:
            raise ValueError("state token count differs from reference encoding")
        return LengthInfo(total, token_end(_offsets(encoded, state, count), end), self.limit, fixed)
