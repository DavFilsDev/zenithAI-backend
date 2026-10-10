import logging

from django.conf import settings
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class QuotaExhausted(APIException):
    """The shared daily message quota is used up."""

    status_code = 429
    default_detail = 'The daily message quota has been exhausted. It resets at midnight.'
    default_code = 'quota_exhausted'

    def __init__(self, retry_after=None):
        self.retry_after = int(retry_after) if isinstance(retry_after, (int, float)) else None
        super().__init__()


_CODE_BY_STATUS = {
    400: 'validation_error',
    401: 'unauthorized',
    403: 'forbidden',
    404: 'not_found',
    405: 'method_not_allowed',
    429: 'rate_limited',
    500: 'server_error',
}

_DEFAULT_MESSAGES = {
    400: 'The request payload is invalid.',
    401: 'Authentication credentials were not provided or are invalid.',
    403: 'You do not have permission to perform this action.',
    404: 'The requested resource was not found.',
    405: 'This HTTP method is not allowed on this endpoint.',
    429: 'Too many requests, please try again later.',
    500: 'An unexpected error occurred.',
}


def _error_code(status_code):
    return _CODE_BY_STATUS.get(status_code, 'server_error')


def _error_message(exc, response, code, status_code):
    detail = getattr(exc, 'detail', None)
    if isinstance(detail, str) and detail:
        return detail
    if isinstance(detail, list) and detail and isinstance(detail[0], str):
        return detail[0]
    if code == 'validation_error' and isinstance(response.data, dict) and response.data:
        return _DEFAULT_MESSAGES[status_code]
    return _DEFAULT_MESSAGES.get(status_code, _DEFAULT_MESSAGES[500])


def _error_details(exc, response, code):
    if code == 'validation_error' and isinstance(response.data, dict):
        return response.data
    return {}


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is None:
        if settings.DEBUG:
            raise exc
        logger.error('Unhandled API exception: %s', exc, exc_info=True)
        return Response(
            {'error': {'code': 'server_error', 'message': _DEFAULT_MESSAGES[500], 'details': {}}},
            status=500,
        )

    code = 'quota_exhausted' if isinstance(exc, QuotaExhausted) else _error_code(response.status_code)
    headers = {}
    if code in ('rate_limited', 'quota_exhausted'):
        wait = getattr(exc, 'retry_after', None)
        if wait is None:
            wait = getattr(exc, 'wait', None)
        if isinstance(wait, (int, float)):
            headers['Retry-After'] = str(int(wait))

    return Response(
        {
            'error': {
                'code': code,
                'message': _error_message(exc, response, code, response.status_code),
                'details': _error_details(exc, response, code),
            }
        },
        status=response.status_code,
        headers=headers,
    )