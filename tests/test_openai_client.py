from types import SimpleNamespace
from unittest.mock import patch

import pytest
from openai import OpenAIError

from bookfactory.adapters.openai_client import OpenAIClient
from bookfactory.config.settings import Settings
from bookfactory.core.llm_client import EmptyLLMResponseError, LLMRequestError


def _settings(model: str = "gpt-4.1-mini") -> Settings:
    return Settings(openai_api_key="test-key", openai_model=model)


def test_sends_responses_request_and_returns_plain_text() -> None:
    with patch("bookfactory.adapters.openai_client.OpenAI") as sdk:
        sdk.return_value.responses.create.return_value = SimpleNamespace(
            output_text="Generated text"
        )
        client = OpenAIClient(_settings("configured-model"))

        output = client.generate("Follow these instructions", "User content")

    sdk.assert_called_once_with(api_key="test-key")
    sdk.return_value.responses.create.assert_called_once_with(
        model="configured-model",
        instructions="Follow these instructions",
        input="User content",
    )
    assert output == "Generated text"


def test_wraps_official_sdk_errors() -> None:
    with patch("bookfactory.adapters.openai_client.OpenAI") as sdk:
        sdk.return_value.responses.create.side_effect = OpenAIError("request failed")
        client = OpenAIClient(_settings())

        with pytest.raises(LLMRequestError, match="OpenAI request failed"):
            client.generate("Instructions", "Input")


def test_rejects_empty_model_output() -> None:
    with patch("bookfactory.adapters.openai_client.OpenAI") as sdk:
        sdk.return_value.responses.create.return_value = SimpleNamespace(
            output_text="  "
        )
        client = OpenAIClient(_settings())

        with pytest.raises(EmptyLLMResponseError, match="empty response"):
            client.generate("Instructions", "Input")

