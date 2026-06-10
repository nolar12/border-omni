from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('channels', '0005_encrypt_tokens'),
    ]

    operations = [
        migrations.AddField(
            model_name='channelprovider',
            name='quality_synced_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='QualityRatingEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('previous_rating', models.CharField(blank=True, default='', max_length=20)),
                ('new_rating', models.CharField(max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('channel', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='quality_events',
                    to='channels.channelprovider',
                )),
            ],
            options={
                'db_table': 'channels_qualityratingevent',
                'ordering': ['-created_at'],
            },
        ),
    ]
