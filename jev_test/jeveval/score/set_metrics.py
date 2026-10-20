"""무엇: family 지표 의미 · 입력: family 이름 · 출력: 불변 MetricSpec · 계약 §7-6."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class MetricSpec:
    f1_undefined_labels: tuple[str, ...] = ()
    observation_excluded_labels: tuple[str, ...] = ()
    pooled_aspect_label: str | None = None
    aspect_flag_prefix: str | None = None
    slot_specific: bool = False
    mix_service: bool = False
    mix_stratum: bool = False
    kosgd_decompose: bool = False


METRICS = MappingProxyType({
    "kosgd": MetricSpec(slot_specific=True, mix_service=True, kosgd_decompose=True),
    "fc_call_decision": MetricSpec(("fc:tool",), ("fc:tool",)),
    "korfin_asc": MetricSpec(pooled_aspect_label="korfin:sentiment", aspect_flag_prefix="aspect_not_in_text:"),
    "klue_mrc_answerable": MetricSpec(mix_stratum=True),
})


def metric_spec(family):
    """조회는 조립 경계에서만 수행하며 계산에는 반환값을 전달한다."""
    return METRICS.get(family, MetricSpec())
