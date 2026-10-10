import time
from types import SimpleNamespace
from typing import Sequence
from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.test import SimpleTestCase, override_settings

from .base import ChatMessage, Provider
from .breaker import CircuitBreaker, CircuitBreakerProvider
from .errors import LLMUnavailableError, SAFE_PROVIDER_MESSAGE, provider_error
from .factory import build_provider, validate_config
from .fallback import FallbackProvider
from .gemini import GeminiProvider
from .groq import GROQ_BASE_URL, GroqProvider
from .prompt import estimate_tokens, windowed_history


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
        self.assertIsInstance(provider, CircuitBreakerProvider)
        self.assertIsInstance(provider.provider, GeminiProvider)

    @override_settings(
        LLM_PROVIDER='gemini',
        LLM_MODEL='gemini-2.5-flash',
        LLM_FALLBACK_PROVIDER='groq',
    )
    def test_build_provider_wraps_in_a_fallback_when_configured(self):
        provider = build_provider()
        self.assertIsInstance(provider, CircuitBreakerProvider)
        self.assertIsInstance(provider.provider, FallbackProvider)
        self.assertIsInstance(provider.provider.primary, GeminiProvider)
        self.assertIsInstance(provider.provider.fallback, GroqProvider)

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


class CountingProvider:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def generate(self, message, history):
        self.calls += 1
        if self.fail:
            raise LLMUnavailableError('down')
        return 'ok'

    def stream(self, message, history):
        self.calls += 1
        if self.fail:
            raise LLMUnavailableError('down')
        yield 'ok'


class CircuitBreakerTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_opens_only_after_the_threshold(self):
        breaker = CircuitBreaker(threshold=3, cooldown=60)
        breaker.record_failure()
        breaker.record_failure()
        self.assertFalse(breaker.is_open())
        breaker.record_failure()
        self.assertTrue(breaker.is_open())

    def test_a_success_resets_the_failure_count(self):
        breaker = CircuitBreaker(threshold=2, cooldown=60)
        breaker.record_failure()
        breaker.record_success()
        breaker.record_failure()
        self.assertFalse(breaker.is_open())

    def test_closes_after_the_cooldown(self):
        breaker = CircuitBreaker(threshold=1, cooldown=0.05)
        breaker.record_failure()
        self.assertTrue(breaker.is_open())
        time.sleep(0.06)
        self.assertFalse(breaker.is_open())

    def test_a_failed_trial_reopens_the_circuit(self):
        breaker = CircuitBreaker(threshold=1, cooldown=0.05)
        breaker.record_failure()
        time.sleep(0.06)
        self.assertFalse(breaker.is_open())
        breaker.record_failure()
        self.assertTrue(breaker.is_open())


class CircuitBreakerProviderTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_failures_open_the_circuit_and_later_calls_fail_fast(self):
        inner = CountingProvider(fail=True)
        breaker = CircuitBreaker(threshold=2, cooldown=60)
        provider = CircuitBreakerProvider(inner, breaker)

        for _ in range(2):
            with self.assertRaises(LLMUnavailableError):
                provider.generate('hi', [])
        self.assertTrue(breaker.is_open())
        self.assertEqual(inner.calls, 2)

        with self.assertRaises(LLMUnavailableError) as context:
            provider.generate('hi', [])
        self.assertEqual(inner.calls, 2)
        self.assertEqual(str(context.exception), SAFE_PROVIDER_MESSAGE)

    def test_a_success_keeps_the_circuit_closed(self):
        inner = CountingProvider()
        breaker = CircuitBreaker(threshold=2, cooldown=60)
        provider = CircuitBreakerProvider(inner, breaker)

        self.assertEqual(provider.generate('hi', []), 'ok')
        self.assertFalse(breaker.is_open())

    def test_stream_failures_open_the_circuit_and_fail_fast(self):
        inner = CountingProvider(fail=True)
        breaker = CircuitBreaker(threshold=1, cooldown=60)
        provider = CircuitBreakerProvider(inner, breaker)

        with self.assertRaises(LLMUnavailableError):
            list(provider.stream('hi', []))
        self.assertTrue(breaker.is_open())
        self.assertEqual(inner.calls, 1)

        with self.assertRaises(LLMUnavailableError):
            provider.stream('hi', [])
        self.assertEqual(inner.calls, 1)

    def test_a_successful_stream_resets_the_circuit(self):
        inner = CountingProvider()
        breaker = CircuitBreaker(threshold=2, cooldown=60)
        breaker.record_failure()
        provider = CircuitBreakerProvider(inner, breaker)

        self.assertEqual(''.join(provider.stream('hi', [])), 'ok')
        breaker.record_failure()
        self.assertFalse(breaker.is_open())


class PromptBudgetTests(SimpleTestCase):
    def test_estimate_tokens_counts_roughly_four_chars_per_token(self):
        self.assertEqual(estimate_tokens('a' * 400), 100)
        self.assertEqual(estimate_tokens(''), 1)

    def test_window_keeps_all_history_within_the_budget(self):
        history = [
            {'role': 'user', 'content': 'a' * 200},
            {'role': 'assistant', 'content': 'b' * 200},
        ]
        with override_settings(LLM_PROMPT_BUDGET=4000):
            self.assertEqual(windowed_history(history), history)

    def test_window_drops_the_oldest_turns_first(self):
        history = [
            {'role': 'user', 'content': 'oldest ' * 2000},
            {'role': 'user', 'content': 'recent ' * 20},
            {'role': 'assistant', 'content': 'latest ' * 20},
        ]
        with override_settings(LLM_PROMPT_BUDGET=100):
            window = windowed_history(history)
        self.assertNotIn(history[0], window)
        self.assertEqual(window, history[1:])

    def test_window_size_stops_growing_with_history_length(self):
        history = [
            {'role': 'user', 'content': 'x' * 400} for _ in range(200)
        ]
        with override_settings(LLM_PROMPT_BUDGET=4000):
            window = windowed_history(history)
        self.assertLess(len(window), len(history))
        self.assertLessEqual(
            sum(estimate_tokens(item['content']) for item in window), 4000
        )

    def test_budget_is_read_from_settings(self):
        history = [{'role': 'user', 'content': 'a' * 100}]
        with override_settings(LLM_PROMPT_BUDGET=10):
            self.assertEqual(windowed_history(history), [])
        self.assertEqual(windowed_history(history), history)

    @patch('chat.providers.gemini.genai.Client')
    def test_gemini_prompt_uses_only_the_windowed_history(self, mock_client):
        given = SimpleNamespace()
        given.text = 'ok'
        mock_client.return_value.models.generate_content.return_value = given

        provider = GeminiProvider(api_key='x')
        history = [
            {'role': 'user', 'content': 'OLDEST ' * 4000},
            {'role': 'assistant', 'content': 'a' * 400},
            {'role': 'user', 'content': 'bbbb'},
        ]
        with override_settings(LLM_PROMPT_BUDGET=10):
            provider.generate('New', history)

        contents = mock_client.return_value.models.generate_content.call_args.kwargs['contents']
        self.assertNotIn('OLDEST', contents)
        self.assertIn('bbbb', contents)

    @patch('chat.providers.gemini.genai.Client')
    def test_gemini_prompt_size_is_bounded_even_for_a_huge_history(self, mock_client):
        given = SimpleNamespace()
        given.text = 'ok'
        mock_client.return_value.models.generate_content.return_value = given

        provider = GeminiProvider(api_key='x')
        history = [
            {'role': 'user', 'content': 'z' * 4000} for _ in range(50)
        ]
        with override_settings(LLM_PROMPT_BUDGET=4000):
            provider.generate('New', history)

        contents = mock_client.return_value.models.generate_content.call_args.kwargs['contents']
        self.assertLess(len(contents), 40000)

    @patch('chat.providers.groq.OpenAI')
    def test_groq_sends_only_the_windowed_history_with_order_preserved(self, mock_openai):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='ok'))]
        )
        completions = FakeCompletions(response)
        mock_openai.return_value = FakeClient(completions)

        provider = GroqProvider(api_key='x')
        history = [
            {'role': 'user', 'content': 'OLDEST ' * 4000},
            {'role': 'assistant', 'content': 'a' * 400},
            {'role': 'user', 'content': 'bbbb'},
        ]
        with override_settings(LLM_PROMPT_BUDGET=10):
            provider.generate('New', history)

        messages = completions.calls[0]['messages']
        self.assertEqual(
            [m['content'] for m in messages],
            [settings.LLM_SYSTEM_PROMPT, 'bbbb', 'New'],
        )


class ProviderRateLimited(Exception):
    def __init__(self, status_code=429, retry_after='7', raw='secret provider text'):
        self.status_code = status_code
        self.response = SimpleNamespace(headers={'Retry-After': retry_after})
        super().__init__(raw)


class ProviderErrorMappingTests(SimpleTestCase):
    def test_rate_limit_maps_to_llm_unavailable_with_retry_after(self):
        mapped = provider_error(ProviderRateLimited())
        self.assertIsInstance(mapped, LLMUnavailableError)
        self.assertEqual(mapped.retry_after, 7)
        self.assertEqual(str(mapped), SAFE_PROVIDER_MESSAGE)

    def test_raw_provider_text_never_reaches_the_message(self):
        mapped = provider_error(ProviderRateLimited(raw='key sk-secret is invalid'))
        self.assertNotIn('secret', str(mapped))

    def test_gemini_style_code_attribute_is_understood(self):
        exc = SimpleNamespace(code=429, response=SimpleNamespace(headers={'retry-after': '3'}))
        self.assertEqual(provider_error(exc).retry_after, 3)

    def test_non_rate_limit_has_no_retry_after(self):
        exc = SimpleNamespace(status_code=500, response=SimpleNamespace(headers={'Retry-After': '9'}))
        self.assertIsNone(provider_error(exc).retry_after)

    def test_error_without_a_response_has_no_retry_after(self):
        mapped = provider_error(RuntimeError('raw'))
        self.assertIsNone(mapped.retry_after)
        self.assertEqual(str(mapped), SAFE_PROVIDER_MESSAGE)

    @patch('chat.providers.gemini.genai.Client')
    def test_gemini_provider_propagates_retry_after(self, mock_client):
        mock_client.return_value.models.generate_content.side_effect = ProviderRateLimited(retry_after='12')
        provider = GeminiProvider(api_key='x')
        with self.assertRaises(LLMUnavailableError) as context:
            provider.generate('hi', [])
        self.assertEqual(context.exception.retry_after, 12)

    @patch('chat.providers.groq.OpenAI')
    def test_groq_provider_propagates_retry_after(self, mock_openai):
        completions = FakeCompletions(None)

        def boom(**kwargs):
            raise ProviderRateLimited(retry_after='5')

        completions.create = boom
        mock_openai.return_value = FakeClient(completions)

        provider = GroqProvider(api_key='x')
        with self.assertRaises(LLMUnavailableError) as context:
            provider.generate('hi', [])
        self.assertEqual(context.exception.retry_after, 5)