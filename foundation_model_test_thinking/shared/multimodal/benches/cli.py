"""bench CLI 인자 빌더 — 단일 책임 모듈.

thinking sampling 인자(add_thinking_sampling_args)와 표준 bench argparser(standard_argparser).
common.py 가 re-export 하므로 기존 `from common import ...` 도 그대로 동작.
"""

import os
import argparse


def add_thinking_sampling_args(parser: argparse.ArgumentParser, *, max_tokens_fallback: str = "2048") -> None:
    """thinking sampling 인자(max_tokens/temperature/top_p/top_k/seed/timeout)를 parser 에 추가.

    여러 진입점(standard_argparser / b4 latency / run_config CLI)이 동일 정의를 공유하도록 분리.
    기본값은 모두 THINK_* env, 미설정 시 thinking 권장값. max_tokens fallback 만 진입점별로 다름
    (일반 bench 2048, latency 1024, run_config 8192). run_full_eval.sh 가 모델 yaml sampling 을 export.
    """
    parser.add_argument("--max-tokens", type=int,
                        default=int(os.environ.get("THINK_MAX_TOKENS", max_tokens_fallback)),
                        help="응답 max_tokens (thinking: 추론+답 공간; env THINK_MAX_TOKENS)")
    parser.add_argument("--temperature", type=float,
                        default=float(os.environ.get("THINK_TEMPERATURE", "0.6")),
                        help="temperature (thinking 권장 0.6; greedy 는 퇴화 유발)")
    parser.add_argument("--top-p", type=float,
                        default=float(os.environ.get("THINK_TOP_P", "0.95")),
                        help="nucleus top_p (thinking 권장 0.95)")
    parser.add_argument("--top-k", type=int,
                        default=int(os.environ.get("THINK_TOP_K", "20")),
                        help="top_k (vLLM extra_body 로 전달; thinking 권장 20). 0/음수면 미전달")
    parser.add_argument("--seed", type=int,
                        default=int(os.environ.get("THINK_SEED", "42")),
                        help="OpenAI seed (sampling 재현성; env THINK_SEED)")
    parser.add_argument("--timeout", type=float,
                        default=float(os.environ.get("THINK_TIMEOUT", "600")),
                        help="요청 timeout 초 (thinking 은 느려서 default 600)")


def standard_argparser(default_endpoint: str = "http://172.16.1.81:18090/v1") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="모델명 (OpenAI-compat 서빙되는 모델)")
    parser.add_argument("--base-url", default=default_endpoint, help=f"OpenAI-compat endpoint (default: {default_endpoint})")
    parser.add_argument("--api-key", default=None, help="API key (없으면 OPENAI_API_KEY env 또는 EMPTY)")
    parser.add_argument("--limit", type=int, default=None, help="샘플 수 제한 (디버깅용)")
    # thinking sampling 인자(공통 정의 — add_thinking_sampling_args)
    add_thinking_sampling_args(parser, max_tokens_fallback="2048")
    parser.add_argument("--retry-max", type=int, default=3, help="일시 오류 재시도 횟수")
    parser.add_argument("--retry-backoff", type=float, default=1.0, help="재시도 backoff 기준 초 (지수 증가)")
    parser.add_argument("--revision", type=str, default=None,
                        help="HuggingFace dataset commit SHA (강제 재현 시 사용). "
                             "미지정 시 환경변수 또는 latest. 미지정+latest 사용 시 run_config 에 캡처된 SHA 만 기록됨.")
    return parser
