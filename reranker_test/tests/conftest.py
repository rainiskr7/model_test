"""eval/ 를 import 경로에 추가해 `rerankeval` 패키지를 테스트에서 로드 가능하게 한다."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
