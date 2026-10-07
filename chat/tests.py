from uuid import UUID
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer
from .services import LLMUnavailableError, gemini_service

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


class ListPayloadTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='list@example.com',
            username='list-user',
            password='Str0ng-Passw0rd!42',
        )
        self.conversation = Conversation.objects.create(user=self.user, title='List chat')
        Message.objects.create(conversation=self.conversation, role='user', content='Hi')
        Message.objects.create(conversation=self.conversation, role='assistant', content='Hello back')
        self.client.force_authenticate(user=self.user)

    def test_list_payload_is_lean(self):
        response = self.client.get('/api/chat/conversations/')
        self.assertEqual(response.status_code, 200)
        item = response.data[0]
        self.assertNotIn('messages', item)
        self.assertEqual(item['message_count'], 2)
        UUID(item['uuid'])

    def test_list_uses_a_constant_number_of_queries(self):
        with self.assertNumQueries(1):
            response = self.client.get('/api/chat/conversations/')
        self.assertEqual(response.status_code, 200)


class ProviderFailureTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='provider@example.com',
            username='provider-user',
            password='Str0ng-Passw0rd!42',
        )
        self.client.force_authenticate(user=self.user)

    @patch(
        'chat.views.gemini_service.generate_response',
        side_effect=LLMUnavailableError('The AI service is temporarily unavailable. Please try again later.'),
    )
    def test_provider_failure_returns_503_and_persists_nothing(self, mock_generate):
        response = self.client.post('/api/chat/chat/', {'message': 'Hello'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error']['code'], 'llm_unavailable')

        conversation = Conversation.objects.get(title='Hello')
        self.assertEqual(conversation.messages.filter(role='assistant').count(), 0)
        self.assertEqual(conversation.messages.count(), 1)
        self.assertEqual(conversation.messages.first().role, 'user')

    def test_generate_response_raises_without_an_api_key(self):
        with override_settings(GEMINI_API_KEY=''):
            with self.assertRaises(LLMUnavailableError):
                gemini_service.generate_response('Hello')