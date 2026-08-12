#!/usr/bin/env python3
"""load_model_config.py 단독 회귀 테스트."""
import contextlib
import importlib.util
import io
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "load_model_config.py"


def load_module():
    spec = importlib.util.spec_from_file_location("load_model_config", LOADER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def capture_emit_shell(module, extra_cfg):
    cfg = {
        "model": "test_model",
        "tokenizer_path": "/tmp/test-tokenizer",
        "class": "vsm",
        "endpoint": {
            "chat": "http://127.0.0.1:18023/v1/chat/completions",
            "v1": "http://127.0.0.1:18023/v1",
        },
        "tracks": ["agent"],
    }
    cfg.update(extra_cfg)

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        module.emit_shell(cfg)
    return stdout.getvalue().splitlines()


def assert_contains(lines, expected):
    if expected not in lines:
        raise AssertionError(f"{expected!r} not in output: {lines!r}")


def assert_absent_prefix(lines, prefix):
    matches = [line for line in lines if line.startswith(prefix)]
    if matches:
        raise AssertionError(f"{prefix!r} output should be absent, got: {matches!r}")


def main():
    module = load_module()
    cases = [
        (
            "agent.native_tool_calling true",
            {"agent": {"native_tool_calling": True}},
            # yaml agent 섹션이 native 모드를 켜면 runner env 도 켠다.
            "export AGENT_NATIVE_TOOL_CALLING=1",
        ),
        (
            "agent.native_tool_calling false",
            {"agent": {"native_tool_calling": False}},
            # native 모드 누수를 막기 위해 false 는 명시적으로 unset 한다.
            "unset AGENT_NATIVE_TOOL_CALLING",
        ),
        (
            "agent section missing",
            {},
            # agent 섹션이 없어도 이전 config 의 native 모드가 새면 안 된다.
            "unset AGENT_NATIVE_TOOL_CALLING",
        ),
        (
            "lm_eval_mode missing",
            {},
            # LM_EVAL_MODE 는 사용자 셸 override 계약이 있으므로 미지정 시 건드리지 않는다.
            ("absent_prefix", "export LM_EVAL_MODE", "unset LM_EVAL_MODE"),
        ),
        (
            "kreta_setting missing",
            {},
            # KRETA_SETTING=direct ./run_full_eval.sh 같은 운영 override 를 보존한다.
            ("absent_prefix", "export KRETA_SETTING", "unset KRETA_SETTING"),
        ),
        (
            "lm_eval_mode completions",
            {"lm_eval_mode": "completions"},
            # yaml 이 명시한 모델별 harness 모드는 기존처럼 export 한다.
            "export LM_EVAL_MODE=completions",
        ),
        (
            "serving missing",
            {},
            # SERVING_* 는 config 간 서빙 제약 누수를 막기 위해 기존 unset 규칙을 유지한다.
            [
                "unset SERVING_UNSUPPORTED_SAMPLING_PARAMS",
                "unset SERVING_MAX_OUTPUT_TOKENS",
                "unset SERVING_FORCE_SKIP_SPECIAL_TOKENS",
            ],
        ),
    ]

    failures = []
    for name, cfg, expected in cases:
        lines = capture_emit_shell(module, cfg)
        if isinstance(expected, tuple) and expected[0] == "absent_prefix":
            for prefix in expected[1:]:
                try:
                    assert_absent_prefix(lines, prefix)
                except AssertionError as exc:
                    failures.append(f"{name}: {exc}")
            continue

        expected_lines = expected if isinstance(expected, list) else [expected]
        for expected_line in expected_lines:
            try:
                assert_contains(lines, expected_line)
            except AssertionError as exc:
                failures.append(f"{name}: {exc}")

    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"OK {len(cases)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
