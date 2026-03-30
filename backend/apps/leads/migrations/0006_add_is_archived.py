from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0005_conversation_fk_multitenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='is_archived',
            field=models.BooleanField(default=False),
        ),
    ]
