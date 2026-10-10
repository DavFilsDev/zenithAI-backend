from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.throttling import AnonRateThrottle, BaseThrottle, UserRateThrottle

from backend.exceptions import QuotaExhausted

from .models import DailyQuota


class MessageUserThrottle(UserRateThrottle):
    scope = 'messages_user'


class MessageAnonThrottle(AnonRateThrottle):
    scope = 'messages_anon'


def seconds_until_midnight():
    now = timezone.localtime()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


class DailyQuotaThrottle(BaseThrottle):
    """Cap the total number of messages sent per day across all users."""

    def allow_request(self, request, view):
        cap = getattr(settings, 'DAILY_MESSAGE_CAP', 500)
        if DailyQuota.try_consume(cap):
            return True
        raise QuotaExhausted(retry_after=seconds_until_midnight())
