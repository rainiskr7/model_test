"""텍스트/숫자 정규화 — 단일 책임 모듈.

OCR 노이즈 흡수용 정규화. common.py 가 re-export.
"""

import re
import unicodedata
from typing import Optional


def normalize_text(s: str) -> str:
    """OCR 노이즈 흡수 정규화: NFKC (전각→반각) + 공백·문장부호 정리 + lower-case.

    NFKC 가 한국어/영문/숫자/전각-반각 모두 처리 (예: '１２３' → '123').
    """
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKC", s)
    # 따옴표/괄호 제거 (OCR 흔한 노이즈)
    s = re.sub(r'[\'"`「『』」\(\)\[\]<>]', '', s)
    # 하이픈류·길이 다른 dash 통일
    s = re.sub(r'[‐‑‒–—―−]', '-', s)
    # 쉼표·마침표 양쪽 공백 제거 (숫자 1,000 vs 1, 000 통합)
    s = re.sub(r'\s*([,.])\s*', r'\1', s)
    # 다중 공백 → 단일
    s = re.sub(r'\s+', ' ', s).strip()
    return s.lower()


def normalize_number(value) -> Optional[float]:
    """숫자 문자열에서 단위/쉼표/공백 제거 후 float 반환. 실패 시 None.

    예: '12,500원' → 12500.0
        '￦12,500' → 12500.0
        '5.2 kg' → 5.2
    """
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    s = unicodedata.normalize("NFKC", value).strip()
    # 숫자 + 부호 + 점 + 쉼표 만 남김
    s = re.sub(r'[^\d.,\-+]', '', s)
    s = s.replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None
