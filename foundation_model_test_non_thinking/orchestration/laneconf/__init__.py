"""Shared literal model-conf parser for lanes and serving smoke."""
from orchestration.laneconf.parser import parse
from orchestration.laneconf.resolver import resolve
from orchestration.laneconf.schema import ConfigError

__all__ = ["ConfigError", "parse", "resolve"]
