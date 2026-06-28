# vlm 평가 대상 모델 (대형 비전+텍스트 LLM)

| 모델 | 타입 | 활성 | 멀티모달 | 양자화 | 출시 |
|---|---|---|---|---|---|
| Qwen/Qwen3.5-122B-A10B | MoE | 10B | ✅ | BF16 (8×80G OK) | 2026-02-24 |
| Qwen/Qwen3.5-397B-A17B | MoE | 17B | ✅ | **FP8 권장** (BF16 8×80G 불가) | 2026-02-16 |
| Qwen/Qwen3.6-122B-A10B | MoE | 10B | ✅(예상) | BF16 | 출시 확인 필요 |
| Qwen/Qwen3.6-397B-A17B | MoE | 17B | ✅(예상) | FP8 | 출시 확인 필요 |

## 환경

- gpustack 2.1.3 + vLLM 0.20.0
- 컨텍스트 200K
- 8×80G + `--enable-expert-parallel` 필수
- 동시성 1~4 (단일 노드 점유)

## 빅모델 고유 검증

- **Published 점수 재현** (Qwen 공식 점수 vs 본 환경 ±5pt 이내)
- **양자화 손실 분리** (122B BF16 vs FP8 미니 비교 50~100문제)
- **운영 비용** (호출당 GPU·sec, 토큰당 비용)

## 결과 위치

`<model_test>/results/<safe_model_name>/<timestamp>/{language,vision}/<track>/<benchmark>.json`

예: `results/Qwen_Qwen3.5_122B_A10B_FP8/20260503_120000/vision/multimodal/kreta.json`
