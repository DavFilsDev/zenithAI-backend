from types import SimpleNamespace
from typing import Sequence
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from .base import ChatMessage, Provider
from .errors import LLMUnavailableError
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