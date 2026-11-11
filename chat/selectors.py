from django.db.models import Count

from .models import Conversation, Message


def conversations_for(user):
    return Conversation.objects.filter(user=user).annotate(message_count=Count('messages'))


def conversation_for(user, conversation_uuid):
    return Conversation.objects.filter(user=user, uuid=conversation_uuid).first()


def messages_for(conversation, exclude_id=None):
    messages = Message.objects.filter(conversation=conversation)
    if exclude_id is not None:
        messages = messages.exclude(id=exclude_id)
    return messages.order_by('created_at')
