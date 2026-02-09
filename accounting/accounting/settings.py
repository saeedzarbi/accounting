import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = os.getenv("DEBUG", "True")
# DEBUG = False
STATIC_URL = "static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
ALLOWED_HOSTS = ["*"]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles/")

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https:\/\/.*\.moshaver-amlak\.com$",
    r"^http:\/\/localhost:\d+$",
    r"^http:\/\/127\.0\.0\.1:\d+$",
]
AUTH_USER_MODEL = "users.CustomUser"
INSTALLED_APPS = [
    "corsheaders",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "drf_yasg",
    "ckeditor",
    "num2words",
    "rest_framework",
    "formtools",
    "users",
    "transactions",
    "finance",
]
CSRF_TRUSTED_ORIGINS = [
    "https://*.moshaver-amlak.com",
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:5173",
]

CORS_ALLOW_CREDENTIALS = True
LOGIN_URL = "/login/"
LOGOUT_REDIRECT_URL = "/login/"

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

ROOT_URLCONF = "accounting.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates/"],
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

WSGI_APPLICATION = "accounting.wsgi.application"
SESSION_COOKIE_SAMESITE = "None"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SECURE = True
CORS_ALLOW_CREDENTIALS = True

# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",
#     }
# }

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ]
}

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


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

CKEDITOR_CONFIGS = {
    "default": {
        "height": 800,
        "width": "100%",
        "language": "fa",
        "contentsCss": ["/static/css/fonts.css"],
        "font_names": (
            "BNazanin/BNazanin;"
            "BTitr/BTitr;"
            "IranNastaliq/IranNastaliq;"
            "Tahoma/Tahoma;"
            "Arial/Arial, Helvetica, sans-serif;"
            "Times New Roman/Times New Roman, Times, serif;"
        ),
        "contentsLangDirection": "rtl",
        "pasteFromWordPromptCleanup": True,
        "pasteFromWordRemoveFontStyles": False,
        "pasteFromWordRemoveStyles": False,
        "forcePasteAsPlainText": False,
        "allowedContent": True,
        "removePlugins": "elementspath,resize,flash,iframe",
        "extraPlugins": ",".join(
            [
                "justify",
                "bidi",
                "table",
                "tabletools",
                "colorbutton",
                "colordialog",
                "div",
            ]
        ),
        "toolbar": "Custom",
        "toolbar_Custom": [
            {"name": "document", "items": ["Source", "-", "Print", "Maximize"]},
            {
                "name": "clipboard",
                "items": [
                    "Cut",
                    "Copy",
                    "Paste",
                    "PasteText",
                    "PasteFromWord",
                    "-",
                    "Undo",
                    "Redo",
                ],
            },
            {"name": "editing", "items": ["Find", "Replace", "-", "SelectAll"]},
            {
                "name": "basicstyles",
                "items": ["Bold", "Italic", "Underline", "Strike", "-", "RemoveFormat"],
            },
            {
                "name": "paragraph",
                "items": [
                    "NumberedList",
                    "BulletedList",
                    "-",
                    "Outdent",
                    "Indent",
                    "-",
                    "Blockquote",
                    "-",
                    "JustifyRight",
                    "JustifyCenter",
                    "JustifyLeft",
                    "JustifyBlock",
                    "-",
                    "BidiRtl",
                    "BidiLtr",
                ],
            },
            {"name": "links", "items": ["Link", "Unlink"]},
            {
                "name": "insert",
                "items": ["Table", "HorizontalRule", "SpecialChar", "PageBreak"],
            },
            "/",
            {"name": "styles", "items": ["Styles", "Format", "Font", "FontSize"]},
            {"name": "colors", "items": ["TextColor", "BGColor"]},
        ],
    },
}
