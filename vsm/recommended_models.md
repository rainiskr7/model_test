# vsm 평가 대상 모델 (소형 비전+텍스트 LLM)

| 모델 | 타입 | 활성 | 멀티모달 | 네이티브 컨텍스트 | 출시 |
|---|---|---|---|---|---|
| Qwen/Qwen3.5-35B-A3B | MoE | 3B | ✅ | 262K | 2026-02-24 |
| Qwen/Qwen3.6-35B-A3B | MoE | 3B | ✅ | 262K | 2026-04 |
| Qwen/Qwen3.5-27B | Dense | 27B | ✅ | 262K | 2026-02-24 |
| Qwen/Qwen3.6-27B | Dense | 27B | ✅ | 262K | 2026-04-22 |
| google/gemma-4-31B-it | Dense | 31B | ✅ | 256K | — |
| google/gemma-4-26B-A4B | MoE | 4B | ✅ | 256K | — |

## 환경 (확정)

- 비양자화 (BF16/FP16)
- gpustack 2.1.3 + vLLM 0.20.0
- 컨텍스트 200K
- non-thinking 통일 (Qwen3.6 thinking은 부록 트랙)

## 결과 위치

`<model_test>/results/<safe_model_name>/<timestamp>/{language,vision}/<track>/<benchmark>.json`

예: `results/Qwen_Qwen3.5_35B_A3B/20260503_043000/vision/multimodal/kreta.json`

## 양자화 변종 (비교 검토 시)

같은 모델의 양자화 변종은 폴더명에서 즉시 구분됨:
- `Qwen_Qwen3.5_35B_A3B` (BF16 원본)
- `Qwen_Qwen3.5_35B_A3B_FP8` (Qwen 공식 FP8)
- `unsloth_Qwen3.5_35B_A3B_GGUF` (unsloth GGUF)
- `mlx_community_Qwen3.5_35B_A3B_4bit` (mlx 4bit)
