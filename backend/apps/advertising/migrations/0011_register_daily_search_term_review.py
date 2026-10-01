from django.db import migrations

TASK_NAME = 'daily-ad-search-term-review'


def create_periodic_task(apps, schema_editor):
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    schedule, _ = IntervalSchedule.objects.get_or_create(every=1, period='days')
    PeriodicTask.objects.get_or_create(
        name=TASK_NAME,
        defaults={
            'task': 'apps.advertising.tasks.daily_search_term_review',
            'interval': schedule,
            'enabled': True,
        },
    )


def remove_periodic_task(apps, schema_editor):
    apps.get_model('django_celery_beat', 'PeriodicTask').objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('advertising', '0010_widen_region_field'),
        ('django_celery_beat', '0019_alter_periodictasks_options'),
    ]

    operations = [
        migrations.RunPython(create_periodic_task, remove_periodic_task),
    ]
