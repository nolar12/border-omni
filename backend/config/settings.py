import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

_secret = os.getenv('SECRET_KEY')
if not _secret:
    raise RuntimeError('SECRET_KEY não definida. Adicione SECRET_KEY ao arquivo .env')
SECRET_KEY = _secret

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if h.strip()
]

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
]

LOCAL_APPS = [
    'apps.core',
    'apps.leads',
    'apps.conversations',
    'apps.quick_replies',
    'apps.channels',
    'apps.qualifier',
    'apps.rag',
    'apps.contracts',
    'apps.notes',
    'apps.kennel',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

# Diretório do build do frontend React (gerado por ./start.sh build)
_FRONTEND_DIST = BASE_DIR.parent / 'frontend' / 'dist'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ([str(_FRONTEND_DIST)] if _FRONTEND_DIST.exists() else []) + [str(BASE_DIR / 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', 'border_leads'),
        'USER': os.getenv('DB_USER', 'root'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# URL pública base — usada para construir links de mídia acessíveis pelo WhatsApp e Meta.
# Em desenvolvimento: MEDIA_BASE_URL=https://borderomni.ngrok.app
# Em produção: MEDIA_BASE_URL=https://api.bordercolliesul.com.br
MEDIA_BASE_URL = os.getenv('MEDIA_BASE_URL', 'http://localhost:9022').rstrip('/')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# URL pública de um vídeo/foto de ninhada anterior (configuração legada — substituta pelo A/B abaixo).
QUALIFICATION_MEDIA_URL = os.getenv('QUALIFICATION_MEDIA_URL', '')
QUALIFICATION_MEDIA_TYPE = os.getenv('QUALIFICATION_MEDIA_TYPE', 'video')

# A/B test de mídia: 4 variantes sorteadas aleatoriamente para cada novo lead.
# Por padrão usa MEDIA_BASE_URL; sobrescreva individualmente via env se necessário.
_AB_CAPTION_VIDEO = ''
_AB_CAPTION_IMAGE = ''
AB_MEDIA_VARIANTS = {
    'A': {'type': 'video', 'url': os.getenv('AB_MEDIA_URL_A', f'{MEDIA_BASE_URL}/media/ab_test/variant_a.mp4'), 'caption': _AB_CAPTION_VIDEO},
    'B': {'type': 'image', 'url': os.getenv('AB_MEDIA_URL_B', f'{MEDIA_BASE_URL}/media/ab_test/variant_b.png'), 'caption': _AB_CAPTION_IMAGE},
    'C': {'type': 'image', 'url': os.getenv('AB_MEDIA_URL_C', f'{MEDIA_BASE_URL}/media/ab_test/variant_c.png'), 'caption': _AB_CAPTION_IMAGE},
    'D': {'type': 'image', 'url': os.getenv('AB_MEDIA_URL_D', f'{MEDIA_BASE_URL}/media/ab_test/variant_d.png'), 'caption': _AB_CAPTION_IMAGE},
}

# CORS
CORS_ALLOW_ALL_ORIGINS = False
_default_cors = (
    'http://localhost:5173,'
    'http://localhost:3000,'
    'http://localhost:9023,'
    'https://www.bordercolliesul.com.br,'
    'https://bordercolliesul.com.br,'
    'https://app.bordercolliesul.com.br'
)
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv('CORS_ALLOWED_ORIGINS', _default_cors).split(',')
    if o.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        'CSRF_TRUSTED_ORIGINS',
        'https://api.bordercolliesul.com.br,https://admin.bordercolliesul.com.br,https://app.bordercolliesul.com.br'
    ).split(',')
    if o.strip()
]

from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + [
    'ngrok-skip-browser-warning',
]

# DRF
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 30,
}

# JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Supabase — infraestrutura vetorial compartilhada (dados isolados por organization_id)
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', '')

# Logging — apenas console em produção (stdout/stderr capturado pelo CloudWatch)
_log_handlers = ['console']
_log_config: dict = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'apps': {
            'handlers': _log_handlers,
            'level': 'INFO' if not DEBUG else 'DEBUG',
            'propagate': False,
        },
    },
}
if DEBUG:
    _log_config['handlers']['file'] = {  # type: ignore[index]
        'class': 'logging.FileHandler',
        'filename': BASE_DIR / 'border_omni.log',
    }
    _log_config['loggers']['apps']['handlers'] = ['console', 'file']  # type: ignore[index]
LOGGING = _log_config
