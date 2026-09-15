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

# Testes nunca devem poder chamar a API real do Google Ads, independentemente
# do que estiver configurado no .env local (que pode estar em modo "live" para
# testes manuais). Casos que precisam exercitar o caminho "ligado" usam
# @override_settings explicitamente.
GOOGLE_ADS_ENABLED = False
GOOGLE_ADS_DRY_RUN = True
