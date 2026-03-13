from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_agentconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentconfig',
            name='cordiality_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='agentconfig',
            name='cordiality_use_ai',
            field=models.BooleanField(default=False),
        ),
    ]
