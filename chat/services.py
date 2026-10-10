from django.conf import settings

from .models import Message
from .providers import LLMUnavailableError, Provider
from .providers.gemini import GeminiProvider


provider: Provider = GeminiProvider(
    model=settings.GEMINI_MODEL,
    config=settings.GEMINI_CONFIG,
    system_prompt=settings.LLM_SYSTEM_PROMPT,
)


def generate_assistant_reply(conversation, user_message):
    user_msg = Message.objects.create(conversation=conversation, role='user', content=user_message)
    messages = Message.objects.filter(conversation=conversation).order_by('created_at')
    chat_history = [{'role': msg.role, 'content': msg.content} for msg in messages if msg.id != user_msg.id]
    ai_response = provider.generate(user_message, chat_history)
    return Message.objects.create(conversation=conversation, role='assistant', content=ai_response)