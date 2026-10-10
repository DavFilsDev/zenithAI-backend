from typing import Iterator, Mapping, Optional, Sequence

import logging

from django.conf import settings
from openai import OpenAI

from .base import ChatMessage
from .errors import LLMUnavailableError

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider:
    """Groq implementation of the Provider protocol on the OpenAI-compatible endpoint.
    The client is built lazily so the API key is read from the settings at first use."""

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
            self.client = OpenAI(
                api_key=self.api_key if self.api_key is not None else settings.LLM_API_KEY,
                base_url=GROQ_BASE_URL,
            )
        return self.client

    def _messages(self, message: str, history: Sequence[ChatMessage]):
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(
            {"role": item["role"], "content": item["content"]} for item in history
        )
        messages.append({"role": "user", "content": message})
        return messages

    def generate(self, message: str, history: Sequence[ChatMessage]) -> str:
        try:
            response = self._client().chat.completions.create(
                model=self.model_name,
                messages=self._messages(message, history),
                temperature=self.config.get("temperature", 0.7),
                max_tokens=self.config.get("max_output_tokens", 2048),
                top_p=self.config.get("top_p", 0.95),
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise LLMUnavailableError(
                "The AI service is temporarily unavailable. Please try again later."
            )

    def stream(self, message: str, history: Sequence[ChatMessage]) -> Iterator[str]:
        try:
            stream = self._client().chat.completions.create(
                model=self.model_name,
                messages=self._messages(message, history),
                temperature=self.config.get("temperature", 0.7),
                max_tokens=self.config.get("max_output_tokens", 2048),
                top_p=self.config.get("top_p", 0.95),
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise LLMUnavailableError(
                "The AI service is temporarily unavailable. Please try again later."
            )