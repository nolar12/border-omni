from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('channels', '0003_channelprovider_app_secret_channelprovider_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='channelprovider',
            name='quality_rating',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
