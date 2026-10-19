import os

from django.core.exceptions import ImproperlyConfigured

from chat.providers.factory import validate_config

from .base import *  # noqa: F401,F403

DEBUG = False

if not SECRET_KEY or 'django-insecure' in SECRET_KEY.lower():
    raise ImproperlyConfigured('SECRET_KEY must be set to a non-default value in production.')

if not DATABASES['default'].get('PASSWORD'):
    raise ImproperlyConfigured('DB_PASSWORD must be set in production.')

if not os.getenv('CORS_ALLOWED_ORIGINS'):
    raise ImproperlyConfigured('CORS_ALLOWED_ORIGINS must be set in production.')

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

validate_config()
