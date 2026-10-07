from django.test import TestCase


class DocumentationTests(TestCase):
    def test_schema_serves_openapi_json(self):
        response = self.client.get('/api/v1/schema/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'].split(';')[0], 'application/vnd.oai.openapi')
        self.assertIn('/api/v1/health/', response.data['paths'])

    def test_swagger_ui_serves(self):
        response = self.client.get('/api/v1/docs/')
        self.assertEqual(response.status_code, 200)

    def test_redoc_serves(self):
        response = self.client.get('/api/v1/redoc/')
        self.assertEqual(response.status_code, 200)