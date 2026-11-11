import logging

from django.db import connection
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    database = serializers.CharField()


class LivenessSerializer(serializers.Serializer):
    status = serializers.CharField()


class LivenessView(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    @extend_schema(
        summary="Liveness check",
        description="Public liveness probe that only confirms the process is serving requests. "
        "It does not query the database, so platform health checks do not wake a suspended database.",
        tags=['System'],
        responses={
            200: OpenApiResponse(response=LivenessSerializer(), description="The service is running"),
        },
    )
    def get(self, request: Request) -> Response:
        return Response({'status': 'ok'})


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
    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
        except Exception as exc:
            logger.error('Health check failed: %s', exc)
            return Response({'status': 'error', 'database': 'unavailable'}, status=503)
        return Response({'status': 'ok', 'database': 'ok'})
