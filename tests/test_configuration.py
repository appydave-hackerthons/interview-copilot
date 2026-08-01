from pathlib import Path

import pytest
from pydantic import ValidationError

from interview_copilot.configuration import (
    ConfigurationYamlError,
    DEFAULT_PRESET_PATH,
    configuration_to_yaml,
    get_default_configuration,
    load_configuration_yaml,
)
from interview_copilot.models import InterviewConfiguration


def test_canonical_preset_validates_and_round_trips() -> None:
    configuration = get_default_configuration()

    assert configuration.schema_version == 1
    assert configuration.template.name == "Digital nomad frictions"
    assert "desired outcome" in configuration.copilot.task_prompt
    assert "expectation gap" in configuration.copilot.task_prompt
    assert any("progressive why probes" in item for item in configuration.template.interviewer_guidance)
    assert configuration.runtime.model.startswith("openai/")
    assert load_configuration_yaml(configuration_to_yaml(configuration)) == configuration
    assert DEFAULT_PRESET_PATH.is_file()


def test_invalid_yaml_reports_line_and_column() -> None:
    with pytest.raises(ConfigurationYamlError, match=r"line \d+, column \d+"):
        load_configuration_yaml("schema_version: 1\ntemplate: [broken\n")


def test_unknown_configuration_keys_are_rejected() -> None:
    payload = get_default_configuration().model_dump()
    payload["mystery"] = True

    with pytest.raises(ValidationError) as error:
        InterviewConfiguration.model_validate(payload)

    assert error.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("runtime", "model"), "gpt-5", "provider/model"),
        (("runtime", "archive_root"), "../private", "inside data"),
    ],
)
def test_invalid_relationships_and_runtime_values(
    path: tuple[str, str], value: object, message: str
) -> None:
    payload = get_default_configuration().model_dump()
    payload[path[0]][path[1]] = value

    with pytest.raises(ValidationError, match=message):
        InterviewConfiguration.model_validate(payload)


def test_audio_overlap_must_be_shorter_than_segment() -> None:
    payload = get_default_configuration().model_dump()
    payload["audio"]["segment_ms"] = 2_000
    payload["audio"]["overlap_ms"] = 2_000

    with pytest.raises(ValidationError, match="overlap_ms must be less than segment_ms"):
        InterviewConfiguration.model_validate(payload)


def test_at_least_one_lens_must_remain_enabled() -> None:
    payload = get_default_configuration().model_dump()
    payload["copilot"]["lenses"] = {key: False for key in payload["copilot"]["lenses"]}

    with pytest.raises(ValidationError, match="At least one specialist lens"):
        InterviewConfiguration.model_validate(payload)
