from uuid import UUID

from django.db.models import Count, QuerySet

from users.models import User

from .models import Conversation, Message


def conversations_for(user: User) -> QuerySet[Conversation]:
    return Conversation.objects.filter(user=user).annotate(message_count=Count('messages'))


def conversation_for(user: User, conversation_uuid: UUID) -> Conversation | None:
    return Conversation.objects.filter(user=user, uuid=conversation_uuid).first()


def messages_for(conversation: Conversation, exclude_id: int | None = None) -> QuerySet[Message]:
    messages = Message.objects.filter(conversation=conversation)
    if exclude_id is not None:
        messages = messages.exclude(id=exclude_id)
    return messages.order_by('created_at')
