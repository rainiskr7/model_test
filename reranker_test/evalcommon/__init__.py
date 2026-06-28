"""evalcommon — 평가 하니스 공용 헬퍼(버전 취약 부분 단일화).

이 하니스(reranker) 안에 자체 포함된 독립 모듈이다(다른 하니스에 의존하지 않음).
torch/mteb 는 모두 함수 내부에서 지연 임포트하여, 라이브러리 미설치 환경에서도
이 모듈 자체는 import 가능하다.
"""

from .torch_utils import torch_dtype, device, set_seed, free_model
from .mteb_compat import get_task, task_languages

__all__ = ["torch_dtype", "device", "set_seed", "free_model", "get_task", "task_languages"]
