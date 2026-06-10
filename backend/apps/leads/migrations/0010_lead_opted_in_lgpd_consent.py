from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0009_alter_lead_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='opted_in',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='lead',
            name='lgpd_consent',
            field=models.BooleanField(default=False),
        ),
    ]
