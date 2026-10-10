from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import Provider
from .fallback import FallbackProvider
from .gemini import GeminiProvider
from .groq import GroqProvider

KNOWN_PROVIDERS = ('gemini', 'groq')


def _build(name, api_key, model):
    if name == 'gemini':
        return GeminiProvider(api_key=api_key, model=model)
    if name == 'groq':
        return GroqProvider(api_key=api_key, model=model)
    raise ImproperlyConfigured(
        f"Unknown LLM provider '{name}'. Supported providers: {', '.join(KNOWN_PROVIDERS)}."
    )


def build_provider():
    provider = _build(settings.LLM_PROVIDER or 'gemini', settings.LLM_API_KEY, settings.LLM_MODEL)
    if settings.LLM_FALLBACK_PROVIDER:
        fallback = _build(
            settings.LLM_FALLBACK_PROVIDER,
            settings.LLM_FALLBACK_API_KEY,
            settings.LLM_FALLBACK_MODEL,
        )
        provider = FallbackProvider(provider, fallback)
    return provider


def validate_config():
    if settings.LLM_PROVIDER not in KNOWN_PROVIDERS:
        _build(settings.LLM_PROVIDER, settings.LLM_API_KEY, settings.LLM_MODEL)
    if not settings.LLM_API_KEY:
        raise ImproperlyConfigured('LLM_API_KEY must be set when DEBUG is off.')
    if settings.LLM_FALLBACK_PROVIDER:
        if settings.LLM_FALLBACK_PROVIDER not in KNOWN_PROVIDERS:
            _build(
                settings.LLM_FALLBACK_PROVIDER,
                settings.LLM_FALLBACK_API_KEY,
                settings.LLM_FALLBACK_MODEL,
            )
        if not settings.LLM_FALLBACK_API_KEY:
            raise ImproperlyConfigured(
                'LLM_FALLBACK_API_KEY must be set when LLM_FALLBACK_PROVIDER is configured and DEBUG is off.'
            )