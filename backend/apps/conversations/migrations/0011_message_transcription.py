from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conversations', '0010_add_meta_media_handle_to_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='transcription',
            field=models.TextField(blank=True, null=True),
        ),
    ]
