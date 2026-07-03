from __future__ import annotations

from openai import OpenAI, OpenAIError

from bookfactory.config.settings import Settings
from bookfactory.core.llm_client import EmptyLLMResponseError, LLMRequestError


class OpenAIClient:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.openai_model
        self._client = OpenAI(api_key=settings.openai_api_key)

    def generate(self, instructions: str, user_input: str) -> str:
        try:
            response = self._client.responses.create(
                model=self._model,
                instructions=instructions,
                input=user_input,
            )
        except OpenAIError as error:
            raise LLMRequestError("OpenAI request failed") from error

        if not response.output_text.strip():
            raise EmptyLLMResponseError("OpenAI returned an empty response")
        return response.output_text

