"""
تنظیمات اجرای پروژه داخل Docker (ویندوز / لینوکس).
از متغیرهای محیطی .env استفاده می‌کند.
"""
from pathlib import Path

from decouple import config

from .settings import *  # noqa: F401,F403

DEBUG = config('DEBUG', default=True, cast=bool)
SECRET_KEY = config('SECRET_KEY', default=SECRET_KEY)  # noqa: F405

_allowed = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,web')
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(',') if h.strip()]  # noqa: F405

DATA_DIR = Path(config('DATA_DIR', default=str(BASE_DIR / 'data')))  # noqa: F405
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASES = {  # noqa: F405
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATA_DIR / 'db.sqlite3',
        'OPTIONS': {'timeout': 30},
    }
}

MEDIA_ROOT = Path(config('MEDIA_ROOT', default=str(BASE_DIR / 'media')))  # noqa: F405
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

STATIC_ROOT = BASE_DIR / 'staticfiles'  # noqa: F405

SERVE_MEDIA = config('SERVE_MEDIA', default=True, cast=bool)

_csrf = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:8000,http://127.0.0.1:8000',
)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf.split(',') if o.strip()]  # noqa: F405

REDIS_URL = config('REDIS_URL', default='')
if REDIS_URL:
    CACHES = {  # noqa: F405
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'  # noqa: F405
    SESSION_CACHE_ALIAS = 'default'  # noqa: F405
    CELERY_BROKER_URL = REDIS_URL  # noqa: F405
    CELERY_TASK_ALWAYS_EAGER = False  # noqa: F405
else:
    CACHES = {  # noqa: F405
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'tadarokat-docker-cache',
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'  # noqa: F405
    SESSION_CACHE_ALIAS = 'default'  # noqa: F405
    CELERY_TASK_ALWAYS_EAGER = True  # noqa: F405
    CELERY_BROKER_URL = None  # noqa: F405

MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')  # noqa: F405

STORAGES = {  # noqa: F405
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

LOGGING = {  # noqa: F405
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}