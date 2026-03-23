import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0010_gallerymedia_description'),
        ('contracts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GenericNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('content', models.TextField(blank=True)),
                ('color', models.CharField(
                    choices=[
                        ('default', 'Padrão'),
                        ('yellow', 'Amarelo'),
                        ('green', 'Verde'),
                        ('blue', 'Azul'),
                        ('pink', 'Rosa'),
                        ('purple', 'Roxo'),
                    ],
                    default='default',
                    max_length=20,
                )),
                ('is_pinned', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='generic_notes',
                    to='core.organization',
                )),
                ('author', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='generic_notes',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'generic_notes',
                'ordering': ['-is_pinned', '-updated_at'],
            },
        ),
    ]
