from unittest.mock import patch

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_health_returns_200_without_authentication(api_client):
    response = api_client.get(reverse('health'))

    assert response.status_code == 200
    assert response.data['status'] == 'ok'
    assert response.data['database'] == 'ok'


@patch('health.views.connection.cursor', side_effect=Exception('db down'))
def test_health_returns_503_when_database_is_unreachable(mock_cursor, api_client):
    response = api_client.get(reverse('health'))

    assert response.status_code == 503
    assert response.data['status'] == 'error'
    assert response.data['database'] == 'unavailable'
