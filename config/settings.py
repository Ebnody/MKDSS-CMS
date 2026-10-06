from pathlib import Path
import os
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TESTING = any(arg == "test" or arg.startswith("test:") for arg in sys.argv[1:])
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY and TESTING:
    # Test-only key so the clean-install test suite does not require a production .env file.
    SECRET_KEY = "mkdss-test-only-secret-key-do-not-use-in-production"
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required. Copy .env.example to .env and set a strong secret.")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [x.strip() for x in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if x.strip()]
CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if x.strip()]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles", "compliance.apps.ComplianceConfig",
]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
              "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
              "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware",
              "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND":"django.template.backends.django.DjangoTemplates", "DIRS":[BASE_DIR/"templates"], "APP_DIRS":True,
              "OPTIONS":{"context_processors":["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "compliance.context_processors.notifications"]}}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default":{"ENGINE":"django.db.backends.sqlite3","NAME":BASE_DIR/"db.sqlite3","OPTIONS":{"timeout":30}}}
AUTH_PASSWORD_VALIDATORS = [{"NAME":"django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
                            {"NAME":"django.contrib.auth.password_validation.MinimumLengthValidator","OPTIONS":{"min_length":10}},
                            {"NAME":"django.contrib.auth.password_validation.CommonPasswordValidator"}]
LANGUAGE_CODE = "en-us"; TIME_ZONE = "Africa/Addis_Ababa"; USE_I18N = True; USE_TZ = True
STATIC_URL = "/static/"; STATIC_ROOT = BASE_DIR/"staticfiles"; STATICFILES_DIRS = [BASE_DIR/"static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
MEDIA_ROOT = BASE_DIR/"data"; MEDIA_URL = "/media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/login/"; LOGIN_REDIRECT_URL = "/"; LOGOUT_REDIRECT_URL = "/login/"
SECURE_CONTENT_TYPE_NOSNIFF = True; X_FRAME_OPTIONS = "SAMEORIGIN"; SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True; CSRF_COOKIE_HTTPONLY = True
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = (int(os.getenv("MAX_UPLOAD_MB", "50")) + 5) * 1024 * 1024
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
LIBREOFFICE_PATH = os.getenv("LIBREOFFICE_PATH", "soffice")
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "False").lower() == "true"
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if os.getenv("DJANGO_TRUST_PROXY", "False").lower() == "true" else None

LOGGING = {"version":1,"disable_existing_loggers":False,"handlers":{"console":{"class":"logging.StreamHandler"}},
           "loggers":{"compliance":{"handlers":["console"],"level":"INFO"}}}
