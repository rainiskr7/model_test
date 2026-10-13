"""Multiple-choice answer extraction shared by the Korean vision benches."""

import re


def extract_choice(response: str) -> str:
    """Extract A/B/C/D from response (한국어 답변 패턴 포함). Returns '' if not found."""
    if not response:
        return ""
    s = response.strip()
    s_up = s.upper()
    # 1) 첫 문자가 letter (가장 빠른 케이스)
    if s_up and s_up[0] in "ABCD":
        return s_up[0]
    # 2) 한국어 답변 패턴 (우선순위 순)
    patterns = [
        r'정답[은:]?\s*[\(\[]?\s*([ABCD])',   # "정답: B", "정답은 B", "정답:(B)"
        r'답[은:]?\s*[\(\[]?\s*([ABCD])',     # "답: B", "답은 B"
        r'[\(\[]([ABCD])[\)\]]',              # "(B)", "[B]"
        r'\b([ABCD])\s*번',                   # "B번"
        r'\b([ABCD])\s*[\)\]\.]',             # "B)", "B]", "B."
        r'\b([ABCD])\b',                       # word-boundary fallback
    ]
    for pat in patterns:
        m = re.search(pat, s_up)
        if m:
            return m.group(1)
    return ""
