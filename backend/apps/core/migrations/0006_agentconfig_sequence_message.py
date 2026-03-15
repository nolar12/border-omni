from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_agentconfig_bot_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentconfig',
            name='sequence_message',
            field=models.TextField(blank=True, default=''),
        ),
    ]
