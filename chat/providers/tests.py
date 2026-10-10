from types import SimpleNamespace
from typing import Sequence
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.test import SimpleTestCase, override_settings

from .base import ChatMessage, Provider
from .errors import LLMUnavailableError
from .factory import build_provider, validate_config
from .fallback import FallbackProvider
from .gemini import GeminiProvider
from .groq import GROQ_BASE_URL, GroqProvider


class FakeProvider:
    def generate(self, message: str, history: Sequence[ChatMessage]) -> str:
        return f"answer for {message}"

    def stream(self, message: str, history: Sequence[ChatMessage]):  # noqa: ANN401
        yield "frag"
        yield "ment"


class ProviderInterfaceTests(SimpleTestCase):
    def test_a_fake_with_the_expected_shape_satisfies_the_protocol(self):
        provider = FakeProvider()
        self.assertIsInstance(provider, Provider)

    def test_generate_and_stream_are_called_through_the_protocol(self):
        provider = FakeProvider()
        self.assertEqual(provider.generate("hi", []), "answer for hi")
        self.assertEqual("".join(provider.stream("hi", [])), "fragment")


class FakeCompletions:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeChat:
    def __init__(self, completions):
        self.completions = completions


class FakeClient:
    def __init__(self, completions):
        self.chat = FakeChat(completions)


class GroqProviderTests(SimpleTestCase):
    def test_groq_provider_satisfies_the_protocol(self):
        provider = GroqProvider()
        self.assertIsInstance(provider, Provider)

    @patch('chat.providers.groq.OpenAI')
    def test_client_is_built_lazily_on_the_openai_compatible_endpoint(self, mock_openai):
        provider = GroqProvider(api_key='test-key')
        provider._client()
        mock_openai.assert_called_once_with(
            api_key='test-key',
            base_url=GROQ_BASE_URL,
        )

    @patch('chat.providers.groq.OpenAI')
    def test_generate_sends_system_prompt_and_history_with_client_roles(self, mock_openai):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='Hello back'))]
        )
        completions = FakeCompletions(response)
        mock_openai.return_value = FakeClient(completions)

        provider = GroqProvider(api_key='test-key')
        result = provider.generate(
            'Is this on?',
            [{'role': 'user', 'content': 'hi'}, {'role': 'assistant', 'content': 'hey'}],
        )

        self.assertEqual(result, 'Hello back')
        self.assertEqual(completions.calls[0]['model'], settings.LLM_MODEL)
        self.assertEqual(completions.calls[0]['messages'], [
            {'role': 'system', 'content': settings.LLM_SYSTEM_PROMPT},
            {'role': 'user', 'content': 'hi'},
            {'role': 'assistant', 'content': 'hey'},
            {'role': 'user', 'content': 'Is this on?'},
        ])

    @patch('chat.providers.groq.OpenAI')
    def test_stream_yields_delta_content(self, mock_openai):
        chunks = [
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='frag'))]),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='ment'))]),
        ]
        completions = FakeCompletions(chunks)
        mock_openai.return_value = FakeClient(completions)

        provider = GroqProvider(api_key='test-key')
        self.assertEqual(''.join(provider.stream('hi', [])), 'fragment')
        self.assertEqual(completions.calls[0]['stream'], True)

    @patch('chat.providers.groq.OpenAI')
    def test_provider_failure_raises_llm_unavailable(self, mock_openai):
        completions = FakeCompletions(None)

        def boom(**kwargs):
            raise RuntimeError('down')

        completions.create = boom
        mock_openai.return_value = FakeClient(completions)

        provider = GroqProvider(api_key='test-key')
        with self.assertRaises(LLMUnavailableError):
            provider.generate('hi', [])

    @patch('chat.providers.groq.OpenAI')
    def test_empty_api_key_still_builds_a_client_lazily(self, mock_openai):
        provider = GroqProvider()
        with override_settings(LLM_API_KEY=''):
            mock_openai.return_value = FakeClient(FakeCompletions(None))
            self.assertIsNotNone(provider._client())
        mock_openai.assert_called_once_with(api_key='', base_url=GROQ_BASE_URL)


class FailingProvider:
    def generate(self, message, history):
        raise LLMUnavailableError('down')

    def stream(self, message, history):
        raise LLMUnavailableError('down')
        yield


class FactoryTests(SimpleTestCase):
    @override_settings(LLM_PROVIDER='gemini', LLM_FALLBACK_PROVIDER='')
    def test_build_provider_returns_the_configured_provider(self):
        provider = build_provider()
        self.assertIsInstance(provider, GeminiProvider)

    @override_settings(
        LLM_PROVIDER='gemini',
        LLM_MODEL='gemini-2.5-flash',
        LLM_FALLBACK_PROVIDER='groq',
    )
    def test_build_provider_wraps_in_a_fallback_when_configured(self):
        provider = build_provider()
        self.assertIsInstance(provider, FallbackProvider)
        self.assertIsInstance(provider.primary, GeminiProvider)
        self.assertIsInstance(provider.fallback, GroqProvider)

    def test_validate_config_rejects_unknown_providers(self):
        with override_settings(LLM_PROVIDER='claude', LLM_API_KEY='x'):
            with self.assertRaises(ImproperlyConfigured):
                validate_config()

    def test_validate_config_rejects_a_missing_key(self):
        with override_settings(LLM_PROVIDER='gemini', LLM_API_KEY=''):
            with self.assertRaisesMessage(ImproperlyConfigured, 'LLM_API_KEY'):
                validate_config()

    def test_validate_config_rejects_a_missing_fallback_key(self):
        with override_settings(
            LLM_PROVIDER='gemini',
            LLM_API_KEY='x',
            LLM_FALLBACK_PROVIDER='groq',
            LLM_FALLBACK_API_KEY='',
        ):
            with self.assertRaisesMessage(ImproperlyConfigured, 'LLM_FALLBACK_API_KEY'):
                validate_config()

    def test_validate_config_accepts_a_complete_configuration(self):
        with override_settings(
            LLM_PROVIDER='groq',
            LLM_API_KEY='x',
            LLM_FALLBACK_PROVIDER='gemini',
            LLM_FALLBACK_API_KEY='y',
        ):
            validate_config()


class FallbackProviderTests(SimpleTestCase):
    def test_generate_falls_back_when_the_primary_is_unavailable(self):
        primary = FailingProvider()
        fallback = FakeProvider()
        provider = FallbackProvider(primary, fallback)
        self.assertEqual(provider.generate('hi', []), 'answer for hi')

    def test_generate_does_not_call_the_fallback_on_success(self):
        primary = FakeProvider()
        fallback = FailingProvider()
        provider = FallbackProvider(primary, fallback)
        self.assertEqual(provider.generate('hi', []), 'answer for hi')

    def test_stream_falls_back_when_the_primary_is_unavailable(self):
        primary = FailingProvider()
        fallback = FakeProvider()
        provider = FallbackProvider(primary, fallback)
        self.assertEqual(''.join(provider.stream('hi', [])), 'fragment')