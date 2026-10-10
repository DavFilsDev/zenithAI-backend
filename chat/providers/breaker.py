from typing import Iterator, Sequence

from django.core.cache import cache

from .base import ChatMessage
from .errors import LLMUnavailableError


class CircuitBreaker:
    """Trip after repeated provider failures and stop calling until a cool-down passes.

    State lives in the cache so the cool-down expires on its own: once the
    ``open`` key expires the circuit lets a trial call through (half-open), and a
    failure of that trial reopens it immediately because the failure counter is
    kept until a success clears it.
    """

    failures_key = 'llm_breaker_failures'
    open_key = 'llm_breaker_open'

    def __init__(self, threshold, cooldown):
        self.threshold = threshold
        self.cooldown = cooldown

    def is_open(self):
        return bool(cache.get(self.open_key))

    def record_failure(self):
        try:
            failures = cache.incr(self.failures_key)
        except ValueError:
            cache.set(self.failures_key, 1)
            failures = 1
        if failures >= self.threshold:
            cache.set(self.open_key, True, timeout=self.cooldown)

    def record_success(self):
        cache.delete(self.failures_key)
        cache.delete(self.open_key)


class CircuitBreakerProvider:
    """Wrap a provider so that an open breaker fails fast with ``llm_unavailable``."""

    def __init__(self, provider, breaker):
        self.provider = provider
        self.breaker = breaker

    def generate(self, message: str, history: Sequence[ChatMessage]) -> str:
        if self.breaker.is_open():
            raise LLMUnavailableError()
        try:
            reply = self.provider.generate(message, history)
        except LLMUnavailableError:
            self.breaker.record_failure()
            raise
        self.breaker.record_success()
        return reply

    def stream(self, message: str, history: Sequence[ChatMessage]) -> Iterator[str]:
        if self.breaker.is_open():
            raise LLMUnavailableError()

        def chunks():
            try:
                yield from self.provider.stream(message, history)
            except LLMUnavailableError:
                self.breaker.record_failure()
                raise
            self.breaker.record_success()

        return chunks()
