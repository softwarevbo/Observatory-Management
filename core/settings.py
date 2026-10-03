"""
IIAP OM - Core Settings (AWS / Cloud Ready)
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Security Settings
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-IIAP-pm-change-this-in-production-!@#$%^&*()")

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() == "true"

# Host configuration (Default to allow all in dev, override via env in AWS production)
# ALLOWED_HOSTS = ["54.xxx.xxx.xxx", "yourdomain.com", "localhost", "127.0.0.1"]

ALLOWED_HOSTS = ["127.0.0.1"]

# Application definition
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Core & Management Apps
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

# Database Settings
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 20,
        },
    }
}

# ------------------------------------------------------------------------------
# AWS RDS / PostgreSQL Configuration (Uncomment this block when deploying to AWS)
# Required Package: pip install psycopg2-binary
# ------------------------------------------------------------------------------
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": os.environ.get("DB_NAME", "iiap_db"),
#         "USER": os.environ.get("DB_USER", "postgres"),
#         "PASSWORD": os.environ.get("DB_PASSWORD", "your_aws_db_password"),
#         "HOST": os.environ.get("DB_HOST", "your-rds-endpoint.xxxxxx.us-east-1.rds.amazonaws.com"), # or AWS EC2 IP if Postgres runs on EC2
#         "PORT": os.environ.get("DB_PORT", "5432"),
#         "OPTIONS": {
#             "connect_timeout": 10,
#         },
#     }
# }

# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
(BASE_DIR / "static").mkdir(exist_ok=True)
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# Authentication URLs
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Sessions and Messages
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 14400  # Session expires after 4 hours of inactivity

# ==============================================================================
# AWS CLOUD - CSRF TRUSTED ORIGINS CONFIGURATION
# ==============================================================================
# Option A: Set via environment variable CSRF_TRUSTED_ORIGINS="http://54.x.x.x,http://yourdomain.com"
# Option B: Or replace the list below directly with your AWS Public IP / Domain, e.g.:
# CSRF_TRUSTED_ORIGINS = [
#     "http://YOUR_AWS_EC2_PUBLIC_IP",
#     "http://YOUR_AWS_EC2_PUBLIC_IP:8000",
#     "https://yourdomain.com",
# ]
# ==============================================================================
csrf_origins_env = os.environ.get(
    "CSRF_TRUSTED_ORIGINS",
    "http://127.0.0.1:8000,http://localhost:8000,http://0.0.0.0:8000,http://localhost,http://127.0.0.1"
)
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins_env.split(",") if origin.strip()]

# File Upload Settings
DATA_UPLOAD_MAX_NUMBER_FILES = None
DATA_UPLOAD_MAX_MEMORY_SIZE = 10737418240  # 10GB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10737418240  # 10GB

# Security Enhancements
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
