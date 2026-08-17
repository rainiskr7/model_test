#!/usr/bin/env python3
"""load_model_config.py 단독 회귀 테스트."""
import contextlib
import importlib.util
import io
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "load_model_config.py"
OVERRIDE_KEYS = ("BASE_URL_CHAT_OVERRIDE", "BASE_URL_V1_OVERRIDE")


def load_module():
    spec = importlib.util.spec_from_file_location("load_model_config", LOADER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def endpoint_override_env(values):
    saved = {key: os.environ[key] for key in OVERRIDE_KEYS if key in os.environ}
    for key in OVERRIDE_KEYS:
        os.environ.pop(key, None)
    os.environ.update(values)
    try:
        yield
    finally:
        for key in OVERRIDE_KEYS:
            os.environ.pop(key, None)
        os.environ.update(saved)


def test_config(extra_cfg):
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
    return cfg


def capture_emit_shell(module, extra_cfg):
    cfg = test_config(extra_cfg)

    stdout = io.StringIO()
    with endpoint_override_env({}), contextlib.redirect_stdout(stdout):
        module.emit_shell(cfg)
    return stdout.getvalue().splitlines()


def capture_endpoint_override(module, overrides):
    stdout = io.StringIO()
    stderr = io.StringIO()
    error = None
    with (
        endpoint_override_env(overrides),
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
    ):
        try:
            module.emit_shell(test_config({}))
        except SystemExit as exc:
            error = str(exc)
    return stdout.getvalue().splitlines(), stderr.getvalue(), error


def assert_contains(lines, expected):
    if expected not in lines:
        raise AssertionError(f"{expected!r} not in output: {lines!r}")


def assert_absent_prefix(lines, prefix):
    matches = [line for line in lines if line.startswith(prefix)]
    if matches:
        raise AssertionError(f"{prefix!r} output should be absent, got: {matches!r}")


def load_fixture(module, cfg):
    """임시 models 디렉터리의 YAML을 실제 load() 경로로 검증한다."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "configs"
        models_dir = config_dir / "models"
        models_dir.mkdir(parents=True)
        (models_dir / "fixture.yaml").write_text(
            module.yaml.safe_dump(cfg, allow_unicode=True),
            encoding="utf-8",
        )
        previous_file = module.__file__
        module.__file__ = str(config_dir / "load_model_config.py")
        try:
            try:
                return module.load("fixture"), None
            except SystemExit as exc:
                return None, str(exc)
        finally:
            module.__file__ = previous_file


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
            "sampling missing",
            {},
            # thinking 트리는 sampling 미지정 시 Qwen 권장 기본값을 모두 export 한다.
            [
                "export THINK_TEMPERATURE=0.6",
                "export THINK_TOP_P=0.95",
                "export THINK_TOP_K=20",
                "export THINK_MAX_TOKENS=8192",
                "export THINK_SEED=42",
                "export THINK_TIMEOUT=600",
            ],
        ),
        (
            "sampling explicit",
            {
                "sampling": {
                    "temperature": 0.2,
                    "top_p": 0.8,
                    "top_k": 10,
                    "max_tokens": 4096,
                    "seed": 7,
                    "timeout": 300,
                }
            },
            # thinking 모델별 sampling override가 여섯 THINK_* export에 반영돼야 한다.
            [
                "export THINK_TEMPERATURE=0.2",
                "export THINK_TOP_P=0.8",
                "export THINK_TOP_K=10",
                "export THINK_MAX_TOKENS=4096",
                "export THINK_SEED=7",
                "export THINK_TIMEOUT=300",
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

    endpoint_cases = 3
    yaml_chat = "export BASE_URL_CHAT=http://127.0.0.1:18023/v1/chat/completions"
    yaml_v1 = "export BASE_URL_V1=http://127.0.0.1:18023/v1"

    lines, stderr, error = capture_endpoint_override(module, {})
    if lines.count(yaml_chat) != 1 or lines.count(yaml_v1) != 1:
        failures.append(f"endpoint overrides absent: YAML endpoints changed: {lines!r}")
    if stderr or error is not None:
        failures.append(
            f"endpoint overrides absent: unexpected stderr/error: {stderr!r}, {error!r}"
        )

    override_chat = "http://host-b:28023/v1/chat/completions"
    override_v1 = "http://host-b:28023/v1"
    lines, stderr, error = capture_endpoint_override(
        module,
        {
            "BASE_URL_CHAT_OVERRIDE": override_chat,
            "BASE_URL_V1_OVERRIDE": override_v1,
        },
    )
    chat_exports = [line for line in lines if line.startswith("export BASE_URL_CHAT=")]
    v1_exports = [line for line in lines if line.startswith("export BASE_URL_V1=")]
    if chat_exports != [yaml_chat, f"export BASE_URL_CHAT={override_chat}"]:
        failures.append(f"both endpoint overrides: unexpected chat exports: {chat_exports!r}")
    if v1_exports != [yaml_v1, f"export BASE_URL_V1={override_v1}"]:
        failures.append(f"both endpoint overrides: unexpected v1 exports: {v1_exports!r}")
    expected_notice = (
        f"[config] endpoint override: BASE_URL_CHAT={override_chat} "
        f"BASE_URL_V1={override_v1}\n"
    )
    if stderr != expected_notice or error is not None:
        failures.append(f"both endpoint overrides: stderr/error: {stderr!r}, {error!r}")

    lines, stderr, error = capture_endpoint_override(
        module, {"BASE_URL_CHAT_OVERRIDE": override_chat}
    )
    expected_error = (
        "[config] ERROR: BASE_URL_CHAT_OVERRIDE and BASE_URL_V1_OVERRIDE "
        "must be set together"
    )
    if lines or stderr or error != expected_error:
        failures.append(
            f"one endpoint override: output/error: {lines!r}, {stderr!r}, {error!r}"
        )

    validation_cases = 3
    _, error = load_fixture(
        module,
        test_config({"agent": {}}),
    )
    expected_fragment = "agent.native_tool_calling을 true 또는 false로 명시"
    if error is None or expected_fragment not in error:
        failures.append(f"agent track without native decision loaded: {error!r}")

    loaded, error = load_fixture(
        module,
        test_config({"agent": {"native_tool_calling": False}}),
    )
    if error is not None or loaded["agent"]["native_tool_calling"] is not False:
        failures.append(f"explicit native_tool_calling false did not load: {error!r}")

    real_configs = sorted((ROOT / "models").glob("*.yaml"))
    real_failures = []
    for path in real_configs:
        try:
            module.load(path.name)
        except SystemExit as exc:
            real_failures.append(f"{path.name}: {exc}")
    if not real_configs:
        failures.append("no real configs found")
    if real_failures:
        failures.append(f"real configs failed to load: {real_failures!r}")

    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"OK {len(cases) + endpoint_cases + validation_cases} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
