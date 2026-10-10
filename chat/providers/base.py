from typing import Iterator, Protocol, Sequence, TypedDict, runtime_checkable


class ChatMessage(TypedDict):
    role: str
    content: str


@runtime_checkable
class Provider(Protocol):
    """The single LLM contract. No provider SDK is ever imported by this module,
    so a fake implementing the protocol can replace a real provider in tests."""

    def generate(self, message: str, history: Sequence[ChatMessage]) -> str:
        """Return the complete text answer for a user message in a conversation history."""
        ...

    def stream(self, message: str, history: Sequence[ChatMessage]) -> Iterator[str]:
        """Yield growing text fragments of the answer; the last fragment completes it."""
        ...