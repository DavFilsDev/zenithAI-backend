from rest_framework import serializers
from .models import Conversation, Message
from drf_spectacular.utils import extend_schema_field

class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer for Message model.
    
    Represents a single message in a conversation.
    Messages can be from 'user', 'assistant', or 'system'.
    """
    class Meta:
        model = Message
        fields = ('id', 'role', 'content', 'created_at')
        read_only_fields = ('id', 'created_at')
        
    @extend_schema_field(
        {
            'type': 'string',
            'enum': ['user', 'assistant', 'system'],
            'description': 'Role of the message sender'
        }
    )
    def get_role(self, obj):
        return obj.role

class ConversationSerializer(serializers.ModelSerializer):
    """
    Serializer for Conversation model.
    
    Includes nested messages and computed message_count field.
    """
    messages = MessageSerializer(many=True, read_only=True)
    message_count = serializers.IntegerField(source='messages.count', read_only=True)
    
    class Meta:
        model = Conversation
        fields = ('id', 'title', 'created_at', 'updated_at', 'messages', 'message_count')
        read_only_fields = ('id', 'created_at', 'updated_at')
        
    @extend_schema_field(
        {
            'type': 'integer',
            'description': 'Total number of messages in this conversation'
        }
    )
    def get_message_count(self, obj):
        return obj.messages.count()