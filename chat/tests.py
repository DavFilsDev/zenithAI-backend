from datetime import timedelta
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from .factories import ConversationFactory
from .models import Conversation, DailyQuota
from .providers import CircuitBreaker, CircuitBreakerProvider, LLMUnavailableError
from .serializers import ConversationSerializer, MessageSerializer
from .services import provider, stream_assistant_reply
from .throttles import MessageAnonThrottle, MessageUserThrottle, seconds_until_midnight

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def conversation_url(conversation: Conversation) -> str:
    return reverse('chat_v1:conversation-detail', kwargs={'uuid': conversation.uuid})


def messages_url(conversation: Conversation) -> str:
    return reverse('chat_v1:conversation-messages', kwargs={'conversation_id': conversation.uuid})


def stream_url(conversation: Conversation) -> str:
    return reverse('chat_v1:conversation-messages-stream', kwargs={'conversation_id': conversation.uuid})


def stream_body(response) -> str:
    return b''.join(response.streaming_content).decode()


def test_message_serializer_has_no_token_count(message):
    payload = MessageSerializer(message).data

    assert 'tokens' not in payload
    assert payload['role'] == message.role


def test_conversation_payload_messages_have_no_token_count(conversation, message):
    payload = ConversationSerializer(conversation).data
    nested = next(item for item in payload['messages'])

    assert 'tokens' not in nested
    assert nested['content'] == message.content


def test_payload_uses_uuid_instead_of_integer_id(conversation, message):
    conversation_payload = ConversationSerializer(conversation).data
    message_payload = MessageSerializer(message).data

    UUID(conversation_payload['uuid'])
    UUID(message_payload['uuid'])
    assert 'id' not in conversation_payload
    assert 'id' not in message_payload


def test_model_strings(conversation, message):
    quota = DailyQuota.objects.create(date=timezone.localdate(), count=2)

    assert str(conversation) == f'{conversation.user.email} - {conversation.title}'
    assert str(message).startswith(f'{message.role}: ')
    assert str(quota) == f'{quota.date}: 2'


def test_admin_helpers(conversation, message):
    from .admin import ConversationAdmin, MessageAdmin

    assert ConversationAdmin.message_count(None, conversation) == 1
    assert MessageAdmin.short_content(None, message) == message.content


def test_list_is_paginated_and_lean(auth_client, conversation, message):
    response = auth_client.get(reverse('chat_v1:conversation-list'))

    assert response.status_code == status.HTTP_200_OK
    item = response.data['results'][0]
    assert 'messages' not in item
    assert item['message_count'] == 1
    UUID(item['uuid'])
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None


def test_list_uses_a_constant_number_of_queries(auth_client, conversation, django_assert_num_queries):
    with django_assert_num_queries(2):
        response = auth_client.get(reverse('chat_v1:conversation-list'))

    assert response.status_code == status.HTTP_200_OK


def test_create_conversation(auth_client, user):
    response = auth_client.post(reverse('chat_v1:conversation-list'), {'title': 'New chat'})

    assert response.status_code == status.HTTP_201_CREATED
    conversation = Conversation.objects.get(uuid=response.data['uuid'])
    assert conversation.user == user
    assert conversation.title == 'New chat'
    assert response.data['message_count'] == 0


def test_create_conversation_requires_a_title(auth_client):
    response = auth_client.post(reverse('chat_v1:conversation-list'), {})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data['error']['code'] == 'validation_error'
    assert 'title' in response.data['error']['details']


def test_create_conversation_requires_authentication(api_client):
    response = api_client.post(reverse('chat_v1:conversation-list'), {'title': 'New chat'})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data['error']['code'] == 'unauthorized'


def test_detail_returns_the_conversation(auth_client, conversation, message):
    response = auth_client.get(conversation_url(conversation))

    assert response.status_code == status.HTTP_200_OK
    assert UUID(response.data['uuid']) == conversation.uuid
    assert response.data['message_count'] == 1


def test_detail_unknown_conversation_returns_not_found(auth_client):
    response = auth_client.get(reverse('chat_v1:conversation-detail', kwargs={'uuid': uuid4()}))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data['error']['code'] == 'not_found'


def test_detail_wrong_owner_returns_not_found(auth_client, other_conversation):
    response = auth_client.get(conversation_url(other_conversation))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_detail_integer_and_malformed_ids_return_404(auth_client, conversation):
    integer = auth_client.get(f'/api/v1/chat/conversations/{conversation.id}/')
    malformed = auth_client.get('/api/v1/chat/conversations/not-a-uuid/')

    assert integer.status_code == status.HTTP_404_NOT_FOUND
    assert malformed.status_code == status.HTTP_404_NOT_FOUND


def test_patch_updates_the_title(auth_client, conversation):
    response = auth_client.patch(conversation_url(conversation), {'title': 'Renamed'})

    assert response.status_code == status.HTTP_200_OK
    conversation.refresh_from_db()
    assert conversation.title == 'Renamed'


def test_patch_wrong_owner_returns_not_found(auth_client, other_conversation):
    response = auth_client.patch(conversation_url(other_conversation), {'title': 'Renamed'})

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_removes_the_conversation(auth_client, conversation):
    response = auth_client.delete(conversation_url(conversation))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Conversation.objects.filter(pk=conversation.pk).exists()


def test_delete_wrong_owner_returns_not_found(auth_client, other_conversation):
    response = auth_client.delete(conversation_url(other_conversation))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert Conversation.objects.filter(pk=other_conversation.pk).exists()


def test_unauthenticated_conversation_requests_return_unauthorized(api_client, conversation):
    responses = (
        api_client.get(reverse('chat_v1:conversation-list')),
        api_client.get(conversation_url(conversation)),
        api_client.get(messages_url(conversation)),
    )

    for response in responses:
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data['error']['code'] == 'unauthorized'


def test_post_and_put_on_detail_return_method_not_allowed(auth_client, conversation):
    post = auth_client.post(conversation_url(conversation), {})
    put = auth_client.put(conversation_url(conversation), {'title': 'Renamed'})

    assert post.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert post.data['error']['code'] == 'method_not_allowed'
    assert put.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert put.data['error']['code'] == 'method_not_allowed'


def test_list_messages(auth_client, conversation, message):
    response = auth_client.get(messages_url(conversation))

    assert response.status_code == status.HTTP_200_OK
    assert response.data['count'] == 1
    assert response.data['results'][0]['role'] == message.role


def test_list_messages_unknown_conversation_returns_not_found(auth_client):
    response = auth_client.get(reverse('chat_v1:conversation-messages', kwargs={'conversation_id': uuid4()}))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_list_messages_wrong_owner_returns_not_found(auth_client, other_conversation):
    response = auth_client.get(messages_url(other_conversation))

    assert response.status_code == status.HTTP_404_NOT_FOUND


@patch('chat.services.provider.generate', return_value='Hello back')
def test_post_creates_both_messages_and_returns_the_assistant_message(
    mock_generate, auth_client, conversation, message
):
    response = auth_client.post(messages_url(conversation), {'message': 'How are you?'})

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['role'] == 'assistant'
    assert response.data['content'] == 'Hello back'
    assert conversation.messages.count() == 3
    assert conversation.messages.filter(role='user').count() == 2


def test_post_requires_a_message(auth_client, conversation):
    response = auth_client.post(messages_url(conversation), {})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data['error']['code'] == 'validation_error'
    assert response.data['error']['message'] == 'Message is required'


def test_post_unknown_conversation_returns_not_found(auth_client):
    response = auth_client.post(
        reverse('chat_v1:conversation-messages', kwargs={'conversation_id': uuid4()}),
        {'message': 'Hi'},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_post_wrong_owner_returns_not_found(auth_client, other_conversation):
    response = auth_client.post(messages_url(other_conversation), {'message': 'Hi'})

    assert response.status_code == status.HTTP_404_NOT_FOUND


@patch(
    'chat.services.provider.generate',
    side_effect=LLMUnavailableError('The AI service is temporarily unavailable. Please try again later.'),
)
def test_provider_failure_returns_503_and_persists_only_the_user_message(mock_generate, auth_client, conversation):
    response = auth_client.post(messages_url(conversation), {'message': 'Hello'})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.data['error']['code'] == 'llm_unavailable'
    assert conversation.messages.filter(role='assistant').count() == 0
    assert conversation.messages.count() == 1
    assert conversation.messages.first().role == 'user'
    assert 'Retry-After' not in response.headers


@patch(
    'chat.services.provider.generate',
    side_effect=LLMUnavailableError(
        'The AI service is temporarily unavailable. Please try again later.',
        retry_after=42,
    ),
)
def test_provider_failure_forwards_retry_after(mock_generate, auth_client, conversation):
    response = auth_client.post(messages_url(conversation), {'message': 'Hello'})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.headers['Retry-After'] == '42'


def test_generate_raises_without_an_api_key():
    with override_settings(LLM_API_KEY=''), pytest.raises(LLMUnavailableError):
        provider.generate('Hello', [])


@override_settings(DEBUG=False)
@patch('chat.services.provider.generate', side_effect=RuntimeError('boom'))
def test_unexpected_error_returns_server_error_envelope(mock_generate, auth_client, conversation):
    response = auth_client.post(messages_url(conversation), {'message': 'Hello'})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.data['error']['code'] == 'server_error'


@patch('chat.services.provider.stream', return_value=iter(['Hel', 'lo']))
def test_stream_happy_path_emits_tokens_then_done_and_persists_once(mock_stream, auth_client, conversation):
    response = auth_client.post(stream_url(conversation), {'message': 'Hi'})

    assert response.status_code == status.HTTP_200_OK
    assert response['Content-Type'] == 'text/event-stream'
    body = stream_body(response)

    assistant = conversation.messages.get(role='assistant')
    assert assistant.content == 'Hello'
    assert 'event: token\ndata: {"content": "Hel"}\n\n' in body
    assert 'event: token\ndata: {"content": "lo"}\n\n' in body
    assert 'event: done\n' in body
    assert f'"message_id": "{assistant.uuid}"' in body
    assert f'"conversation_id": "{conversation.uuid}"' in body
    assert conversation.messages.filter(role='user').count() == 1
    assert conversation.messages.filter(role='assistant').count() == 1


@patch('chat.services.provider.stream', return_value=iter(['a', 'b', 'c']))
def test_disconnect_mid_stream_leaves_no_assistant_row(mock_stream, conversation):
    state = {}
    generator = stream_assistant_reply(conversation, 'Hi', state)
    assert next(generator) == 'a'
    generator.close()

    assert conversation.messages.filter(role='assistant').count() == 0
    assert conversation.messages.filter(role='user').count() == 1
    assert 'assistant_message' not in state


def test_provider_error_mid_stream_emits_error_and_persists_no_assistant(auth_client, conversation):
    def failing_stream(message, history):
        yield 'partial'
        raise LLMUnavailableError('The AI service is temporarily unavailable. Please try again later.')

    with patch('chat.services.provider.stream', side_effect=failing_stream):
        response = auth_client.post(stream_url(conversation), {'message': 'Hi'})
        body = stream_body(response)

    assert 'event: token\ndata: {"content": "partial"}\n\n' in body
    assert 'event: error\n' in body
    assert '"code": "llm_unavailable"' in body
    assert conversation.messages.filter(role='assistant').count() == 0
    assert conversation.messages.filter(role='user').count() == 1


@patch('chat.services.provider.stream', side_effect=RuntimeError('boom'))
def test_stream_unexpected_error_emits_server_error(mock_stream, auth_client, conversation):
    response = auth_client.post(stream_url(conversation), {'message': 'Hi'})
    body = stream_body(response)

    assert response.status_code == status.HTTP_200_OK
    assert 'event: error\n' in body
    assert '"code": "server_error"' in body
    assert conversation.messages.filter(role='assistant').count() == 0


def test_stream_requires_a_message(auth_client, conversation):
    response = auth_client.post(stream_url(conversation), {})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data['error']['code'] == 'validation_error'


def test_stream_unknown_conversation_returns_not_found(auth_client):
    response = auth_client.post(
        reverse('chat_v1:conversation-messages-stream', kwargs={'conversation_id': uuid4()}),
        {'message': 'Hi'},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_stream_wrong_owner_returns_not_found(auth_client, other_conversation):
    response = auth_client.post(stream_url(other_conversation), {'message': 'Hi'})

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_stream_unauthenticated_request_returns_unauthorized(api_client, conversation):
    response = api_client.post(stream_url(conversation), {'message': 'Hi'})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data['error']['code'] == 'unauthorized'


def test_scopes_use_the_configured_rates():
    assert MessageUserThrottle().rate == '10/min'
    assert MessageAnonThrottle().rate == '5/min'


@patch('chat.services.provider.generate', return_value='ok')
def test_sending_past_the_user_limit_returns_429_with_retry_after(mock_generate, auth_client, conversation):
    for _ in range(10):
        response = auth_client.post(messages_url(conversation), {'message': 'Hi'})
        assert response.status_code == status.HTTP_201_CREATED

    response = auth_client.post(messages_url(conversation), {'message': 'Hi'})

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.data['error']['code'] == 'rate_limited'
    assert 1 <= int(response['Retry-After']) <= 60


@patch('chat.services.provider.generate', return_value='ok')
def test_the_limit_is_shared_between_send_and_stream(mock_generate, auth_client, conversation):
    for _ in range(10):
        auth_client.post(messages_url(conversation), {'message': 'Hi'})

    response = auth_client.post(stream_url(conversation), {'message': 'Hi'})

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.data['error']['code'] == 'rate_limited'


def test_listing_messages_is_not_throttled(auth_client, conversation):
    for _ in range(11):
        assert auth_client.get(messages_url(conversation)).status_code == status.HTTP_200_OK


@override_settings(DAILY_MESSAGE_CAP=2)
@patch('chat.services.provider.generate', return_value='ok')
def test_exhausting_the_cap_returns_quota_exhausted(mock_generate, auth_client, conversation):
    assert auth_client.post(messages_url(conversation), {'message': 'one'}).status_code == status.HTTP_201_CREATED
    assert auth_client.post(messages_url(conversation), {'message': 'two'}).status_code == status.HTTP_201_CREATED

    response = auth_client.post(messages_url(conversation), {'message': 'three'})

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.data['error']['code'] == 'quota_exhausted'
    assert 'quota' in response.data['error']['message'].lower()
    assert 1 <= int(response['Retry-After']) <= 86400
    assert DailyQuota.objects.get(date=timezone.localdate()).count == 2


@override_settings(DAILY_MESSAGE_CAP=2)
@patch('chat.services.provider.generate', return_value='ok')
def test_the_cap_is_shared_across_users(mock_generate, api_client, user, other_user, conversation):
    other_conversation = ConversationFactory(user=other_user)

    api_client.force_authenticate(user=user)
    assert api_client.post(messages_url(conversation), {'message': 'one'}).status_code == status.HTTP_201_CREATED

    api_client.force_authenticate(user=other_user)
    assert api_client.post(messages_url(other_conversation), {'message': 'two'}).status_code == status.HTTP_201_CREATED

    api_client.force_authenticate(user=user)
    response = api_client.post(messages_url(conversation), {'message': 'three'})

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.data['error']['code'] == 'quota_exhausted'


@override_settings(DAILY_MESSAGE_CAP=2)
@patch('chat.services.provider.generate', return_value='ok')
def test_the_counter_survives_an_in_memory_restart(mock_generate, auth_client, conversation):
    auth_client.post(messages_url(conversation), {'message': 'one'})
    auth_client.post(messages_url(conversation), {'message': 'two'})
    cache.clear()

    response = auth_client.post(messages_url(conversation), {'message': 'three'})

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.data['error']['code'] == 'quota_exhausted'
    assert DailyQuota.objects.filter(date=timezone.localdate(), count=2).exists()


@override_settings(DAILY_MESSAGE_CAP=2)
@patch('chat.services.provider.generate', return_value='ok')
def test_a_new_day_starts_from_zero(mock_generate, auth_client, conversation):
    DailyQuota.objects.create(date=timezone.localdate() - timedelta(days=1), count=2)

    response = auth_client.post(messages_url(conversation), {'message': 'fresh day'})

    assert response.status_code == status.HTTP_201_CREATED
    assert DailyQuota.objects.get(date=timezone.localdate()).count == 1


@override_settings(DAILY_MESSAGE_CAP=2)
def test_listing_messages_does_not_consume_the_quota(auth_client, conversation):
    for _ in range(3):
        assert auth_client.get(messages_url(conversation)).status_code == status.HTTP_200_OK

    assert not DailyQuota.objects.exists()


def test_seconds_until_midnight_is_within_a_day():
    assert 1 <= seconds_until_midnight() <= 86400


def test_an_open_circuit_fails_fast_with_llm_unavailable(auth_client, conversation):
    class FailingCounter:
        def __init__(self):
            self.calls = 0

        def generate(self, message, history):
            self.calls += 1
            raise LLMUnavailableError('down')

    inner = FailingCounter()
    breaker = CircuitBreaker(threshold=2, cooldown=60)
    wrapped = CircuitBreakerProvider(inner, breaker)

    with patch('chat.services.provider', wrapped):
        for _ in range(2):
            response = auth_client.post(messages_url(conversation), {'message': 'Hi'})
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert response.data['error']['code'] == 'llm_unavailable'
        assert inner.calls == 2

        response = auth_client.post(messages_url(conversation), {'message': 'Hi'})
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data['error']['code'] == 'llm_unavailable'
        assert inner.calls == 2
