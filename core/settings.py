"""
IIAP OM - Core Settings
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

import os
import secrets

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    # Use fallback secure key or generate a unique random one on start
    SECRET_KEY = "django-insecure-IIAP-pm-change-this-in-production-!@#$%^&*()"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Custom apps
    "accounts",
    "tasks",
    "notes",
    "bugs",
    "events",
    "notifications",
    "testcases",
    "files",
    "finance",
    "telescope",
    "resource_hub",

    # Inventory Apps
    "inventory",
    "products",
    "stock",
    "audit",
    "reports",
    "procurement",
    "dashboard",
    "chat",
    "channels",
]

INTERNAL_IPS = [
    "127.0.0.1",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.InventoryAccessMiddleware",
]

if DEBUG:
    INSTALLED_APPS.append("debug_toolbar")
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "inventory.context_processors.inventory_notifications_count",
                "tasks.context_processors.notifications_count",
                "tasks.context_processors.notes_count",
                "tasks.context_processors.system_settings",
                "tasks.context_processors.sidebar_projects",
                "resource_hub.context_processors.git_status",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 20,
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
# Ensure static directory exists to prevent W004 warning
(BASE_DIR / "static").mkdir(exist_ok=True)
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Message storage
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# File Upload Settings
DATA_UPLOAD_MAX_NUMBER_FILES = None
DATA_UPLOAD_MAX_MEMORY_SIZE = 10737418240  # 10GB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10737418240  # 10GB

# Dynamic CSRF Trusted Origins for local network and development
import socket
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://192.168.100.175:8000",
    "http://192.168.100.175",
]
try:
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    CSRF_TRUSTED_ORIGINS.extend([
        f"http://{local_ip}:8000",
        f"http://{local_ip}",
    ])
except Exception:
    pass

# Security Enhancements
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 14400 # Session expires after 4 hours of inactivity


