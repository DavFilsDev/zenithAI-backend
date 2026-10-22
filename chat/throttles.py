from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.throttling import AnonRateThrottle, BaseThrottle, UserRateThrottle
from rest_framework.views import APIView

from backend.exceptions import QuotaExhausted

from .models import DailyQuota


class MessageUserThrottle(UserRateThrottle):
    scope = 'messages_user'


class MessageAnonThrottle(AnonRateThrottle):
    scope = 'messages_anon'


def seconds_until_midnight() -> int:
    now = timezone.localtime()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


class DailyQuotaThrottle(BaseThrottle):
    def allow_request(self, request: Request, view: APIView) -> bool:
        cap = getattr(settings, 'DAILY_MESSAGE_CAP', 500)
        if DailyQuota.try_consume(cap):
            return True
        raise QuotaExhausted(retry_after=seconds_until_midnight())
