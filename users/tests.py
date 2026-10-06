from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class CreditsRemovalTests(APITestCase):
    def setUp(self):
        self.password = 'Str0ng-Passw0rd!42'
        self.user = User.objects.create_user(
            email='tester@example.com',
            username='tester',
            password=self.password,
        )

    def test_token_response_has_no_credits(self):
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'email': self.user.email, 'password': self.password},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('credits', response.data)
        self.assertIn('username', response.data)

    def test_profile_response_has_no_credits(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('credits', response.data)
        self.assertIn('email', response.data)
