import os
import sys
from pathlib import Path

import dj_database_url
from django.utils.translation import gettext_lazy as _
from environs import Env

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = Env()
env.read_env()

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env.str("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

# CORS header config
CORS_ALLOW_ALL_ORIGINS = env.bool("DEBUG")
# CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")

# Application definition

INSTALLED_APPS = [
    "admin_interface",
    "colorfield",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

LOCAL_APPS = [
    "apps.account",
    "apps.resume",
    "apps.settings",
    "apps.exam",
    "apps.public",
    "apps.project",
    "apps.community",
    'apps.comments',
]

EXTERNAL_APPS = [
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "rest_framework_simplejwt",
]

INSTALLED_APPS += LOCAL_APPS + EXTERNAL_APPS


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "conf.urls"

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

WSGI_APPLICATION = "conf.wsgi.application"

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

if env.bool("SQLITE"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

else:
    DATABASES = {"default": dj_database_url.config(default=os.getenv("DATABASE_URL"))}

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = "fa-IR"

LANGUAGES = (("fa", _("Persian")),)

TIME_ZONE = "Asia/Tehran"
USE_TZ = True

USE_I18N = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = "static/"

# Media files
MEDIA_URL = "api-media/"
MEDIA_ROOT = os.path.join(BASE_DIR, MEDIA_URL)

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "account.User"

from conf.apps_settings.drf import REST_FRAMEWORK
from conf.apps_settings.drf import SPECTACULAR_SETTINGS

if DEBUG:
    SPECTACULAR_SETTINGS.setdefault("TITLE", "Rahisho API (DEV)")
    SPECTACULAR_SETTINGS.setdefault(
        "DESCRIPTION",
        "⚠️ **Development Mode** — The “DEV Tools” endpoints are for local testing only.",
    )
    # Ensure the tag shows with a short description
    tags = SPECTACULAR_SETTINGS.get("TAGS", [])
    tags.append({"name": "DEV Tools", "description": "Development-only helpers (visible in DEBUG)."})
    SPECTACULAR_SETTINGS["TAGS"] = tags

from conf.apps_settings.sso import (
    CLIENT_ID,
    CLIENT_SECRET,
    CODE_CHALLENGE,
    CODE_VERIFIER,
    REDIRECT_URI,
    SSO_BASE_URL,
)

IS_TEST = "test" in sys.argv

X_FRAME_OPTIONS = "SAMEORIGIN"
SILENCED_SYSTEM_CHECKS = ["security.W019"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env.str("REDIS"),
        "TIMEOUT": 300,
    }
}

# تنظیمات مخصوص سیستم نظرات
COMMENTS_SETTINGS = {
    'MIN_CONTENT_LENGTH': 5,
    'MAX_CONTENT_LENGTH': 2000,
    'EDIT_TIME_LIMIT': 900,  # 15 minutes in seconds
    'AUTO_APPROVE_OLD_COMMENTS': True,
    'OLD_COMMENT_THRESHOLD_DAYS': 7,
    'CACHE_TIMEOUT': 300,  # 5 minutes
    'ENABLE_EMAIL_NOTIFICATIONS': False,  # Future feature
    'MAX_REPLY_DEPTH': 1,  # Only one level of replies
    'PROFANITY_FILTER_ENABLED': False,  # Future feature
    }

