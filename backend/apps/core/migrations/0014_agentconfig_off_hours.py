from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_agentconfig_conversation_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentconfig',
            name='off_hours_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='agentconfig',
            name='off_hours_start',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='agentconfig',
            name='off_hours_end',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='agentconfig',
            name='off_hours_message',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='agentconfig',
            name='off_hours_timezone',
            field=models.CharField(blank=True, default='America/Sao_Paulo', max_length=60),
        ),
    ]
