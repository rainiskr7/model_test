"""무엇: pplx v1/v1.1 systemone 길이 측정 · 입력: 로컬 체크포인트 사본(토크나이저·decision_config.json·source/src/autojev)·CallPlan · 출력: LengthInfo · 계약 §4-3·§8-6 H·I."""

from jeveval.io.reference import package_module
from jeveval.io.run_files import read_json
from jeveval.io.tokenizers import load_offline, verified_directory
from jeveval.run.length import state_offsets, token_end
from jeveval.types import CallPlan, LengthInfo, ModelConfig

REQUIRED = ("decision_config.json", "source/src/autojev/model.py", "source/src/autojev/types.py")
TEMPLATE = dict(tokenize=False, add_generation_prompt=True, enable_thinking=False)
STATE_PREFIX, STATE_SUFFIX = "State:\n", "\n\nQuestion:\n"   # autojev.model.decision_messages 의 프롬프트 틀


class PplxDecisionMessages:
    """참조 autojev.model.decision_messages 로 질문마다 한 행을 만들어 잰다 — 서버 prepare 와 같은 chat 템플릿(생각 끔).

    서버는 행마다 8,192 토큰을 넘으면 잘리지 않고 거부하므로 ℓ = 행 길이의 최댓값, 고정부 = 그 행에서 state 토큰을 뺀 수,
    usage.input_tokens 는 모든 행 길이의 합이라 usage_tokens 에 따로 적는다.
    """

    def __init__(self, cfg: ModelConfig):
        """tokenizer.files_sha256 에 decision_config.json 과 autojev/model.py·types.py 가 있어야 한다 (fingerprint 에 묶임)."""
        directory = verified_directory(cfg.tokenizer)
        missing = [name for name in REQUIRED if name not in cfg.tokenizer["files_sha256"]]
        if missing:
            raise ValueError(f"tokenizer.files_sha256 must list {', '.join(missing)}")
        self.tokenizer = load_offline(directory)
        self.codes = read_json(directory / "decision_config.json")["codes"]
        self.reference = package_module(directory / "source/src", "autojev.model")
        self.limit = cfg.limit["tokens"]

    def _row(self, state: str, question: dict):
        """한 질문 행의 토큰 수·state 토큰 offsets(state 기준). state 위치는 참조 프롬프트의 'State:' 틀로 찾는다."""
        messages = self.reference.decision_messages({"state": state, "question": question}, self.codes)
        text = self.tokenizer.apply_chat_template(messages, **TEMPLATE)
        marker = STATE_PREFIX + state + STATE_SUFFIX
        if not isinstance(text, str) or text.count(marker) != 1:
            raise ValueError("rendered row must contain the State block exactly once")
        encoded = self.tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        ids = list(encoded["input_ids"])
        if ids != list(self.tokenizer.apply_chat_template(messages, **{**TEMPLATE, "tokenize": True, "return_dict": False})):
            raise ValueError("re-encoded token IDs differ from chat template")
        start = text.index(marker) + len(STATE_PREFIX)
        return len(ids), state_offsets(encoded["offset_mapping"], text, start, start + len(state), len(ids))

    def measure(self, plan: CallPlan) -> LengthInfo:
        if plan.kind != "systemone" or plan.request is None:
            raise ValueError("pplx encoder requires a systemone request")
        if self.limit is None:
            raise ValueError("limit.tokens must not be null")
        body = plan.request.to_dict()
        if body.get("images") or body.get("videos"):
            raise NotImplementedError("media requests are out of scope")
        state = body["state"]
        if self.reference.describe(state) != state or state != plan.rendered.state:
            raise ValueError("reference state rendering differs from request")
        end = plan.rendered.target_end_char
        if type(end) is not int or not 0 <= end <= len(state):
            raise ValueError("target end must be inside state")
        rows = [self._row(state, question) for question in body["questions"].values()]
        if not rows:
            raise ValueError("at least one question is required")
        count, offsets = max(rows, key=lambda row: row[0])
        return LengthInfo(count, token_end(offsets, end), self.limit, count - len(offsets),
                          usage_tokens=sum(row[0] for row in rows))
