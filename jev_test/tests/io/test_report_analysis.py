"""무엇: 보조 절 구분 · 입력: 보고 타입 · 출력: 제목/조건부 설명 · 계약 §7-6."""

from jeveval.io.report_analysis import selective, score_variants
from jeveval.types.report import ReportSelective, ReportScoreVariants


def test_titles_and_missing_auxiliary():
    lines = selective(ReportSelective('missing', None, {}))
    assert '선택적 예측(보조, 인증과 별개)' in lines
    assert '관측 n에 조건부인 가정상 통과 확률' in lines
    assert '확신 변형(탐색적; 주 지표 인증과 별개)' in score_variants(ReportScoreVariants('exploratory', {}))
