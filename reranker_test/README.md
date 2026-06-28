# rerankeval — 한국어 리랭커 비교 평가 하니스

`../리랭커_모델_테스트_계획안.md` 를 실행 코드로 옮긴 것. 임베딩 하니스(`../../embedding_model/eval`)와 짝.

## 핵심 설계

- **2-stage A/B** (계획안 1.3): retrieval 데이터 → 임베딩으로 **frozen 1차 후보(top-N)** → 리랭커 재채점
  → `baseline`(1차 순서) vs `reranked` 지표 비교. **임베딩 모델을 실행 인자**(`--embedder`)로 받음.
- **native vs 변환** (계획안 3-2, codex 검토 반영):
  - `MIRACLReranking` = MTEB **native reranking** → `native`/`smoke` 경로.
  - `Ko-StrategyQA`, `AutoRAGRetrieval`(금융), `MultiLongDocRetrieval` = **retrieval** → 2-stage `rerank` 경로.
- **candidate 수 민감도** (계획안 3·5): top-N 20/50/100 별 품질·latency 곡선.
- **데이터셋별 재시작**: 1차 후보는 `cache/` 에 동결 캐시 → 끊겨도 rerank 만 재개. 결과 JSON 있으면 건너뜀.
  특정 데이터셋만 강제 재실행은 `--overwrite`.
- **순수 지표 레이어**(`metrics.py`)는 GPU 없이 단위 테스트 → `tests/` 19개 통과.

```
eval/
├─ run.py                  # CLI
├─ requirements.txt
├─ rerankeval/
│  ├─ config.py            # 리랭커/임베더/태스크/설정 SSOT
│  ├─ metrics.py           # nDCG·MRR·P@k·HitRate@1·Recall@k (순수)
│  ├─ rerankers.py         # CrossEncoder + Qwen3 백엔드 (recommended/controlled)
│  ├─ embedders.py         # 1차 검색 임베딩
│  ├─ datasets.py          # 실재성 검증 + retrieval 로딩
│  ├─ firststage.py        # frozen 후보 생성 + 캐시(재시작)
│  ├─ rerank_runner.py     # 2-stage A/B
│  ├─ native_runner.py     # MTEB native reranking
│  ├─ latency.py           # P50/95/99·throughput·VRAM·민감도
│  └─ aggregate.py         # 결과 매트릭스
└─ tests/                  # 단위 테스트(GPU 불필요)
```

## 설치 & 실행

```bash
pip install -r requirements.txt        # torch 는 사내 CUDA 빌드에 맞춰 조정
python run.py env                       # 버전 기록(재현성)

python run.py verify                    # ① 데이터셋 실재성/성격 게이트(계획안 8절)
python run.py smoke                      # ① 스모크(native reranking)

python run.py native                     # MIRACLReranking 등 native reranking
python run.py rerank --embedder bge-m3-ko   # ② retrieval 3종 2-stage A/B
python run.py task Ko-StrategyQA         # 테스트 단위(단일 데이터셋)
python run.py rerank --overwrite --tasks AutoRAGRetrieval   # 특정 셋만 강제 재실행

python run.py latency                    # ③ latency/효율(candidate 민감도)
python run.py aggregate                  # results/summary.md, rerank_long.csv
```

공통 옵션: `--rerankers ...`, `--modes recommended controlled`, `--embedder ...`, `--overwrite`.

## 결과물

- `results/rerank/*.json` — 데이터셋별 A/B(baseline vs reranked) + Δ + top_n
- `results/native/<reranker>__<mode>/...` — mteb native 점수
- `results/summary.md` — A/B 개선폭 매트릭스 + candidate 민감도 + latency 표
- `cache/*.json` — frozen 1차 후보(재시작용)

## 실행 전 확인 (계획안 8절 게이트)

- `run.py verify` 로 4종 태스크의 **registry 정식명 + native/retrieval 성격** 확정.
  `KIND=DIFF` 는 오류가 아니라 "retrieval→rerank 변환 필요" 신호.
- 리랭커 `revision` 모두 `None` → 실행 직전 커밋 해시로 고정.
- **Qwen3-Reranker**: 2-stage(`rerank`) 경로는 동작하나, native reranking 에 넣으려면 mteb 호환
  `predict` 래퍼 필요(`native_runner._mteb_compatible` 참고 — 비호환 시 자동 skip). 또한
  `rerankers.Qwen3Reranker` 의 프롬프트/토큰은 모델 카드와 대조 검증 후 확정.
  **transformers>=4.51.0 필수**(이전 버전은 `KeyError: 'qwen3'`).
- **native reranking + CrossEncoder**: 고정 mteb 버전이 reranking 태스크에서 CrossEncoder 를
  직접 받는지 `verify`/스모크로 확인. 임베딩 기반 evaluator 만 지원하면 수동 evaluator 로 대체.
- **MIRACLReranking 한국어 subset**: native 실행 시 'ko' subset 이 실제 선택되는지 확인(8절).
- **jina-reranker-v2** 라이선스 CC-BY-NC-4.0(비상업) — 운영 후보 가부 별도 확인.
- **candidate recall 상한**: 2-stage 결과의 `candidate_recall` 이 낮으면 리랭커가 아니라
  1차 검색(임베딩) 한계 → 임베더 교체/top-N 상향 검토(품질 해석의 핵심 변수).
