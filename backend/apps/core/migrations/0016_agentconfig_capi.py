from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_add_audio_gallery_media_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentconfig',
            name='meta_pixel_id',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='agentconfig',
            name='meta_capi_token',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='agentconfig',
            name='meta_conversions_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='agentconfig',
            name='meta_test_event_code',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='agentconfig',
            name='send_warm_events',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='agentconfig',
            name='send_hot_events',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='agentconfig',
            name='send_purchases',
            field=models.BooleanField(default=True),
        ),
    ]
