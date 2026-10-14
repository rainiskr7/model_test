"""Fresh runner imports while preserving shared modules and parent attributes."""

from contextlib import contextmanager, ExitStack
import importlib
import sys

import pytest

# Other tracks can import these shared fakes before this conftest is loaded.
if "shared.multimodal.tests._runner_fakes" not in sys.modules:
    pytest.register_assert_rewrite("shared.multimodal.tests._runner_fakes")


@contextmanager
def fresh_runner(name):
    """Restore only the target module cache and its parent attribute on exit."""
    parent_name, attribute = name.rsplit(".", 1)
    parent = importlib.import_module(parent_name)
    missing = object()
    previous_module = sys.modules.pop(name, missing)
    previous_attribute = vars(parent).pop(attribute, missing)
    try:
        yield importlib.import_module(name)
    finally:
        if previous_module is missing:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous_module
        if previous_attribute is missing:
            vars(parent).pop(attribute, None)
        else:
            setattr(parent, attribute, previous_attribute)


@pytest.fixture
def fresh_import():
    with ExitStack() as imports:
        yield lambda name: imports.enter_context(fresh_runner(name))
