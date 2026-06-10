from django.db import migrations
import apps.channels.encrypted_fields


class Migration(migrations.Migration):
    """
    Altera app_secret e access_token para usar campos criptografados.
    Valores já armazenados permanecem legíveis (decifrado transparente no from_db_value).
    Novos valores escritos após esta migration serão cifrados com prefixo 'enc:'.
    """

    dependencies = [
        ('channels', '0004_channelprovider_quality_rating'),
    ]

    operations = [
        migrations.AlterField(
            model_name='channelprovider',
            name='app_secret',
            field=apps.channels.encrypted_fields.EncryptedCharField(
                blank=True, default='', max_length=500
            ),
        ),
        migrations.AlterField(
            model_name='channelprovider',
            name='access_token',
            field=apps.channels.encrypted_fields.EncryptedTextField(
                blank=True, default=''
            ),
        ),
    ]
