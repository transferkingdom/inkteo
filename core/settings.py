"""
Django settings for core project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv('SECRET_KEY', 'TKInkteo3506')

# Debug settings
DEBUG = os.getenv('DEBUG', 'True') == 'True'

# Base URL Settings
BASE_URL = os.getenv('BASE_URL', 'https://inkteo-inkteo.7r1maa.easypanel.host')
if DEBUG:
    BASE_URL = 'http://localhost:8000'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,93.127.217.110,inkteo-inkteo.7r1maa.easypanel.host,127.0.0.1:8000,orders.inkteo.com').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'crispy_forms',
    'crispy_tailwind',

    'accounts.apps.AccountsConfig',
    'dashboard.apps.DashboardConfig',
    'pages.apps.PagesConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
            os.path.join(BASE_DIR, 'templates', 'account'),
            os.path.join(BASE_DIR, 'templates', 'account', 'email'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'core.context_processors.media_url',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Database settings
if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'inkteo_db',
            'USER': 'postgres',
            'PASSWORD': '982286',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'inkteo'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'Heysem35Saint!'),
            'HOST': os.getenv('DB_HOST', 'inkteo_db'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        'OPTIONS': {
            'user_attributes': ('email',),
            'max_similarity': 0.7,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
if DEBUG:
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
    STATICFILES_DIRS = [
        os.path.join(BASE_DIR, 'static')
    ]
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
else:
    STATIC_ROOT = '/etc/easypanel/projects/inkteo/inkteo/volumes/static'
    STATICFILES_DIRS = [
        os.path.join(BASE_DIR, 'static')
    ]
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Media files
MEDIA_URL = '/media/'
if DEBUG:
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
else:
    MEDIA_ROOT = '/etc/easypanel/projects/inkteo/inkteo/volumes/media'

# Ensure media directories exist in both environments
MEDIA_DIRS = [
    os.path.join(MEDIA_ROOT, 'orders/pdfs'),
    os.path.join(MEDIA_ROOT, 'orders/images'),
    os.path.join(MEDIA_ROOT, 'orders/raw_data')
]

# Create directories and set permissions
for dir_path in MEDIA_DIRS:
    try:
        os.makedirs(dir_path, exist_ok=True)
        # Set directory permissions (755 = rwxr-xr-x)
        os.chmod(dir_path, 0o755)
    except Exception as e:
        print(f"Error creating directory {dir_path}: {str(e)}")

# File upload settings
FILE_UPLOAD_PERMISSIONS = 0o644  # rw-r--r--
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755  # rwxr-xr-x
FILE_UPLOAD_MAX_MEMORY_SIZE = 524288000  # 500MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 524288000  # 500MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

# Security Settings
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Security Settings
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication settings
AUTH_USER_MODEL = 'accounts.CustomUser'
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Django-allauth settings
SITE_ID = 1

# Account settings
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_EMAIL_SUBJECT_PREFIX = ''
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_EMAIL_CONFIRMATION_HTML = True
ACCOUNT_EMAIL_CONFIRMATION_HMAC = True

# Redirects
LOGIN_REDIRECT_URL = 'dashboard:home'  # Dashboard ana sayfasına yönlendir
ACCOUNT_LOGOUT_REDIRECT_URL = 'account_login'
LOGIN_URL = 'account_login'
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = 'account_login'
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = 'dashboard:home'

# Rate limits
ACCOUNT_RATE_LIMITS = {
    'login_failed': '5/300m',
    'confirm_email': '3/180m',
    'signup': '5/300m',
}

# Custom messages
ACCOUNT_ERROR_MESSAGES = {
    'invalid_login': 'Invalid email or password. Please try again.',
    'inactive': 'This account is inactive.',
    'email_taken': 'An account already exists with this email address.',
    'password_mismatch': "The two password fields didn't match.",
    'password_too_short': "Password must be at least 8 characters long.",
    'password_too_common': "Password is too common.",
    'password_entirely_numeric': "Password cannot be entirely numeric.",
}

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'sainteagle@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'wtdy jcnq jqqi kmvi')
DEFAULT_FROM_EMAIL = f"Inkteo <{os.environ.get('EMAIL_HOST_USER', 'sainteagle@gmail.com')}>"

# Email template settings
ACCOUNT_EMAIL_CONFIRMATION_TEMPLATE = 'account/email/email_confirmation_message.html'
ACCOUNT_EMAIL_CONFIRMATION_SIGNUP_TEMPLATE = 'account/email/email_confirmation_message.html'

# Crispy Forms settings
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# CSRF settings
CSRF_TRUSTED_ORIGINS = [
    'https://panel.inkteo.com',
    'http://panel.inkteo.com',
    'https://inkteo-inkteo.72xy9m.easypanel.host',
    'http://inkteo-inkteo.72xy9m.easypanel.host'
]

# Development ortamında local URL'leri ekle
if DEBUG:
    CSRF_TRUSTED_ORIGINS.extend([
        'http://localhost:8000',
        'http://127.0.0.1:8000'
    ])

# CSRF Ayarları
CSRF_USE_SESSIONS = True
CSRF_COOKIE_SECURE = False  # Development için False
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Session Ayarları
SESSION_COOKIE_SECURE = False  # Development için False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Logging configuration
if DEBUG:
    # Development ortamı için basit logging
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '[{levelname}] {asctime} {module} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
            },
            'file': {
                'class': 'logging.FileHandler',
                'filename': os.path.join(BASE_DIR, 'django.log'),
                'formatter': 'verbose',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': True,
            },
            'dashboard': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': True,
            },
        },
    }
else:
    # Production ortamı için logging
    LOG_DIR = os.path.join('/etc/easypanel/projects/inkteo/inkteo/volumes/logs')
    if not os.path.exists(LOG_DIR):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            os.chmod(LOG_DIR, 0o755)
        except Exception as e:
            print(f"Error creating log directory: {str(e)}")

    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '[{levelname}] {asctime} {module} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
            },
            'file': {
                'class': 'logging.FileHandler',
                'filename': os.path.join(LOG_DIR, 'django.log'),
                'formatter': 'verbose',
                'mode': 'a',  # Append mode
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': True,
            },
            'dashboard': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': True,
            },
        },
    }

# Allauth settings ekleyin/güncelleyin
ACCOUNT_EMAIL_VERIFICATION_REQUIRED_ON_PASSWORD_CHANGE = False
ACCOUNT_PASSWORD_RESET_VERIFY_EMAIL = False

# Orders specific settings
ORDERS_PDF_DIR = 'orders/pdfs/%Y/%m/%d'
ORDERS_IMAGES_DIR = 'orders/images'
ORDERS_RAW_DATA_DIR = 'orders/raw_data/%Y/%m/%d'

# Dropbox API Settings
DROPBOX_APP_KEY = os.environ.get('DROPBOX_APP_KEY', '6j0fohrnyxu4o17')
DROPBOX_APP_SECRET = os.environ.get('DROPBOX_APP_SECRET', '3p56cepqeng26qs')
if DEBUG:
    DROPBOX_OAUTH_CALLBACK_URL = os.environ.get('DROPBOX_OAUTH_CALLBACK_URL_LOCAL', 'http://localhost:8000/dashboard/settings/dropbox/callback')
else:
    DROPBOX_OAUTH_CALLBACK_URL = os.environ.get('DROPBOX_OAUTH_CALLBACK_URL', 'https://orders.inkteo.com/dashboard/settings/dropbox/callback')

# Form processing settings
DATA_UPLOAD_MAX_MEMORY_SIZE = 524288000  # 500MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 524288000  # 500MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
CSRF_COOKIE_SECURE = False  # Development için False
SESSION_COOKIE_SECURE = False  # Development için False
