"""Dependency-free timeout argument plumbing for the agent runner."""

import argparse
import sys


TASK_TIMEOUT_HELP = (
    "Maximum time in seconds for one whole task across all its steps (default: 60); "
    "must be greater than --request-timeout."
)
REQUEST_TIMEOUT_HELP = (
    "Maximum time in seconds for one HTTP chat-completion request (default: 60)."
)
MAX_RETRIES_HELP = (
    "Maximum harness attempts per logical model call (default: 2). The SDK retry "
    "layer is disabled, so worst case is 2 x request_timeout plus harness backoff."
)


class TimeoutConfigurationError(ValueError):
    """Raised when the task budget cannot outlive one request."""


def add_timeout_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=int, default=60, help=TASK_TIMEOUT_HELP)
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=60,
        help=REQUEST_TIMEOUT_HELP,
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help=MAX_RETRIES_HELP,
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Agent runner timeout configuration")
    add_timeout_arguments(parser)
    return parser.parse_args(argv)


def validate_timeouts(args) -> None:
    if args.timeout <= args.request_timeout:
        raise TimeoutConfigurationError(
            f"--timeout ({args.timeout}s task budget) must be greater than "
            f"--request-timeout ({args.request_timeout}s per HTTP request)"
        )
    if args.max_retries < 1:
        raise TimeoutConfigurationError("--max-retries must be at least 1")


def build_adapter_config(args, config=None):
    adapter_config = {} if config is None else config
    # NOTE: 키를 "timeout" 으로 두면 run_benchmark_on_dataset 의 명명 인자
    # timeout(= 태스크 예산)과 **adapter_config 가 충돌해 TypeError 가 난다.
    # 어댑터가 기대하는 "timeout" 으로의 변환은 어댑터 생성 직전에서 한다.
    adapter_config["request_timeout"] = args.request_timeout
    return adapter_config


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        validate_timeouts(args)
    except TimeoutConfigurationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(
        f"[OK] task timeout {args.timeout}s; "
        f"request timeout {args.request_timeout}s; "
        f"max retries {args.max_retries}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
