#!/bin/bash
# KO-VLM-Benchmark (Marker AI) — KO-VQA / KO-VDC / KO-OCRAG 3 sub-task
# Source: https://github.com/Marker-Inc-Korea/KO-VLM-Benchmark
#
# ⚠️ 현재 상태: 미통합 (stub) ⚠️
#
# KO-VLM-Benchmark 의 eval_VQA.py / eval_VDC.py / eval_OCRAG_v2.py 는
# **로컬 HF transformers** 로 모델을 직접 로드해서 평가하도록 hardcoded:
#   - AutoModelForCausalLM, Gemma3ForConditionalGeneration,
#     Qwen2_5_VLForConditionalGeneration 등 명시적 모델 클래스
#   - device_map="auto", flash_attention_2 등 GPU 직접 사용
#   - OpenAI-compat API 옵션 없음
#
# 우리 환경 (GPUStack OpenAI-compat) 에서는 그대로 동작 불가.
#
# 또한 repo 의 data/*.{csv,xlsx} 는 작은 sample subset 만 포함:
#   - 실제 평가셋 + 이미지는 외부에서 별도 다운로드 필요 (AI Hub 등)
#   - data/images/ 비어있음
#
# 통합하려면 다음 작업 필요 (별도 작업, ~수일):
#   1. 각 sub-task 의 sample csv/xlsx 읽기
#   2. (실제 데이터/이미지 외부 수집)
#   3. 자체 runner 작성 (OpenAI-compat API 호출)
#   4. KO-OCRAG 의 (1-WER + 1-CER + sBERT + ROUGE-1)/4 채점 로직 재구현
#
# 우선 KOFFVQA 처럼 자체 runner 를 만들어야 하나 데이터 의존성 큼.
#
# 대안:
#   A) KO-VLM-Benchmark 평가 보류, KRETA + K-MMBench + MTVQA(KR) 로 대체
#   B) Marker AI 와 협의해 OpenAI-compat 평가 옵션 요청
#   C) 직접 runner 작성 (별도 프로젝트)

set -e
echo "==================================================================="
echo "  KO-VLM-Benchmark — 미통합 (stub)"
echo "==================================================================="
echo ""
echo "이 wrapper 는 호환되지 않는 외부 코드를 호출하지 않습니다."
echo "통합 방식은 별도 작업으로 분리 (자세히는 본 스크립트의 주석 참조)."
echo ""
echo "현재 가용한 한국어 비전 평가:"
echo "  - K-DTCBench  (run_k_dtcbench.sh)"
echo "  - K-MMBench   (run_k_mmbench.sh)"
echo "  - MTVQA(KR)   (run_mtvqa_kr.sh)"
echo "  - KRETA       (run_kreta.sh)"
echo "  - KOFFVQA     (run_koffvqa.sh)"
echo ""
echo "==================================================================="
exit 64  # EX_USAGE
