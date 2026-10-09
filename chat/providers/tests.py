from typing import Sequence

from django.test import SimpleTestCase

from .base import ChatMessage, Provider


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