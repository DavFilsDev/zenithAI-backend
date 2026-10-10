from uuid import UUID, uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer
from .services import LLMUnavailableError, provider, stream_assistant_reply

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
            self.client.get(f'/api/v1/chat/conversations/{self.conversation.id}/').status_code,
            404,
        )
        self.assertEqual(
            self.client.get('/api/v1/chat/conversations/not-a-uuid/').status_code,
            404,
        )

    def test_uuid_detail_returns_200(self):
        self.client.force_authenticate(user=self.user)
        url = f'/api/v1/chat/conversations/{self.conversation.uuid}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UUID(response.data['uuid']), self.conversation.uuid)

    def test_detail_payload_message_count_matches_the_actual_count(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/v1/chat/conversations/{self.conversation.uuid}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message_count'], self.conversation.messages.count())
        self.assertEqual(self.conversation.messages.count(), 1)


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
        response = self.client.get('/api/v1/chat/conversations/')
        self.assertEqual(response.status_code, 200)
        item = response.data['results'][0]
        self.assertNotIn('messages', item)
        self.assertEqual(item['message_count'], 2)
        UUID(item['uuid'])
        self.assertEqual(response.data['count'], 1)
        self.assertIsNone(response.data['next'])
        self.assertIsNone(response.data['previous'])

    def test_list_uses_a_constant_number_of_queries(self):
        with self.assertNumQueries(2):
            response = self.client.get('/api/v1/chat/conversations/')
        self.assertEqual(response.status_code, 200)


class ProviderFailureTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='provider@example.com',
            username='provider-user',
            password='Str0ng-Passw0rd!42',
        )
        self.conversation = Conversation.objects.create(user=self.user, title='Provider chat')
        self.client.force_authenticate(user=self.user)

    @patch(
        'chat.services.provider.generate',
        side_effect=LLMUnavailableError('The AI service is temporarily unavailable. Please try again later.'),
    )
    def test_provider_failure_returns_503_and_persists_nothing(self, mock_generate):
        response = self.client.post(
            f'/api/v1/chat/conversations/{self.conversation.uuid}/messages/',
            {'message': 'Hello'},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error']['code'], 'llm_unavailable')
        self.assertEqual(self.conversation.messages.filter(role='assistant').count(), 0)
        self.assertEqual(self.conversation.messages.count(), 1)
        self.assertEqual(self.conversation.messages.first().role, 'user')
        self.assertNotIn('Retry-After', response.headers)

    @patch(
        'chat.services.provider.generate',
        side_effect=LLMUnavailableError('The AI service is temporarily unavailable. Please try again later.', retry_after=42),
    )
    def test_rate_limited_provider_forwards_retry_after(self, mock_generate):
        response = self.client.post(
            f'/api/v1/chat/conversations/{self.conversation.uuid}/messages/',
            {'message': 'Hello'},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error']['code'], 'llm_unavailable')
        self.assertEqual(response.headers['Retry-After'], '42')

    def test_generate_raises_without_an_api_key(self):
        with override_settings(LLM_API_KEY=''):
            with self.assertRaises(LLMUnavailableError):
                provider.generate('Hello', [])


class ErrorEnvelopeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='env@example.com',
            username='env-user',
            password='Str0ng-Passw0rd!42',
        )
        self.conversation = Conversation.objects.create(user=self.user, title='Env chat')
        self.client.force_authenticate(user=self.user)

    def test_missing_message_returns_validation_error_envelope(self):
        response = self.client.post(
            f'/api/v1/chat/conversations/{self.conversation.uuid}/messages/',
            {},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'validation_error')
        self.assertEqual(response.data['error']['message'], 'Message is required')
        self.assertEqual(response.data['error']['details'], {})

    def test_unknown_conversation_returns_not_found_envelope(self):
        response = self.client.post(
            f'/api/v1/chat/conversations/{uuid4()}/messages/',
            {'message': 'Hello'},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'not_found')
        self.assertEqual(response.data['error']['message'], 'Conversation not found')

    def test_post_to_conversation_detail_returns_method_not_allowed_envelope(self):
        response = self.client.post(f'/api/v1/chat/conversations/{self.conversation.uuid}/', {})
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.data['error']['code'], 'method_not_allowed')

    @override_settings(DEBUG=False)
    @patch(
        'chat.services.provider.generate',
        side_effect=RuntimeError('boom'),
    )
    def test_unexpected_error_returns_server_error_envelope(self, mock_generate):
        response = self.client.post(
            f'/api/v1/chat/conversations/{self.conversation.uuid}/messages/',
            {'message': 'Hello'},
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data['error']['code'], 'server_error')


class NestedMessagesTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='nested@example.com',
            username='nested-user',
            password='Str0ng-Passw0rd!42',
        )
        self.conversation = Conversation.objects.create(user=self.user, title='Nested chat')
        Message.objects.create(conversation=self.conversation, role='user', content='Hi')
        self.client.force_authenticate(user=self.user)

    def test_list_returns_the_conversation_messages(self):
        response = self.client.get(f'/api/v1/chat/conversations/{self.conversation.uuid}/messages/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['role'], 'user')

    @patch('chat.services.provider.generate', return_value='Hello back')
    def test_post_creates_both_messages_and_returns_the_assistant_message(self, mock_generate):
        response = self.client.post(
            f'/api/v1/chat/conversations/{self.conversation.uuid}/messages/',
            {'message': 'How are you?'},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['role'], 'assistant')
        self.assertEqual(response.data['content'], 'Hello back')
        self.assertEqual(self.conversation.messages.count(), 3)
        self.assertEqual(self.conversation.messages.filter(role='user').count(), 2)

    def test_post_requires_a_message(self):
        response = self.client.post(
            f'/api/v1/chat/conversations/{self.conversation.uuid}/messages/',
            {},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'validation_error')
        self.assertEqual(response.data['error']['message'], 'Message is required')

    def test_list_unknown_conversation_returns_not_found(self):
        response = self.client.get(f'/api/v1/chat/conversations/{uuid4()}/messages/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'not_found')

    def test_post_unknown_conversation_returns_not_found(self):
        response = self.client.post(f'/api/v1/chat/conversations/{uuid4()}/messages/', {'message': 'Hi'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'not_found')

    def test_put_on_conversation_detail_returns_method_not_allowed(self):
        response = self.client.put(
            f'/api/v1/chat/conversations/{self.conversation.uuid}/',
            {'title': 'Renamed'},
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.data['error']['code'], 'method_not_allowed')

    @patch(
        'chat.services.provider.generate',
        side_effect=LLMUnavailableError('The AI service is temporarily unavailable. Please try again later.'),
    )
    def test_post_provider_failure_returns_503_and_persists_only_the_user_message(self, mock_generate):
        response = self.client.post(
            f'/api/v1/chat/conversations/{self.conversation.uuid}/messages/',
            {'message': 'Hello'},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error']['code'], 'llm_unavailable')
        self.assertEqual(self.conversation.messages.filter(role='assistant').count(), 0)
        self.assertEqual(self.conversation.messages.count(), 2)


class PaginationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='pages@example.com',
            username='pages-user',
            password='Str0ng-Passw0rd!42',
        )
        self.client.force_authenticate(user=self.user)

    def test_page_size_above_the_cap_is_capped_at_20(self):
        for i in range(25):
            Conversation.objects.create(user=self.user, title=f'Chat {i}')
        response = self.client.get('/api/v1/chat/conversations/', {'page_size': 100})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 25)
        self.assertEqual(len(response.data['results']), 20)
        self.assertIsNotNone(response.data['next'])

    def test_empty_list_keeps_the_paginated_envelope(self):
        response = self.client.get('/api/v1/chat/conversations/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)
        self.assertIsNone(response.data['next'])
        self.assertIsNone(response.data['previous'])
        self.assertEqual(response.data['results'], [])


class StreamingTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='stream@example.com',
            username='stream-user',
            password='Str0ng-Passw0rd!42',
        )
        self.conversation = Conversation.objects.create(user=self.user, title='Stream chat')
        self.client.force_authenticate(user=self.user)

    def _url(self):
        return f'/api/v1/chat/conversations/{self.conversation.uuid}/messages/stream/'

    def _body(self, response):
        return b''.join(response.streaming_content).decode()

    @patch('chat.services.provider.stream', return_value=iter(['Hel', 'lo']))
    def test_happy_path_emits_tokens_then_done_and_persists_once(self, mock_stream):
        response = self.client.post(self._url(), {'message': 'Hi'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/event-stream')
        body = self._body(response)

        assistant = self.conversation.messages.get(role='assistant')
        self.assertEqual(assistant.content, 'Hello')

        self.assertIn('event: token\ndata: {"content": "Hel"}\n\n', body)
        self.assertIn('event: token\ndata: {"content": "lo"}\n\n', body)
        self.assertIn('event: done\n', body)
        self.assertIn(f'"message_id": "{assistant.uuid}"', body)
        self.assertIn(f'"conversation_id": "{self.conversation.uuid}"', body)

        self.assertEqual(self.conversation.messages.filter(role='user').count(), 1)
        self.assertEqual(self.conversation.messages.filter(role='assistant').count(), 1)

    @patch('chat.services.provider.stream', return_value=iter(['a', 'b', 'c']))
    def test_disconnect_mid_stream_leaves_no_assistant_row(self, mock_stream):
        state = {}
        generator = stream_assistant_reply(self.conversation, 'Hi', state)
        self.assertEqual(next(generator), 'a')
        generator.close()

        self.assertEqual(self.conversation.messages.filter(role='assistant').count(), 0)
        self.assertEqual(self.conversation.messages.filter(role='user').count(), 1)
        self.assertNotIn('assistant_message', state)

    def test_provider_error_mid_stream_emits_error_and_persists_no_assistant(self):
        def failing_stream(message, history):
            yield 'partial'
            raise LLMUnavailableError('The AI service is temporarily unavailable. Please try again later.')

        with patch('chat.services.provider.stream', side_effect=failing_stream):
            response = self.client.post(self._url(), {'message': 'Hi'})
            body = self._body(response)

        self.assertIn('event: token\ndata: {"content": "partial"}\n\n', body)
        self.assertIn('event: error\n', body)
        self.assertIn('"code": "llm_unavailable"', body)
        self.assertEqual(self.conversation.messages.filter(role='assistant').count(), 0)
        self.assertEqual(self.conversation.messages.filter(role='user').count(), 1)

    def test_missing_message_returns_validation_error_envelope(self):
        response = self.client.post(self._url(), {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'validation_error')

    def test_unknown_conversation_returns_not_found_envelope(self):
        response = self.client.post(
            f'/api/v1/chat/conversations/{uuid4()}/messages/stream/',
            {'message': 'Hi'},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'not_found')

    def test_unauthenticated_request_returns_unauthorized_envelope(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self._url(), {'message': 'Hi'})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['error']['code'], 'unauthorized')