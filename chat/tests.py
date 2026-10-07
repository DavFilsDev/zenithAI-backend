from uuid import UUID

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer

User = get_user_model()


class MessagePayloadTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='chatter@example.com',
            username='chatter',
            password='Str0ng-Passw0rd!42',
        )
        self.conversation = Conversation.objects.create(
            user=self.user,
            title='Test chat',
        )
        self.message = Message.objects.create(
            conversation=self.conversation,
            role='assistant',
            content='Hello',
        )

    def test_message_serializer_has_no_token_count(self):
        payload = MessageSerializer(self.message).data
        self.assertNotIn('tokens', payload)
        self.assertEqual(payload['role'], 'assistant')

    def test_conversation_payload_messages_have_no_token_count(self):
        payload = ConversationSerializer(self.conversation).data
        message = next(item for item in payload['messages'])
        self.assertNotIn('tokens', message)
        self.assertEqual(message['content'], 'Hello')


class UuidPayloadTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='uuid-chatter@example.com',
            username='uuid-chatter',
            password='Str0ng-Passw0rd!42',
        )
        self.conversation = Conversation.objects.create(
            user=self.user,
            title='UUID chat',
        )
        self.message = Message.objects.create(
            conversation=self.conversation,
            role='assistant',
            content='Hello',
        )

    def test_payload_uses_uuid_instead_of_integer_id(self):
        conversation_payload = ConversationSerializer(self.conversation).data
        message_payload = MessageSerializer(self.message).data
        UUID(conversation_payload['uuid'])
        UUID(message_payload['uuid'])
        self.assertNotIn('id', conversation_payload)
        self.assertNotIn('id', message_payload)

    def test_integer_and_malformed_ids_return_404(self):
        self.client.force_authenticate(user=self.user)
        self.assertEqual(
            self.client.get(f'/api/chat/conversations/{self.conversation.id}/').status_code,
            404,
        )
        self.assertEqual(
            self.client.get('/api/chat/conversations/not-a-uuid/').status_code,
            404,
        )

    def test_uuid_detail_returns_200(self):
        self.client.force_authenticate(user=self.user)
        url = f'/api/chat/conversations/{self.conversation.uuid}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UUID(response.data['uuid']), self.conversation.uuid)