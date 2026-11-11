import pytest
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .factories import DEFAULT_PASSWORD, UserFactory
from .models import User
from .serializers import RegisterSerializer

pytestmark = pytest.mark.django_db


def obtain_tokens(client, email: str, password: str = DEFAULT_PASSWORD):
    return client.post(reverse('token_obtain_pair'), {'email': email, 'password': password})


def refresh_token_for(client, user: User) -> str:
    response = obtain_tokens(client, user.email)
    assert response.status_code == status.HTTP_200_OK
    return response.data['refresh']


def test_token_response_has_no_billing_state(api_client, user):
    response = obtain_tokens(api_client, user.email)

    assert response.status_code == status.HTTP_200_OK
    assert 'credits' not in response.data
    assert 'is_premium' not in response.data
    assert 'username' in response.data


def test_profile_response_contains_only_user_fields(auth_client):
    response = auth_client.get(reverse('profile'))

    assert response.status_code == status.HTTP_200_OK
    assert 'credits' not in response.data
    assert 'is_premium' not in response.data
    assert 'theme' not in response.data
    assert 'language' not in response.data
    assert 'email' in response.data


def test_api_key_never_appears_in_responses(api_client, auth_client, user):
    profile = auth_client.get(reverse('profile'))
    token = obtain_tokens(api_client, user.email)

    assert profile.status_code == status.HTTP_200_OK
    assert token.status_code == status.HTTP_200_OK
    assert 'api_key' not in profile.data
    assert 'api_key' not in token.data


def test_access_token_expires_in_15_minutes(api_client, user):
    response = obtain_tokens(api_client, user.email)
    token = AccessToken(response.data['access'])

    assert token.payload['exp'] - token.payload['iat'] == 15 * 60


def test_rotated_refresh_token_is_blacklisted(api_client, user):
    refresh = refresh_token_for(api_client, user)

    first = api_client.post(reverse('token_refresh'), {'refresh': refresh})
    second = api_client.post(reverse('token_refresh'), {'refresh': refresh})

    assert first.status_code == status.HTTP_200_OK
    assert first.data['refresh'] != refresh
    assert second.status_code == status.HTTP_401_UNAUTHORIZED


def test_blacklisted_token_is_rejected(api_client, user):
    refresh = refresh_token_for(api_client, user)
    RefreshToken(refresh).blacklist()

    response = api_client.post(reverse('token_refresh'), {'refresh': refresh})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_logout_blacklists_the_refresh_token(api_client, user):
    refresh = refresh_token_for(api_client, user)

    response = api_client.post(reverse('logout'), {'refresh': refresh})
    rejected = api_client.post(reverse('token_refresh'), {'refresh': refresh})

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert rejected.status_code == status.HTTP_401_UNAUTHORIZED


def test_logout_rejects_a_missing_refresh_token(api_client):
    response = api_client.post(reverse('logout'), {})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_logout_rejects_a_malformed_refresh_token(api_client):
    response = api_client.post(reverse('logout'), {'refresh': 'not-a-token'})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data['error']['code'] == 'unauthorized'


def test_registration_lowercases_the_email(api_client):
    response = api_client.post(reverse('register'), {
        'email': 'MixedCase@Example.COM',
        'username': 'mixed-case',
        'password': DEFAULT_PASSWORD,
        'password2': DEFAULT_PASSWORD,
    })

    assert response.status_code == status.HTTP_201_CREATED
    assert User.objects.get(username='mixed-case').email == 'mixedcase@example.com'


def test_registration_rejects_case_insensitive_duplicate(api_client, user):
    response = api_client.post(reverse('register'), {
        'email': user.email.upper(),
        'username': 'duplicate',
        'password': DEFAULT_PASSWORD,
        'password2': DEFAULT_PASSWORD,
    })

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data['error']['code'] == 'validation_error'
    assert 'email' in response.data['error']['details']


def test_registration_rejects_mismatched_passwords(api_client):
    response = api_client.post(reverse('register'), {
        'email': 'mismatch@example.com',
        'username': 'mismatch',
        'password': DEFAULT_PASSWORD,
        'password2': f'{DEFAULT_PASSWORD}x',
    })

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data['error']['code'] == 'validation_error'
    assert 'password' in response.data['error']['details']


def test_registration_serializer_ignores_the_current_user_email(user):
    serializer = RegisterSerializer(instance=user, data={
        'email': user.email.upper(),
        'username': user.username,
        'password': DEFAULT_PASSWORD,
        'password2': DEFAULT_PASSWORD,
    })

    assert serializer.is_valid(), serializer.errors


def test_login_accepts_uppercase_email(api_client, user):
    response = obtain_tokens(api_client, user.email.upper())

    assert response.status_code == status.HTTP_200_OK


def test_login_rejects_invalid_credentials(api_client, user):
    response = obtain_tokens(api_client, user.email, 'wrong-password')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data['error']['code'] == 'unauthorized'


def test_database_rejects_case_insensitive_duplicate():
    UserFactory(email='db-case@example.com')

    with pytest.raises(IntegrityError):
        UserFactory(email='DB-CASE@Example.com')


def test_user_string_is_the_email(user):
    assert str(user) == user.email


def test_unauthenticated_profile_request_returns_unauthorized_envelope(api_client):
    response = api_client.get(reverse('profile'))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data['error']['code'] == 'unauthorized'
    assert 'message' in response.data['error']
    assert response.data['error']['details'] == {}


def test_registration_returns_field_map_in_details(api_client):
    response = api_client.post(reverse('register'), {
        'username': 'noemail',
        'password': DEFAULT_PASSWORD,
        'password2': DEFAULT_PASSWORD,
    })

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data['error']['code'] == 'validation_error'
    assert 'email' in response.data['error']['details']


def test_profile_patch_updates_the_username(auth_client, user):
    response = auth_client.patch(reverse('profile'), {'username': 'renamed'})

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.username == 'renamed'


def test_put_profile_returns_method_not_allowed(auth_client):
    response = auth_client.put(reverse('profile'), {'username': 'renamed'})

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response.data['error']['code'] == 'method_not_allowed'
