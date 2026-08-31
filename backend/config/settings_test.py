"""
Settings para rodar a suíte de testes localmente sem depender de privilégio de
CREATE DATABASE no MySQL gerenciado (RDS) usado em desenvolvimento/produção.
Uso: DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test
"""
from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
