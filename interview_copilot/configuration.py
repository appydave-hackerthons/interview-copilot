"""Canonical interview configuration loading and YAML serialization."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from interview_copilot.models import InterviewConfiguration

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PRESET_PATH = ROOT / "config" / "presets" / "digital-nomad-discovery.yaml"


class ConfigurationYamlError(ValueError):
    """A YAML parsing error with a useful source location."""


def load_configuration_yaml(source: str) -> InterviewConfiguration:
    """Parse and validate one complete YAML configuration."""

    try:
        payload: Any = yaml.safe_load(source)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        problem = getattr(exc, "problem", None) or str(exc)
        raise ConfigurationYamlError(f"Invalid YAML{location}: {problem}") from exc
    if not isinstance(payload, dict):
        raise ConfigurationYamlError("Configuration YAML must contain one mapping object")
    try:
        return InterviewConfiguration.model_validate(payload)
    except ValidationError:
        raise


@lru_cache(maxsize=1)
def get_default_configuration() -> InterviewConfiguration:
    """Load the canonical preset, the only source of application defaults."""

    return load_configuration_yaml(DEFAULT_PRESET_PATH.read_text(encoding="utf-8"))


def configuration_to_yaml(configuration: InterviewConfiguration) -> str:
    """Serialize a complete configuration in stable, human-readable order."""

    return yaml.safe_dump(
        configuration.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
        width=88,
    )


def resolve_archive_root(value: str) -> Path:
    """Resolve an already-validated local archive root inside the repository."""

    resolved = (ROOT / value).resolve()
    data_root = (ROOT / "data").resolve()
    if not resolved.is_relative_to(data_root):
        raise ValueError("Archive root must resolve inside the project's data directory")
    return resolved
