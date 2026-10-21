"""입력: wrapper 경로와 합성 키. 출력: 격리 실행 rc, judge 기록, 전체 argv.

HEAD 비교: KOFFVQA_TEST_SHELL=/absolute/path/to/HEAD-run_koffvqa.sh bash tests/run_pytests.sh -q shared/multimodal/tests/test_run_koffvqa_judge_key_argv.py
전달 경계만 검사한다. 실제 키 해석·요청·저장은 기존 judge 시험이 담당한다.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[3]
SYNTHETIC_KEY = "fixture-only-judge-credential"
JUDGE_MODULE = "shared.multimodal.benches.koffvqa_api_judge"

# 실제 Python 모듈은 실행하지 않는다. stdout은 SAFE_MODEL 응답에만 쓴다.
FAKE_PY = r'''
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
record = {"argv": sys.argv}
if args[:2] == ["-m", "shared.multimodal.benches.koffvqa_api_judge"]:
    record["key_matches"] = (
        os.environ.get("JUDGE_API_KEY") == os.environ.get("FIXTURE_EXPECTED_KEY")
    )
with Path(os.environ["FIXTURE_RECORD"]).open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(record) + "\n")

if args[:1] == ["-c"]:
    print("fixture_model")
elif args[:2] == ["-m", "shared.multimodal.benches.common"]:
    Path(args[args.index("--out") + 1]).write_text("{}\n", encoding="utf-8")
elif args[:2] == ["-m", "shared.multimodal.benches.koffvqa_run"]:
    dest = (Path(os.environ["MODEL_TEST_BASE"]) / "results" / "fixture_model"
            / os.environ["EVAL_TIMESTAMP"] / "vision/multimodal/koffvqa")
    (dest / "fixture_gen.xlsx").write_bytes(b"synthetic workbook")
elif args[:2] == ["-m", "shared.multimodal.benches.koffvqa_api_judge"]:
    assert Path(args[args.index("--predfile") + 1]).is_file()
else:
    raise SystemExit("unexpected fake Python invocation")
'''


def run_isolated(shell_path, tmp_path, key):
    """셸을 임시 트리로 복사해 실행하고 (rc, judge 기록 목록, 전체 argv)를 반환한다."""
    base = tmp_path.resolve()
    assert not base.is_relative_to(REPO), "fixture must stay outside the repository"
    script_dir = base / "shared/multimodal"
    (script_dir / "benches").mkdir(parents=True)
    script = script_dir / "run_koffvqa.sh"
    shutil.copyfile(shell_path, script)
    fake_py = base / "fake_python"
    fake_py.write_text(f"#!{sys.executable}\n" + FAKE_PY, encoding="utf-8")
    fake_py.chmod(0o755)
    record_path = base / "calls.jsonl"
    record_path.write_text("", encoding="utf-8")
    env = {
        "PATH": os.defpath,
        "PY": str(fake_py),
        "PYTHONDONTWRITEBYTECODE": "1",
        "MODEL_TEST_BASE": str(base),
        "EVAL_TIMESTAMP": "fixture-session",
        "FIXTURE_RECORD": str(record_path),
        "API_JUDGE": "1",
        "JUDGE_MODEL": "fixture-judge",
        "JUDGE_BASE_URL": "http://unused.invalid/v1",
    }
    if key is not None:
        env["JUDGE_API_KEY"] = key
        env["FIXTURE_EXPECTED_KEY"] = key
    command = ["/bin/bash", str(script), "fixture-model", "http://unused.invalid/v1"]
    result = subprocess.run(
        command, cwd=base, env=env, text=True, capture_output=True,
        check=False, timeout=30,
    )
    records = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]
    judges = [record for record in records if record["argv"][1:3] == ["-m", JUDGE_MODULE]]
    return result.returncode, judges, [command, *(record["argv"] for record in records)]


@pytest.fixture
def shell_path():
    return Path(os.environ.get("KOFFVQA_TEST_SHELL", REPO / "shared/multimodal/run_koffvqa.sh"))


@pytest.fixture
def keyed_run(shell_path, tmp_path):
    result = run_isolated(shell_path, tmp_path, SYNTHETIC_KEY)
    rc, judges, argv = result
    # 준비 실패나 judge 미도달을 키 전달 결함의 재현으로 세지 않는다.
    assert rc == 0, (rc, judges, argv)
    assert len(judges) == 1, judges
    return result


def test_key_value_is_absent_from_all_argv(keyed_run):
    _, _, calls = keyed_run
    assert not any(SYNTHETIC_KEY in argument for argv in calls for argument in argv)


def test_judge_receives_environment_variable_name(keyed_run):
    _, judges, _ = keyed_run
    argv = judges[0]["argv"]
    assert any(argv[i:i + 2] == ["--judge-api-key-env", "JUDGE_API_KEY"]
               for i in range(len(argv) - 1))
    assert "--judge-api-key" not in argv


def test_judge_inherits_same_key_value(keyed_run):
    _, judges, _ = keyed_run
    assert judges[0]["key_matches"] is True


@pytest.mark.parametrize("key", [None, ""], ids=["unset", "empty"])
def test_empty_or_unset_key_omits_both_options(shell_path, tmp_path, key):
    rc, judges, argv = run_isolated(shell_path, tmp_path, key)
    assert rc == 0, (rc, judges, argv)
    assert len(judges) == 1, judges
    assert "--judge-api-key" not in judges[0]["argv"]
    assert "--judge-api-key-env" not in judges[0]["argv"]
