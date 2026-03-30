from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_add_phone_to_userprofile'),
    ]

    operations = [
        migrations.CreateModel(
            name='GalleryMedia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=255)),
                ('file_url', models.URLField(max_length=2000)),
                ('mime_type', models.CharField(blank=True, max_length=100)),
                ('media_type', models.CharField(choices=[('IMAGE', 'Imagem'), ('VIDEO', 'Vídeo')], default='IMAGE', max_length=10)),
                ('size_bytes', models.PositiveBigIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gallery_media', to='core.organization')),
            ],
            options={
                'db_table': 'gallery_media',
                'ordering': ['-created_at'],
            },
        ),
    ]
