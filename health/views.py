import logging

from django.db import connection
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    database = serializers.CharField()


class HealthView(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    @extend_schema(
        summary="Health check",
        description="Public readiness probe: returns 200 when the service and the database are reachable, "
        "503 when the database is not. No authentication is required.",
        tags=['System'],
        responses={
            200: OpenApiResponse(response=HealthSerializer(), description="Service and database are available"),
            503: OpenApiResponse(response=HealthSerializer(), description="The database is unreachable"),
        },
    )
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
        except Exception as exc:
            logger.error('Health check failed: %s', exc)
            return Response({'status': 'error', 'database': 'unavailable'}, status=503)
        return Response({'status': 'ok', 'database': 'ok'})