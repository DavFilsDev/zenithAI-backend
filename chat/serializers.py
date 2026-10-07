from rest_framework import serializers
from .models import Conversation, Message

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ('uuid', 'role', 'content', 'created_at')
        read_only_fields = ('uuid', 'created_at')

class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    message_count = serializers.IntegerField(source='messages.count', read_only=True)

    class Meta:
        model = Conversation
        fields = ('uuid', 'title', 'created_at', 'updated_at', 'messages', 'message_count')
        read_only_fields = ('uuid', 'created_at', 'updated_at')