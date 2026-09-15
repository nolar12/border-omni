from django.db import migrations


def create_periodic_task(apps, schema_editor):
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=7,
        period='days',
    )

    PeriodicTask.objects.get_or_create(
        name='run-proactive-ad-campaign-reviews',
        defaults={
            'task': 'apps.advertising.tasks.run_proactive_campaign_reviews',
            'interval': schedule,
            'enabled': True,
        },
    )


def remove_periodic_task(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(name='run-proactive-ad-campaign-reviews').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('advertising', '0007_adchatmessage_is_proactive_and_more'),
        ('django_celery_beat', '0019_alter_periodictasks_options'),
    ]

    operations = [
        migrations.RunPython(create_periodic_task, remove_periodic_task),
    ]
