"""
Campos Django que criptografam o valor em repouso usando Fernet (AES-128-CBC + HMAC).
Requer FIELD_ENCRYPTION_KEY no settings (gerar com Fernet.generate_key()).
Se a chave não estiver configurada, os dados são armazenados em texto plano
(compatibilidade com ambientes sem a variável definida).
"""
from django.db import models
from django.conf import settings


def _get_fernet():
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', '')
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedTextField(models.TextField):
    """TextField que cifra antes de salvar e decifra ao ler."""

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        f = _get_fernet()
        if f is None:
            return value
        if value.startswith('enc:'):
            try:
                return f.decrypt(value[4:].encode()).decode()
            except Exception:
                return value
        return value

    def to_python(self, value):
        return value

    def get_prep_value(self, value):
        if not value:
            return value
        f = _get_fernet()
        if f is None:
            return value
        if value.startswith('enc:'):
            return value
        return 'enc:' + f.encrypt(value.encode()).decode()


class EncryptedCharField(models.CharField):
    """CharField que cifra antes de salvar e decifra ao ler."""

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        f = _get_fernet()
        if f is None:
            return value
        if value.startswith('enc:'):
            try:
                return f.decrypt(value[4:].encode()).decode()
            except Exception:
                return value
        return value

    def to_python(self, value):
        return value

    def get_prep_value(self, value):
        if not value:
            return value
        f = _get_fernet()
        if f is None:
            return value
        if value.startswith('enc:'):
            return value
        return 'enc:' + f.encrypt(value.encode()).decode()
