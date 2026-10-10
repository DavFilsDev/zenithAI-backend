from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class MessageUserThrottle(UserRateThrottle):
    scope = 'messages_user'


class MessageAnonThrottle(AnonRateThrottle):
    scope = 'messages_anon'
