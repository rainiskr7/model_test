# results/ 색인 (2026-10-10)

세션 폴더를 옮기지 않고 여기서 분류한다. 문서·시험 코드가 경로를 직접 가리키기 때문이다(예: TAUBENCH_TRACK_RESULTS.md 의 tbfix_*, multimodal 시험의 gemma_4_26b_a4b_it).
분류: **본** = 현행 비교의 본 측정 · **보조** = 같은 모델의 별도 본 측정(트랙 하나) · **실험** = 디버깅·설정 시험·재현 확인 · **구판** = 이전 라운드(5~7월) · **무효** = 측정 조건 결함으로 격리.
세션 안의 `<트랙>.<사유>_<날짜>` 폴더(예: `harness.thinkopen_20261010`, `taubench.badseed_20260908`)는 격리된 무효 결과다 — 리포트 도구는 `language/<트랙>` 만 읽는다.

## 현행 비교 라운드 (8~10월)

### google_gemma_4_26B_A4B_it (gemma 4 26B A4B)
| 세션 | 분류 | 내용 |
|---|---|---|
| 20260830_095733_r1, 20260830_095733_r2, 20260927_230250_r3 | 본 | 텍스트·이미지 전 트랙 3회. KMMLU(harness)는 chat 템플릿이 생각 채널을 닫고 시작 → 유효 |
| tbstd4_20261003 | 보조 | taubench standard×4 (telecom 40, 사용자 gpt-4.1-mini, 동시 1, vLLM 0.28) |
| tbair/tbfix/tbretail_20260823, tbpin/tbrep_20260827, tbk4_/tbstd1_20261002 | 실험 | taubench 설정·재현 시험 (TAUBENCH_TRACK_RESULTS.md 참조) |
| fc1/fcrep_a/fcrep_b_20260819, fcfull_20260823 | 실험 | functionchat 재현·전량 시험 |
| v2b_20260824, 20260621_221741, v4run_20260818 | 실험 | multimodal·agent 시험 |
| 20260505_124246, 20260505_124246.bad | 구판 | 5월 라운드 |
※ 10-13 정리: 소문자 `google_gemma_4_26b_a4b_it/20260621_221741`(KRETA 원본 3파일)이 git 에 따로 추적돼 리눅스 체크아웃에서 두 폴더로 갈리고 `results_model_dir_name` 이 "case-fold ambiguous" 로 거부하던 것을, 원본 3파일을 위 폴더(`google_gemma_4_26B_A4B_it`)로 옮기고 publish sidecar 의 경로 4곳을 맞춰 해소했다. 이제 결과 폴더 철자는 한 가지뿐이다(`configs/model_identity.json` 의 소문자 키는 과거 산출물용으로 남김).

### google_diffusiongemma_26B_A4B_it — 정리: [SUMMARY.md](google_diffusiongemma_26B_A4B_it/SUMMARY.md)
| 세션 | 분류 | 내용 |
|---|---|---|
| 20260830_222550_r1, 20260830_222550_r2, 20260907_001502_r3 | 본 | nlu·functionchat·taubench(solo)·multimodal 3회. 세션 안 `taubench.badseed_20260908` 는 무효 |
| tbstd4_20261011 | 보조 | taubench standard×4 (원본 템플릿, 동시 4) 37.5% — 빈 응답 중단 41건을 측정된 실패로(채점 empty_message) |
| (없음) | — | **KMMLU 측정 불가**(확산 엔진이 echo+logprobs 요청에 죽음 — 커밋 0140030, logs/kmmlu_protocol_diag_20261010) |
| p0verify_20260816, smoke_20260812_234414, v4run_20260817, v4run2_20260817 | 실험 | agent 트랙 시험 |

### nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16 — 정리: [SUMMARY.md](nvidia_nvidia_nemotron_3.5_lightning_30b_a3b_bf16/SUMMARY.md)
| 세션 | 분류 | 내용 |
|---|---|---|
| 20260830_095747_r1, 20260830_123159_r1, 20260830_123159_r2 | 본 | nlu·functionchat·taubench(solo) 3회 (multimodal 은 텍스트 전용 모델이라 r1 만, 이미지 조건 거부). 세션 안 `harness.thinkopen_20261010`(KMMLU, 생각 열림) 무효, `taubench.timeout_20260927` 무효 |
| kmmlu_nothink_20261010_r1..r3 | 보조 | **KMMLU 재측정** chat + 생각 끔 — 0.549 / 0.549 / 0.548 (10-11 완료) |
| tbstd4_20261010 | 보조 | taubench standard×4 (동시 4) 4.4% — 식별 정보를 지어내 도구 호출 |

### qwen_qwen3.8_27b (BF16)
| 세션 | 분류 | 내용 |
|---|---|---|
| 20260927_232851_r1..r3 | 본 | 텍스트·이미지 3회 (taubench solo 는 Qwen 템플릿 거부로 측정 불가). 세션 안 `harness.thinkopen_20261010`(KMMLU 붕괴, 22.8%) 무효 |
| tbstd4_20261003 | 보조 | taubench standard×4 (동시 4) |
| kmmlu_nothink_20261011_r1..r3 | 보조 | **KMMLU 재측정** chat + 생각 끔 (10-11 09:57 시작) |

### qwen_qwen3.8_27B_FP8
| 세션 | 분류 | 내용 |
|---|---|---|
| 20261003_171917_r1..r3 | 본 | 텍스트·이미지 3회. 세션 안 `harness.thinkopen_20261010` 무효 |
| 20261003_171917_tbstd4 | 보조 | taubench standard×4 (동시 4) |
| kmmlu_nothink_20261010_r1..r3 | 보조 | **KMMLU 재측정** chat + 생각 끔 (10-10 진행 중) |

## 이전 라운드 (5~7월) — 구판 보고서용, 그대로 둔다
| 모델 폴더 | 본(구판) | 실험 |
|---|---|---|
| Qwen3.5_122B_A10B_GPTQ_Int4 | 20260720_235721 | |
| Qwen_Qwen3.6_35B_A3B | 20260524_120652 | 20260505_221108.bad(구판 무효) |
| qwen3.6_35b_a3b | | v4run_20260817 |
| qwen3.5_27b | 20260525_145725 | v4run_20260817 |
| qwen_qwen3.5_27b_fp8 | 20260705_082256 | cohort2_20260816, l2fix_20260817, v4run_20260817 |
| qwen_qwen3.5_35b_a3b | 20260621_233258 | v4run_20260817 |
| qwen_qwen3.5_35b_a3b_fp8 | 20260711_003523 | tb_std_20260819·tb_std_rep2_20260820·tb_std_rep3_20260823(taubench standard 3회), 20260823_021442, tbair/tbfix/tbretail/tbsmoke_20260823, tbpin/tbrep_20260827, tbtel_a/b_20260828, fc1/fcrep_a/b/c_20260819, fcfull_20260823, 20260823_020522, p0verify_20260816, rep2/rep3_20260818, v2_20260824_2300, v4run_20260817 |
| qwen_qwen3.6_27b | 20260622_153150 (KMMLU 는 completions+5shot 재채점 — 커밋 e886311) | |
| qwen_qwen3.6_27b_fp8 | 20260704_081047 | v4run_20260817 |
| qwen_qwen3.6_35b_a3b_fp8 | 20260702_133909 | |
| google_gemma_4_31B_it | 20260505_130752, 20260525_152204 | cohort2_20260816, l2fix_20260817, v4run_20260817 |
| meta_models_Muse_Glimmer_30B | 20260812_005758 (harness 만) | |

## 옛 이름·중복 (사용 안 함, 정리 보류)
| 대상 | 상태 |
|---|---|
| gemma_4_26b_a4b_it, gemma_4_26b_a4b_it.bad | 5월 gemma 26B 의 옛 폴더 이름 두 벌(내용 다름). multimodal 시험 코드가 참조 |
| gemma_4_31b_it | google_gemma_4_31B_it 와 같은 세션 20260505_130752 를 가짐(파일 8개 다름) |
| gemma_4_.zip | gemma_4_26b_a4b_it 폴더의 5월 압축 백업(241파일, 22.7MB) |

## 정리 기록
- 10-10: 빈 폴더 `qwen3_vl_8b_instruct/20260830_124418`(파일 0) 삭제, `qwen_qwen3.5_35b_a3b_fp8/.DS_Store` 삭제. 둘 다 git 미추적.
- 10-10: 생각 열린 chat 으로 잰 KMMLU 8개를 `language/harness.thinkopen_20261010` 으로 격리 — 목록·되돌리기: logs/kmmlu_protocol_diag_20261010/MOVED_harness_thinkopen.tsv
