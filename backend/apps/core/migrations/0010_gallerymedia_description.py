from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_gallerymedia'),
    ]

    operations = [
        migrations.AddField(
            model_name='gallerymedia',
            name='description',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='gallerymedia',
            name='file_url',
            field=models.CharField(max_length=2000),
        ),
    ]
