import factory

from users.factories import UserFactory

from .models import Conversation, Message


class ConversationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Conversation

    user = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f'Conversation {n}')


class MessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Message

    conversation = factory.SubFactory(ConversationFactory)
    role = 'user'
    content = factory.Sequence(lambda n: f'Message {n}')
