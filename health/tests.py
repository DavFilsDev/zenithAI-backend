from unittest.mock import patch

from django.test import TestCase


class HealthEndpointTests(TestCase):
    def test_health_returns_200_without_authentication(self):
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'ok')
        self.assertEqual(response.data['database'], 'ok')

    @patch('health.views.connection.cursor', side_effect=Exception('db down'))
    def test_health_returns_503_when_database_is_unreachable(self, mock_cursor):
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['status'], 'error')
        self.assertEqual(response.data['database'], 'unavailable')