from .models import Message
from .providers import LLMUnavailableError, Provider
from .providers.factory import build_provider


provider: Provider = build_provider()


def _history_for(conversation, exclude_message_id):
    messages = Message.objects.filter(conversation=conversation).order_by('created_at')
    return [
        {'role': msg.role, 'content': msg.content}
        for msg in messages
        if msg.id != exclude_message_id
    ]


def generate_assistant_reply(conversation, user_message):
    user_msg = Message.objects.create(conversation=conversation, role='user', content=user_message)
    chat_history = _history_for(conversation, user_msg.id)
    ai_response = provider.generate(user_message, chat_history)
    return Message.objects.create(conversation=conversation, role='assistant', content=ai_response)


def stream_assistant_reply(conversation, user_message, state=None):
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