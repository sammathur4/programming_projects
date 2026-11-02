"""
Mission 2026 — Django settings.
MySQL via PyMySQL driver (pure python, no libmysqlclient needed).
All secrets configurable via environment; defaults match the local dev setup.
"""
import os
import pymysql

pymysql.install_as_MySQLdb()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-me-in-production-mission2026",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mission2026.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "mission2026.wsgi.application"

# ---------------- MySQL ----------------
if os.environ.get("USE_SQLITE") == "1":
    # Tests run against SQLite so they need no MySQL privileges.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("SQLITE_NAME", ":memory:"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME", "mission2026"),
            "USER": os.environ.get("DB_USER", "mission"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "M1ssion_2026_App!"),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
            "CONN_MAX_AGE": 600,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Vision board (standalone HTML) copied into the project and served read-only.
VISION_BOARD_DIR = os.path.join(BASE_DIR, "vision_board")
# The server-rendered WhatsApp check-in page (standalone HTML, no Flutter).
CHECKIN_BOARD_DIR = os.path.join(BASE_DIR, "checkin_board")

# Flutter web build, served by Django so the app and the API share one origin
# (no CORS, no second server). Point this at mission_app/build/web.
FLUTTER_WEB_DIR = os.environ.get(
    "FLUTTER_WEB_DIR",
    os.path.join(os.path.dirname(BASE_DIR), "mission_app", "build", "web"),
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------- API ----------------
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser", "rest_framework.parsers.FormParser"],
    "DEFAULT_PAGINATION_CLASS": None,
}

# Flutter web / LAN devices — allow all origins for the personal app.
# Tighten this if you ever expose the server publicly.
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = False

# Optional shared-secret API key. Empty = disabled (local use).
# Set MISSION_API_KEY env var and send header X-API-Key from clients to enable.
MISSION_API_KEY = os.environ.get("MISSION_API_KEY", "")
