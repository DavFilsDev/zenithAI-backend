from collections.abc import Iterator, Sequence

from .base import ChatMessage, Provider
from .errors import LLMUnavailableError


class FallbackProvider:
    def __init__(self, primary: Provider, fallback: Provider) -> None:
        self.primary = primary
        self.fallback = fallback

    def generate(self, message: str, history: Sequence[ChatMessage]) -> str:
        try:
            return self.primary.generate(message, history)
        except LLMUnavailableError:
            return self.fallback.generate(message, history)

    def stream(self, message: str, history: Sequence[ChatMessage]) -> Iterator[str]:
        try:
            yield from self.primary.stream(message, history)
        except LLMUnavailableError:
            yield from self.fallback.stream(message, history)
