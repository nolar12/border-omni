"""
Settings de teste local — roda a suíte contra SQLite em memória em vez do MySQL de
produção (settings.py aponta para o RDS real via .env). Uso:

    DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test apps.advertising
"""
from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
