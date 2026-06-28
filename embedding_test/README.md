# embeval — 임베딩 모델 비교 평가 하니스

`../임베딩_모델_테스트_계획안.md` 를 실행 가능한 코드로 옮긴 것.
대상 모델: **Qwen3-Embedding-8B / kanana-nano-2.1b-embedding / bge-m3-korean**.

## 설계 원칙

- **기능별 모듈**: 모델 로딩 / 데이터셋 검증 / 실행 / 비용 / 정리를 분리.
- **테스트 단위 실행**: 그룹 전체뿐 아니라 데이터셋 1개만도 실행 가능 (`run.py task <Name>`).
- **MTEB 번들**: 여러 태스크를 한 번에 묶어 실행 (`run.py bundle ...`, `run.py official ...`).
- **언제든 재시작**: 중간에 끊겨도 같은 명령 재실행 시 **완료된 데이터셋은 건너뛰고 이어서** 돈다
  (mteb `overwrite_results=False`). 특정 데이터셋만 강제 재실행은 `--overwrite`.

```
eval/
├─ run.py                  # CLI 진입점(서브커맨드)
├─ requirements.txt        # 버전 핀 고정(계획안 5절 재현성)
├─ embeval/
│  ├─ config.py            # 모델/태스크/설정 SSOT
│  ├─ models.py            # 권장(recommended) vs 통제(controlled) prompt 로딩
│  ├─ datasets.py          # 데이터셋 실재성 검증(계획안 8절 게이트)
│  ├─ mteb_runner.py       # 단일 태스크 / 그룹 / 번들 평가
│  ├─ benchmarks.py        # MTEB 네이티브 번들 + 공식 벤치마크
│  ├─ cost.py              # 운영 비용(latency/throughput/VRAM)
│  └─ aggregate.py         # 결과 매트릭스(CSV/MD)
└─ tests/                  # 하니스 자체 단위 테스트(GPU 불필요)
```

## 설치

```bash
pip install -r requirements.txt   # torch 라인은 사내 PC CUDA 빌드에 맞춰 조정
python run.py env                 # 설치된 실제 버전 기록(재현성 로그)
```

## 실행 순서 (계획안 5절 절차)

```bash
# ① 데이터셋 실재성 먼저 확정 (계획안 8절 — 가장 중요한 게이트)
python run.py verify             # registry 존재 확인
python run.py verify --load      # 실제 데이터 로드까지 확인(느림)
python run.py list-ko            # registry 한국어 태스크 실재명 덤프

# ① 스모크: 3개 모델이 끝까지 도는지 (점수 아닌 파이프라인 검증)
python run.py smoke

# ③ 범용 한국어 / ④ 금융
python run.py korean
python run.py financial

# 테스트 단위(데이터셋 1개)만, 또는 끊긴 것 이어서:
python run.py task KorSTS
python run.py task FiQA2018 --overwrite     # 그 데이터셋만 강제 재실행

# MTEB 번들로 묶어 실행:
python run.py bundle korean
python run.py official "MTEB(kor, v1)"      # 이름은 list-benchmarks 로 확인

# ⑤ 운영 비용 / ⑥ 결과 정리
python run.py cost
python run.py aggregate          # results/summary.md, scores_long.csv 생성
```

공통 옵션: `--models qwen3-8b ...`, `--modes recommended controlled`,
`--include-fallback`, `--overwrite`.

## 결과물

- `results/<group>/<model>__<mode>/...` : mteb 원본 점수 JSON
- `results/scores_long.csv` : long-format 점수
- `results/summary.md` : 모델×태스크 매트릭스 + 운영 비용 표 (prompt_mode 별 분리)

## 하니스 자체 테스트

```bash
pip install pytest && pytest tests/ -q     # 또는 README 하단의 무-pytest 러너
```
GPU/mteb 없이 config 무결성·점수 파싱·비용 헬퍼 로직을 검증한다.

## 계획안 대비 미해결(실행 전 확인 필요)

`config.py` 의 `status="unverified"` 태스크들은 **이름이 추정치**다.
`run.py verify` 결과로 정식명을 확정한 뒤 `config.py` 를 갱신할 것:
- `KLUE-STS`, `KLUE-TC`, `Ko-StrategyQA` → mteb 실제 클래스명 확인
- `KlueMrcDomainClustering`, `KorFin-ASC` → **미존재 추정**(계획안 8.1). 없으면 대체/제거.
- 모델 `revision` 은 모두 `None` → 실행 직전 커밋 해시로 고정(재현성).
