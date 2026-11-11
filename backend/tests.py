from django.urls import reverse

from backend.settings.database import database_config


def test_database_config_reads_a_pooled_neon_url():
    config = database_config(
        'postgresql://user:p%40ss@ep-test-pooler.eu-central-1.aws.neon.tech/neondb'
        '?sslmode=require&channel_binding=require'
    )

    assert config['HOST'] == 'ep-test-pooler.eu-central-1.aws.neon.tech'
    assert config['NAME'] == 'neondb'
    assert config['USER'] == 'user'
    assert config['PASSWORD'] == 'p@ss'
    assert config['CONN_MAX_AGE'] == 0
    assert config['CONN_HEALTH_CHECKS'] is True
    assert config['OPTIONS']['sslmode'] == 'require'
    assert config['OPTIONS']['channel_binding'] == 'require'


def test_schema_serves_openapi_json(api_client):
    response = api_client.get(reverse('schema'))

    assert response.status_code == 200
    assert response['Content-Type'].split(';')[0] == 'application/vnd.oai.openapi'
    assert '/api/v1/health/' in response.data['paths']
    assert '/api/v1/health/live/' in response.data['paths']


def test_swagger_ui_serves(api_client):
    response = api_client.get(reverse('swagger-ui'))

    assert response.status_code == 200


def test_redoc_serves(api_client):
    response = api_client.get(reverse('redoc'))

    assert response.status_code == 200
