"""객관식/자유서술형 최종 답 추출 — 단일 책임 모듈.

thinking 모델은 추론 트레이스(<think> 또는 reasoning_content)를 낸 뒤 최종 답을 쓴다.
chat_with_image() 가 이미 추론을 strip 해 '최종 답' 텍스트만 넘기지만, 추론이
content 에 새는 경우(서버 파서 없음 + 태그 누락)에도 견고하도록 여기서 다시
'명시적 정답 마커의 *마지막* 매치'를 우선한다 — 추론 중간에 흩어진 A/B/C/D 가
먼저 잡히는 non-thinking 시절의 오답 추출을 방지한다.

원래 k_mmbench.py / k_dtcbench.py 에 동일 코드가 중복돼 있던 것을 한 곳으로 모았다.
"""

import re
from typing import Optional

# "정답: B", "정답은 (B)", "Answer: C", "최종 답: D" 등 — 그룹 1 = 보기 문자
_CHOICE_MARKER_PATS = [
    r'정답[은:\s]*[\(\[]?\s*([ABCD])\b',
    r'최종\s*답[은:\s]*[\(\[]?\s*([ABCD])\b',
    r'답[은:\s]*[\(\[]?\s*([ABCD])\b',
    r'ANSWER[:\s]*[\(\[]?\s*([ABCD])\b',
]
# 마커가 전혀 없을 때의 약한 fallback (우선순위 낮음)
_CHOICE_FALLBACK_PATS = [
    # 맨 앞 보기 문자 — 단, 뒤에 또 다른 라틴 글자가 오면 영어 단어(Because→B, Avenue→A)이므로 제외.
    # "A를 골랐다", "B.", "C)", 단독 "D" 는 잡고 "Because" 는 안 잡음.
    r'^([ABCD])(?![A-Za-z])',
    r'[\(\[]([ABCD])[\)\]]',   # "(B)", "[B]"
    r'\b([ABCD])\s*번',         # "B번"
    r'\b([ABCD])\s*[\)\]\.]',  # "B)", "B]", "B."
    r'\b([ABCD])\b',            # word-boundary 최후 fallback
]


def extract_choice(response: str) -> str:
    """응답에서 A/B/C/D 추출. 못 찾으면 '' 반환.

    우선순위:
      1) 명시적 정답 마커('정답:', 'Answer:' 등)의 *마지막* 매치 — thinking 답이 마지막에 옴.
      2) 괄호/맨앞글자/번호/word-boundary fallback (첫 매치, 영어 단어 오인 회피).
    """
    if not response:
        return ""
    s = response.strip()
    s_up = s.upper()

    # 1) 명시적 마커 — 가장 신뢰도 높음. 패턴별 우선이 아니라 *위치상 가장 뒤*의
    #    마커를 채택해야 한다(thinking 답이 맨 끝에 옴). 모든 마커 패턴을 finditer 로
    #    훑어 end() 가 가장 큰 매치를 고른다.
    best = None
    for pat in _CHOICE_MARKER_PATS:
        for m in re.finditer(pat, s_up):
            if best is None or m.end() > best.end():
                best = m
    if best is not None:
        return best.group(1)

    # 2) 약한 fallback (첫 매치). 맨앞글자 패턴이 'Because'(B)/'Avenue'(A) 같은 영어 단어를
    #    오인하지 않도록 뒤에 라틴 글자가 오면 제외(_CHOICE_FALLBACK_PATS 첫 패턴).
    for pat in _CHOICE_FALLBACK_PATS:
        m = re.search(pat, s_up)
        if m:
            return m.group(1)
    return ""


# 마커 자체만 매칭(꼬리는 위치로 잘라냄) → 멀티라인 답도 온전히 회수 가능.
_FINAL_MARKER_RE = re.compile(r'(?:최종\s*답|정답|답)\s*[:：]\s*', re.IGNORECASE)


def extract_final_answer(text: Optional[str], multiline: bool = False) -> str:
    """자유서술형 최종 답 추출.

    '최종 답:' / '정답:' / '답:' 마커가 있으면 *마지막* 마커 뒤를 답으로 취한다.
    - multiline=False (mtvqa 등 단답형): 마커 뒤 *첫 줄*만.
    - multiline=True (koffvqa 등 서술형): 마커 뒤 *전체*(여러 줄 포함).
    마커가 없거나 뒤가 비면 입력 전체를 그대로 반환(미준수 fallback — 지금보다 나빠지지 않음).
    """
    if not text:
        return ""
    matches = list(_FINAL_MARKER_RE.finditer(text))
    if matches:
        tail = text[matches[-1].end():].strip()
        if tail:
            return tail if multiline else tail.splitlines()[0].strip()
    return text.strip()
