from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conversations', '0008_add_draft_status_to_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='messagetemplate',
            name='header_media_url',
            field=models.URLField(
                blank=True,
                max_length=2000,
                help_text='URL padrão de mídia do cabeçalho (imagem/vídeo/documento). Usada como pré-preenchimento no envio.',
            ),
        ),
    ]
