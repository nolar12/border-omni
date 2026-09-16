from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('advertising', '0008_register_proactive_review_periodic_task'),
    ]

    operations = [
        migrations.AddField(
            model_name='adcampaignplan',
            name='ad_groups',
            field=models.JSONField(default=list, blank=True),
        ),
    ]
