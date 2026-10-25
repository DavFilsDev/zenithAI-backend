from typing import cast

import pytest
from rest_framework.test import APIClient

from chat.factories import ConversationFactory, MessageFactory
from chat.models import Conversation, Message
from users.factories import UserFactory
from users.models import User


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user() -> User:
    return cast(User, UserFactory())


@pytest.fixture
def other_user() -> User:
    return cast(User, UserFactory())


@pytest.fixture
def auth_client(api_client: APIClient, user: User) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def conversation(user: User) -> Conversation:
    return cast(Conversation, ConversationFactory(user=user))


@pytest.fixture
def other_conversation(other_user: User) -> Conversation:
    return cast(Conversation, ConversationFactory(user=other_user))


@pytest.fixture
def message(conversation: Conversation) -> Message:
    return cast(Message, MessageFactory(conversation=conversation))
