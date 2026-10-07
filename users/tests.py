from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

User = get_user_model()


class UserPayloadTests(APITestCase):
    def setUp(self):
        self.password = 'Str0ng-Passw0rd!42'
        self.user = User.objects.create_user(
            email='tester@example.com',
            username='tester',
            password=self.password,
        )

    def test_token_response_has_no_billing_state(self):
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'email': self.user.email, 'password': self.password},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('credits', response.data)
        self.assertNotIn('is_premium', response.data)
        self.assertIn('username', response.data)

    def test_profile_response_contains_only_user_fields(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('credits', response.data)
        self.assertNotIn('is_premium', response.data)
        self.assertNotIn('theme', response.data)
        self.assertNotIn('language', response.data)
        self.assertIn('email', response.data)

    def test_api_key_never_appears_in_responses(self):
        self.client.force_authenticate(self.user)
        profile = self.client.get(reverse('profile'))
        self.assertEqual(profile.status_code, status.HTTP_200_OK)
        self.assertNotIn('api_key', profile.data)

        token = self.client.post(
            reverse('token_obtain_pair'),
            {'email': self.user.email, 'password': self.password},
        )
        self.assertEqual(token.status_code, status.HTTP_200_OK)
        self.assertNotIn('api_key', token.data)


class TokenSecurityTests(APITestCase):
    def setUp(self):
        self.password = 'Str0ng-Passw0rd!42'
        self.user = User.objects.create_user(
            email='tokens@example.com',
            username='tokens',
            password=self.password,
        )
        self.refresh = self.client.post(
            reverse('token_obtain_pair'),
            {'email': self.user.email, 'password': self.password},
        ).data['refresh']

    def test_access_token_expires_in_15_minutes(self):
        access = self.client.post(
            reverse('token_obtain_pair'),
            {'email': self.user.email, 'password': self.password},
        ).data['access']
        token = AccessToken(access)
        self.assertEqual(token.payload['exp'] - token.payload['iat'], 15 * 60)

    def test_rotated_refresh_token_is_blacklisted(self):
        first = self.client.post(reverse('token_refresh'), {'refresh': self.refresh})
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertIn('refresh', first.data)
        self.assertNotEqual(first.data['refresh'], self.refresh)

        second = self.client.post(reverse('token_refresh'), {'refresh': self.refresh})
        self.assertEqual(second.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_blacklisted_token_is_rejected(self):
        RefreshToken(self.refresh).blacklist()
        response = self.client.post(reverse('token_refresh'), {'refresh': self.refresh})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_the_refresh_token(self):
        response = self.client.post(reverse('logout'), {'refresh': self.refresh})
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        refresh = self.client.post(reverse('token_refresh'), {'refresh': self.refresh})
        self.assertEqual(refresh.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_rejects_a_missing_refresh_token(self):
        response = self.client.post(reverse('logout'), {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EmailNormalizationTests(APITestCase):
    def test_registration_lowercases_the_email(self):
        response = self.client.post(reverse('register'), {
            'email': 'MixedCase@Example.COM',
            'username': 'mixed-case',
            'password': 'Str0ng-Passw0rd!42',
            'password2': 'Str0ng-Passw0rd!42',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(username='mixed-case').email, 'mixedcase@example.com')

    def test_registration_rejects_case_insensitive_duplicate(self):
        User.objects.create_user(
            email='duplicate@example.com',
            username='duplicate',
            password='Str0ng-Passw0rd!42',
        )
        response = self.client.post(reverse('register'), {
            'email': 'DUPLICATE@Example.com',
            'username': 'dup-two',
            'password': 'Str0ng-Passw0rd!42',
            'password2': 'Str0ng-Passw0rd!42',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_login_accepts_uppercase_email(self):
        self.password = 'Str0ng-Passw0rd!42'
        User.objects.create_user(
            email='login@example.com',
            username='login-user',
            password=self.password,
        )
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'email': 'LOGIN@Example.COM', 'password': self.password},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_database_rejects_case_insensitive_duplicate(self):
        User.objects.create_user(
            email='db-case@example.com',
            username='db-case',
            password='Str0ng-Passw0rd!42',
        )
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email='DB-CASE@Example.com',
                username='db-case-two',
                password='Str0ng-Passw0rd!42',
            )
