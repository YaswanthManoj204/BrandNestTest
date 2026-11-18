"""
Django settings for BrandNest project.
"""

from pathlib import Path
import importlib.util
import os
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def _csv_env(name):
    raw = os.environ.get(name, '')
    return [item.strip() for item in raw.split(',') if item.strip()]


# Environment detection: supports local development and Vercel serverless production
IS_VERCEL = bool(os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV'))
DJANGO_ENV = os.environ.get('DJANGO_ENV', 'production' if IS_VERCEL else 'development').lower()
IS_PRODUCTION = IS_VERCEL or DJANGO_ENV == 'production'

# SECURITY WARNING: don't run with debug turned on in production!
# Never enable DEBUG automatically on Vercel; default to False in production.
if IS_VERCEL:
    DEBUG = False
elif IS_PRODUCTION:
    DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')
else:
    DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

# SECURITY WARNING: keep the secret key used in production secret!
_DEV_SECRET_KEY = 'django-insecure-brandnest-platform-core-key-2026'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or ('' if IS_PRODUCTION else _DEV_SECRET_KEY)
if IS_PRODUCTION and (not SECRET_KEY or SECRET_KEY.startswith('django-insecure-')):
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY must be set to a strong non-insecure value in production.'
    )
if not SECRET_KEY:
    SECRET_KEY = _DEV_SECRET_KEY


_env_hosts = _csv_env('ALLOWED_HOSTS')
if not IS_PRODUCTION and DEBUG and not _env_hosts:
    ALLOWED_HOSTS = ['*']
else:
    ALLOWED_HOSTS = list(_env_hosts)
    if IS_VERCEL or IS_PRODUCTION:
        if '.vercel.app' not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append('.vercel.app')
        for _vercel_host_var in ('VERCEL_URL', 'VERCEL_BRANCH_URL', 'VERCEL_PROJECT_PRODUCTION_URL'):
            _vercel_host = os.environ.get(_vercel_host_var, '').strip()
            if _vercel_host and _vercel_host not in ALLOWED_HOSTS:
                ALLOWED_HOSTS.append(_vercel_host)
    if not IS_PRODUCTION:
        for _local_host in ('127.0.0.1', 'localhost'):
            if _local_host not in ALLOWED_HOSTS:
                ALLOWED_HOSTS.append(_local_host)

CSRF_TRUSTED_ORIGINS = _csv_env('CSRF_TRUSTED_ORIGINS')
if IS_VERCEL or IS_PRODUCTION:
    if 'https://*.vercel.app' not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append('https://*.vercel.app')
    for _vercel_host_var in ('VERCEL_URL', 'VERCEL_BRANCH_URL', 'VERCEL_PROJECT_PRODUCTION_URL'):
        _vercel_host = os.environ.get(_vercel_host_var, '').strip()
        if _vercel_host:
            _origin = f'https://{_vercel_host}'
            if _origin not in CSRF_TRUSTED_ORIGINS:
                CSRF_TRUSTED_ORIGINS.append(_origin)
    for _host in ALLOWED_HOSTS:
        _clean_host = _host.lstrip('.')
        if _clean_host and _clean_host not in ('*', '127.0.0.1', 'localhost', '0.0.0.0'):
            _origin = f'https://*.{_clean_host}' if _host.startswith('.') else f'https://{_host}'
            if _origin not in CSRF_TRUSTED_ORIGINS:
                CSRF_TRUSTED_ORIGINS.append(_origin)

# Application definition
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party packages
    'rest_framework',
    'corsheaders',

    # BrandNest Core Apps
    'apps.domains',
    'apps.cards',
    'apps.websites',
    'apps.api',
    'apps.frontend',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    *(
        ['whitenoise.middleware.WhiteNoiseMiddleware']
        if (not DEBUG or importlib.util.find_spec('whitenoise'))
        else []
    ),
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'

# Database configuration:
# - Local development defaults to existing SQLite when no PostgreSQL config is set.
# - Production uses Neon PostgreSQL via DATABASE_URL (with SSL and serverless CONN_MAX_AGE=0),
#   and refuses to silently fall back to SQLite.
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if DATABASE_URL:
    import dj_database_url

    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.environ.get('DB_CONN_MAX_AGE', '0')),
            ssl_require=os.environ.get('DB_SSL_REQUIRE', 'True').lower() in ('true', '1', 'yes'),
        )
    }
elif os.environ.get('DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'brandnest_db'),
            'USER': os.environ.get('DB_USER', 'brandnest_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '0')),
            'OPTIONS': {
                'sslmode': os.environ.get('DB_SSLMODE', 'require' if IS_PRODUCTION else 'prefer'),
            },
        }
    }
elif IS_PRODUCTION:
    raise ImproperlyConfigured(
        'DATABASE_URL (or DB_NAME) must be configured in production; SQLite fallback is disabled.'
    )
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files (User uploads: logos, profile pictures, banners, documents)
# Uses Cloudflare R2 (S3-compatible) when R2 environment variables are configured;
# defaults to local backend/media/ filesystem storage in local development.
USE_R2_STORAGE = all([
    os.environ.get('AWS_STORAGE_BUCKET_NAME'),
    os.environ.get('AWS_S3_ENDPOINT_URL'),
    os.environ.get('AWS_ACCESS_KEY_ID'),
    os.environ.get('AWS_SECRET_ACCESS_KEY'),
])

if USE_R2_STORAGE:
    INSTALLED_APPS.append('storages')
    _r2_custom_domain = os.environ.get('AWS_S3_CUSTOM_DOMAIN', '').strip() or None
    _r2_options = {
        'access_key': os.environ['AWS_ACCESS_KEY_ID'],
        'secret_key': os.environ['AWS_SECRET_ACCESS_KEY'],
        'bucket_name': os.environ['AWS_STORAGE_BUCKET_NAME'],
        'endpoint_url': os.environ['AWS_S3_ENDPOINT_URL'],
        'region_name': os.environ.get('AWS_S3_REGION_NAME', 'auto'),
        'signature_version': 's3v4',
        'default_acl': None,
        'file_overwrite': False,
        'querystring_auth': not bool(_r2_custom_domain),
    }
    if _r2_custom_domain:
        _r2_options['custom_domain'] = _r2_custom_domain
        MEDIA_URL = f'https://{_r2_custom_domain}/'
    else:
        MEDIA_URL = f"{os.environ['AWS_S3_ENDPOINT_URL'].rstrip('/')}/{os.environ['AWS_STORAGE_BUCKET_NAME']}/"

    _default_storage_config = {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': _r2_options,
    }
else:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    _default_storage_config = {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    }

STORAGES = {
    'default': _default_storage_config,
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
            if DEBUG
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# CORS settings for API consumption
_cors_env_origins = _csv_env('CORS_ALLOWED_ORIGINS')
if not IS_PRODUCTION and DEBUG and not _cors_env_origins:
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = False
else:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = list(_cors_env_origins)
    for _origin in CSRF_TRUSTED_ORIGINS:
        if '*' not in _origin and _origin not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(_origin)
    if IS_VERCEL or IS_PRODUCTION:
        CORS_ALLOWED_ORIGIN_REGEXES = [r'^https://.*\.vercel\.app$']
    CORS_ALLOW_CREDENTIALS = True

# Allow iframe embedding for same-origin builder/template previews
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Production security hardening (conditionally applied when DEBUG is disabled)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 'yes')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Platform Domain Settings
PLATFORM_BASE_DOMAIN = os.environ.get('PLATFORM_BASE_DOMAIN', 'sites.brandnest.local')

# Jazzmin SaaS Super Admin Settings
JAZZMIN_SETTINGS = {
    "site_title": "BrandNest Admin",
    "site_header": "BrandNest SaaS",
    "site_brand": "BrandNest Admin",
    "site_logo": None,
    "login_logo": None,
    "login_logo_dark": None,
    "site_logo_classes": "img-circle",
    "site_icon": None,
    "welcome_sign": "Welcome to BrandNest SaaS Control Center",
    "copyright": "BrandNest Technologies Ltd",
    "search_model": ["cards.BusinessCard", "websites.Website", "auth.User"],
    "user_avatar": None,
    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Create Card", "url": "/card/create/", "new_window": True},
        {"name": "Public Landing", "url": "/", "new_window": True},
    ],
    "usermenu_links": [
        {"name": "BrandNest Platform", "url": "/", "new_window": True},
        {"model": "auth.user"},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": ["cards", "websites", "domains", "auth"],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user-shield",
        "auth.Group": "fas fa-users",
        "cards.BusinessCard": "fas fa-id-card",
        "websites.Website": "fas fa-globe",
        "websites.Industry": "fas fa-briefcase",
        "websites.WebsitePage": "fas fa-file-alt",
        "websites.ContactSubmission": "fas fa-envelope-open-text",
        "domains.Domain": "fas fa-network-wired",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "navbar": "navbar-dark navbar-primary",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "default_theme_mode": "auto",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/overview/'
LOGOUT_REDIRECT_URL = '/login/'
