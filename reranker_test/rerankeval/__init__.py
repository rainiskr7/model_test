"""rerankeval — 한국어 리랭커 비교 평가 하니스.

계획안(../리랭커_모델_테스트_계획안.md)을 기능별 모듈로 구현.
  config        : 리랭커/임베더/태스크/설정 SSOT
  metrics       : nDCG·MRR·P@k·HitRate@1 (순수 함수)
  rerankers     : 리랭커 로딩(cross_encoder/causal_lm) — recommended vs controlled
  embedders     : 1차 검색 임베딩(실행 인자)
  datasets      : 데이터셋 실재성 검증 + retrieval 로딩
  firststage    : frozen 1차 후보 생성 + 캐시(데이터셋별 재시작)
  rerank_runner : 2-stage A/B 평가(retrieval 태스크)
  native_runner : MTEB native reranking 태스크
  latency       : P50/95/99·throughput·VRAM·candidate 민감도
  aggregate     : 결과 매트릭스
"""

__all__ = ["config", "metrics", "rerankers", "embedders", "datasets",
           "firststage", "rerank_runner", "native_runner", "latency", "aggregate"]
