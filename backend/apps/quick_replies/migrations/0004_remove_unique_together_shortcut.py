from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('quick_replies', '0003_quickreplycategory_and_new_fields'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='quickreply',
            unique_together=set(),
        ),
    ]
