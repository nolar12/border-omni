from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_agentconfig_cordiality'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentconfig',
            name='bot_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='agentconfig',
            name='initial_message',
            field=models.TextField(blank=True, default=''),
        ),
    ]
