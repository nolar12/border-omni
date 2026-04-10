from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_gallerymedia_document_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentconfig',
            name='link_message',
            field=models.TextField(blank=True, default=''),
        ),
    ]
