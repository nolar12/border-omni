from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_gallerymedia_description'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gallerymedia',
            name='media_type',
            field=models.CharField(
                max_length=10,
                choices=[('IMAGE', 'Imagem'), ('VIDEO', 'Vídeo'), ('DOCUMENT', 'Documento')],
                default='IMAGE',
            ),
        ),
    ]
