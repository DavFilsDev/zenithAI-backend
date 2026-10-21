import os
from datetime import timedelta
from pathlib import Path

import dotenv

dotenv.load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-change-in-production')

DEBUG = False

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'corsheaders',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',

    'users',
    'chat',
    'health',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

DB_PASSWORD = os.getenv('DB_PASSWORD')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'zenith_ai_db'),
        'USER': os.getenv('DB_USER', 'manager_zenith_ai'),
        'PASSWORD': DB_PASSWORD,
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# DRF throttling keeps its state here; LocMemCache is fine for a single instance.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'zenith-ai',
    }
}

CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5173').split(',')

CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'backend.pagination.StandardResultsSetPagination',
    'EXCEPTION_HANDLER': 'backend.exceptions.exception_handler',
    'DEFAULT_THROTTLE_RATES': {
        'messages_user': '10/min',
        'messages_anon': '5/min',
    },
}

DAILY_MESSAGE_CAP = int(os.getenv('DAILY_MESSAGE_CAP', '500'))

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Zenith AI API',
    'DESCRIPTION': '''
    Zenith AI is a chatbot platform API built with Django REST Framework.

    ## Features
    - User authentication with JWT
    - Conversation management
    - Message history

    ## Authentication
    Most endpoints require JWT authentication via Bearer token.
    Obtain tokens via `/api/v1/auth/token/` endpoint.
    ''',
    'VERSION': '1.0.0',
    'SERVERS': [{'url': '/api/v1'}],
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,

    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
    },

    'TAGS': [
        {'name': 'Authentication', 'description': 'User registration and login'},
        {'name': 'Users', 'description': 'User profile management'},
        {'name': 'Chat', 'description': 'Conversations and messages'},
    ],
}

AUTH_USER_MODEL = 'users.User'

LLM_SYSTEM_PROMPT = """You are a helpful AI assistant specialized in programming and software development.
When answering coding questions:
- Provide clear, well-commented code examples
- Explain *why* the code works, not just what it does
- Point out common mistakes and how to avoid them
- Suggest best practices for the language or framework being used
Be concise, friendly, and educational in tone."""

LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'gemini')
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'gemini-2.5-flash')

LLM_FALLBACK_PROVIDER = os.getenv('LLM_FALLBACK_PROVIDER', '')
LLM_FALLBACK_API_KEY = os.getenv('LLM_FALLBACK_API_KEY', '')
LLM_FALLBACK_MODEL = os.getenv('LLM_FALLBACK_MODEL', '')

LLM_PROMPT_BUDGET = int(os.getenv('LLM_PROMPT_BUDGET', '4000'))

LLM_BREAKER_THRESHOLD = int(os.getenv('LLM_BREAKER_THRESHOLD', '5'))
LLM_BREAKER_COOLDOWN = int(os.getenv('LLM_BREAKER_COOLDOWN', '60'))
