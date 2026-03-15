from django.db import migrations, models
import django.db.models.deletion
import apps.core.models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_agentconfig_sequence_message'),
    ]

    operations = [
        migrations.CreateModel(
            name='InitialMessageMedia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to=apps.core.models._media_upload_path)),
                ('media_type', models.CharField(choices=[('image', 'Imagem'), ('video', 'Vídeo')], default='image', max_length=10)),
                ('original_name', models.CharField(blank=True, max_length=255)),
                ('order', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('agent_config', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='initial_media',
                    to='core.agentconfig',
                )),
            ],
            options={
                'db_table': 'initial_message_media',
                'ordering': ['order', 'created_at'],
            },
        ),
    ]
