"""무엇: 셋 reader 선택 · 입력: 셋·설정·root · 출력: SourceRow 목록 · 계약 §6."""

from jeveval.io.sources import functionchat, klue_mrc, kmhas, korfin, kosgd, kote
from jeveval.types import SourceRow


READERS = {"kosgd": kosgd, "fc_call_decision": functionchat, "kmhas": kmhas,
           "kote_escalation": kote, "korfin_asc": korfin, "klue_mrc_answerable": klue_mrc}


def read_set_rows(set_name, set_cfg, root) -> list[SourceRow]:
    """KOTE에만 투표 설정을 전달하며 알 수 없는 셋은 거부한다."""
    if set_name not in READERS:
        raise ValueError(f"unknown set: {set_name}")
    kwargs = {"votes_cfg": set_cfg["votes"]} if set_name == "kote_escalation" else {}
    return READERS[set_name].read_rows(set_cfg["source"], root, **kwargs)
