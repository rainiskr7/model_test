"""bench CLI 인자 빌더 — 단일 책임 모듈.

표준 bench argparser(standard_argparser). common.py 가 re-export 하므로
기존 `from common import standard_argparser` 도 그대로 동작.
"""

import argparse


def standard_argparser(default_endpoint: str = "http://172.16.1.81:18090/v1") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="모델명 (OpenAI-compat 서빙되는 모델)")
    parser.add_argument("--base-url", default=default_endpoint, help=f"OpenAI-compat endpoint (default: {default_endpoint})")
    parser.add_argument("--api-key", default=None, help="API key (없으면 OPENAI_API_KEY env 또는 EMPTY)")
    parser.add_argument("--limit", type=int, default=None, help="샘플 수 제한 (디버깅용)")
    parser.add_argument("--max-tokens", type=int, default=512, help="응답 max_tokens")
    parser.add_argument("--temperature", type=float, default=0.0, help="응답 temperature (default 0.0, 결정론적)")
    # 재현성·견고성
    parser.add_argument("--seed", type=int, default=None, help="OpenAI seed (default None, 서버 지원 시 결정론적)")
    parser.add_argument("--timeout", type=float, default=60.0, help="요청 timeout 초")
    parser.add_argument("--retry-max", type=int, default=3, help="일시 오류 재시도 횟수")
    parser.add_argument("--retry-backoff", type=float, default=1.0, help="재시도 backoff 기준 초 (지수 증가)")
    parser.add_argument("--revision", type=str, default=None,
                        help="HuggingFace dataset commit SHA (강제 재현 시 사용). "
                             "미지정 시 환경변수 또는 latest. 미지정+latest 사용 시 run_config 에 캡처된 SHA 만 기록됨.")
    return parser
