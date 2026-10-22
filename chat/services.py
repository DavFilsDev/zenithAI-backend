from collections.abc import Generator
from typing import Any

from .models import Conversation, Message
from .providers import ChatMessage, Provider
from .providers.factory import build_provider
from .selectors import messages_for

provider: Provider = build_provider()


def _history_for(conversation: Conversation, exclude_message_id: int) -> list[ChatMessage]:
    return [
        {'role': msg.role, 'content': msg.content}
        for msg in messages_for(conversation, exclude_id=exclude_message_id)
    ]


def generate_assistant_reply(conversation: Conversation, user_message: str) -> Message:
    user_msg = Message.objects.create(conversation=conversation, role='user', content=user_message)
    chat_history = _history_for(conversation, user_msg.id)
    ai_response = provider.generate(user_message, chat_history)
    return Message.objects.create(conversation=conversation, role='assistant', content=ai_response)


def stream_assistant_reply(
    conversation: Conversation,
    user_message: str,
    state: dict[str, Any] | None = None,
) -> Generator[str, None, None]:
    user_msg = Message.objects.create(conversation=conversation, role='user', content=user_message)
    chat_history = _history_for(conversation, user_msg.id)
    fragments = []
    for fragment in provider.stream(user_message, chat_history):
        fragments.append(fragment)
        yield fragment
    assistant = Message.objects.create(
        conversation=conversation, role='assistant', content=''.join(fragments)
    )
    if state is not None:
        state['assistant_message'] = assistant
