"""4a lane timeout pairs against real validators; no runners/data/server access."""

import pytest

from shared.functionchat.runner import run_functionchat
from shared.taubench.runner import run_taubench


@pytest.mark.parametrize("runner", [run_functionchat, run_taubench])
def test_full_lane_default_timeouts_are_valid(runner):
    args = runner.parse_args(["--model", "fixture/model", "--request-timeout", "300",
                              "--task-timeout", "900"])
    runner._validate_args(args)


@pytest.mark.parametrize("runner", [run_functionchat, run_taubench])
def test_full_lane_request_without_longer_task_is_rejected(runner):
    args = runner.parse_args(["--model", "fixture/model", "--request-timeout", "300",
                              "--task-timeout", "120"])
    with pytest.raises(ValueError, match="task timeout must be greater than request timeout"):
        runner._validate_args(args)
