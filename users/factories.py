import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

DEFAULT_PASSWORD = 'Str0ng-Passw0rd!42'


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    email = factory.Sequence(lambda n: f'user{n}@example.com')
    username = factory.Sequence(lambda n: f'user{n}')
    password = factory.LazyFunction(lambda: make_password(DEFAULT_PASSWORD))
