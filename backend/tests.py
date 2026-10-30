from django.urls import reverse


def test_schema_serves_openapi_json(api_client):
    response = api_client.get(reverse('schema'))

    assert response.status_code == 200
    assert response['Content-Type'].split(';')[0] == 'application/vnd.oai.openapi'
    assert '/api/v1/health/' in response.data['paths']


def test_swagger_ui_serves(api_client):
    response = api_client.get(reverse('swagger-ui'))

    assert response.status_code == 200


def test_redoc_serves(api_client):
    response = api_client.get(reverse('redoc'))

    assert response.status_code == 200
