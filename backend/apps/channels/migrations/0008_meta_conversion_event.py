import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('channels', '0007_register_quality_periodic_task'),
        ('core', '0016_agentconfig_capi'),
        ('leads', '0011_lead_adfields_leadprofile'),
    ]

    operations = [
        migrations.CreateModel(
            name='MetaConversionEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_name', models.CharField(max_length=50)),
                ('lead_status', models.CharField(blank=True, default='', max_length=20)),
                ('event_id', models.CharField(default=uuid.uuid4, max_length=100, unique=True)),
                ('phone_hash', models.CharField(blank=True, default='', max_length=64)),
                ('campaign_id', models.CharField(blank=True, default='', max_length=100)),
                ('adset_id', models.CharField(blank=True, default='', max_length=100)),
                ('ad_id', models.CharField(blank=True, default='', max_length=100)),
                ('value', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('currency', models.CharField(default='BRL', max_length=3)),
                ('payload', models.JSONField(default=dict)),
                ('response', models.JSONField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[('pending', 'Pendente'), ('sent', 'Enviado'), ('error', 'Erro'), ('skipped', 'Ignorado')],
                    default='pending', max_length=10,
                )),
                ('error_message', models.TextField(blank=True, default='')),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='meta_conversion_events',
                    to='core.organization',
                )),
                ('lead', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='meta_events',
                    to='leads.lead',
                )),
            ],
            options={
                'db_table': 'meta_conversion_events',
                'ordering': ['-created_at'],
            },
        ),
    ]
