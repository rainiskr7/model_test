"""embeval — 임베딩 모델 비교 평가 하니스.

계획안(../임베딩_모델_테스트_계획안.md)을 기능별 모듈로 구현.
  config         : 모델/태스크/설정 SSOT (+ yaml 운영 오버레이)
  models         : 모델 로딩(권장 prompt vs 통제, local/endpoint)
  datasets       : 데이터셋 실재성 검증(계획안 8절 게이트)
  retrieval_data : retrieval 코퍼스/쿼리/qrels 로딩 + 정답보존 캡(repr 입력)
  metrics        : 순위 지표(ndcg/mrr/recall) 순수 함수(repr용)
  representations: dense/sparse/hybrid 표현 비교(repr 트랙, FlagEmbedding)
  mteb_runner    : 단일 태스크 / 그룹 평가 실행(+ model_test 규약 summary)
  benchmarks     : MTEB 네이티브 번들(여러 태스크를 한 번에 묶어 실행)
  cost           : 운영 비용(latency/throughput/VRAM)
  aggregate      : 결과 매트릭스 정리
"""

__all__ = ["config", "models", "datasets", "retrieval_data", "metrics",
           "representations", "mteb_runner", "benchmarks", "cost", "aggregate"]
