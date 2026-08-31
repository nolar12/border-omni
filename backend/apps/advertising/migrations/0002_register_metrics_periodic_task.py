from django.db import migrations


def create_periodic_task(apps, schema_editor):
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=6,
        period='hours',
    )

    PeriodicTask.objects.get_or_create(
        name='sync-ad-campaign-metrics',
        defaults={
            'task': 'apps.advertising.tasks.sync_all_campaign_metrics',
            'interval': schedule,
            'enabled': True,
        },
    )


def remove_periodic_task(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(name='sync-ad-campaign-metrics').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('advertising', '0001_initial'),
        ('django_celery_beat', '0019_alter_periodictasks_options'),
    ]

    operations = [
        migrations.RunPython(create_periodic_task, remove_periodic_task),
    ]
