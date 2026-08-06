# JOYLASHTIRISH MANZILI: ACADEMY_BACK/config/settings.py

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = True
ALLOWED_HOSTS = ["globallogistic.ecorise.uz", "127.0.0.1", "localhost", "45.92.173.65"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "django_celery_beat",
    "corsheaders",
    "users",
    "subscriptions",
    "gifts",
    "content",
    "cms",
    "growth",
    "broadcast",
    "api",
    "admin_api",
    "bot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# DATABASES = {
#     "default": {
#         "ENGINE": os.environ.get("DJANGO_DB_ENGINE", "django.db.backends.postgresql"),
#         "NAME": os.environ.get("POSTGRES_DB", "davron_academy"),
#         "USER": os.environ.get("POSTGRES_USER", "postgres"),
#         "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
#         "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
#         "PORT": os.environ.get("POSTGRES_PORT", "5432"),
#     }
# }


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    # Diqqat: bu default'lar faqat `api` (mini app) endpointlari uchun.
    # `admin_api` (admin panel) ViewSet'lari o'z authentication/permission
    # klasslarini AdminModelViewSet orqali alohida belgilaydi (Token/Session + is_staff).
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.TelegramInitDataAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "admin_api.pagination.AdminPagination",
    "PAGE_SIZE": 20,
}

# ---- Loyihaga xos sozlamalar (.env orqali beriladi) ----
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
# aiogram tashqarisida (masalan payment_form_service.py, oddiy Django view) botga qaytish
# havolasini qurish uchun — @get_me() async chaqiruv talab qiladi, shu yerda statik saqlanadi.
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "")
MINI_APP_BASE_URL = os.environ.get("MINI_APP_BASE_URL", "https://app.turdievakademiyasi.uz")
PAYMENT_BASE_URL = os.environ.get("PAYMENT_BASE_URL", "https://pay.turdievakademiyasi.uz")

PAYME_MERCHANT_ID = os.environ.get("PAYME_MERCHANT_ID", "")
PAYME_SECRET_KEY = os.environ.get("PAYME_SECRET_KEY", "")
# Merchant API (JSON-RPC) manzili — Payme hosted checkout EMAS, biz o'z formamizdan
# (PAYMENT_BASE_URL) to'g'ridan-to'g'ri shu API'ga cards.*/receipts.* chaqiramiz.
PAYME_API_URL = os.environ.get("PAYME_API_URL", "https://checkout.paycom.uz/api")

TRIBUTE_API_KEY = os.environ.get("TRIBUTE_API_KEY", "")
TRIBUTE_WEBHOOK_SECRET = os.environ.get("TRIBUTE_WEBHOOK_SECRET", "")

ESKIZ_EMAIL = os.environ.get("ESKIZ_EMAIL", "")
ESKIZ_PASSWORD = os.environ.get("ESKIZ_PASSWORD", "")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    }
}

# ---- Celery ----
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TIMEZONE = TIME_ZONE


# ---- CORS (admin panel frontend, e.g. Vite dev server) ----
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")
CORS_ALLOW_CREDENTIALS = True


CSRF_TRUSTED_ORIGINS = [
    "https://ddfb-188-113-209-181.ngrok-free.app", "https://globallogistic.ecorise.uz"
]

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

