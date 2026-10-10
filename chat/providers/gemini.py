from typing import Iterator, Optional, Sequence, Mapping

import logging

from django.conf import settings
from google import genai
from google.genai import types

from .base import ChatMessage, Provider
from .errors import provider_error
from .prompt import windowed_history

logger = logging.getLogger(__name__)


class GeminiProvider:
    """Gemini implementation of the Provider protocol. The client is built lazily so a
    missing or overridden API key is read from the settings at first use, not at import."""

    def __init__(
        self,
        model: Optional[str] = None,
        config: Optional[Mapping] = None,
        system_prompt: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.model_name = model or settings.LLM_MODEL
        self.config = dict(config or {})
        self.system_prompt = system_prompt or settings.LLM_SYSTEM_PROMPT
        self.api_key = api_key
        self.client = None

    def _client(self):
        if self.client is None:
            self.client = genai.Client(
                api_key=self.api_key if self.api_key is not None else settings.LLM_API_KEY
            )
        return self.client

    def _generation_config(self):
        return types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=self.config.get("temperature", 0.7),
            max_output_tokens=self.config.get("max_output_tokens", 2048),
            top_p=self.config.get("top_p", 0.95),
            top_k=self.config.get("top_k", 40),
        )

    def _build_prompt(self, message: str, history: Sequence[ChatMessage]) -> str:
        history = windowed_history(history)
        if not history:
            return message
        parts = [
            f"{'User' if item['role'] == 'user' else 'Assistant'}: {item['content']}"
            for item in history
        ]
        parts.append(f"User: {message}")
        return "\n".join(parts)

    def generate(self, message: str, history: Sequence[ChatMessage]) -> str:
        try:
            response = self._client().models.generate_content(
                model=self.model_name,
                contents=self._build_prompt(message, history),
                config=self._generation_config(),
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise provider_error(e)

    def stream(self, message: str, history: Sequence[ChatMessage]) -> Iterator[str]:
        try:
            stream = self._client().models.generate_content_stream(
                model=self.model_name,
                contents=self._build_prompt(message, history),
                config=self._generation_config(),
            )
            for chunk in stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise provider_error(e)