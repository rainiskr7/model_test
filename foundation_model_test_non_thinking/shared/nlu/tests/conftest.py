"""Fresh NLU imports without disturbing sibling module caches."""

from contextlib import contextmanager
import importlib
import sys

import pytest


@contextmanager
def fresh_runner():
    """Restore both the target cache entry and its parent attribute on exit."""
    name = "shared.nlu.nlu_gpustack"
    parent = importlib.import_module("shared.nlu")
    missing = object()
    previous_module = sys.modules.pop(name, missing)
    previous_attribute = vars(parent).pop("nlu_gpustack", missing)
    try:
        yield importlib.import_module(name)
    finally:
        if previous_module is missing:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous_module
        if previous_attribute is missing:
            vars(parent).pop("nlu_gpustack", None)
        else:
            parent.nlu_gpustack = previous_attribute


@pytest.fixture
def runner():
    with fresh_runner() as module:
        yield module
