from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0010_lead_opted_in_lgpd_consent'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='ad_referral',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='lead',
            name='ctwa_clid',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.CreateModel(
            name='LeadProfile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('intencao_uso', models.CharField(
                    choices=[
                        ('familia_companhia', 'Família/Companhia'),
                        ('trabalho_rural', 'Trabalho Rural'),
                        ('reproducao', 'Reprodução'),
                        ('curiosidade', 'Curiosidade'),
                        ('indefinido', 'Indefinido'),
                    ],
                    default='indefinido', max_length=30,
                )),
                ('perfil_localizacao', models.CharField(
                    choices=[
                        ('capital_grande_centro', 'Capital/Grande Centro'),
                        ('cidade_media', 'Cidade Média'),
                        ('rural_interior', 'Rural/Interior'),
                        ('outro_estado_distante', 'Outro Estado/Distante'),
                        ('indefinido', 'Indefinido'),
                    ],
                    default='indefinido', max_length=30,
                )),
                ('potencial_compra', models.CharField(
                    choices=[
                        ('alto', 'Alto'),
                        ('medio', 'Médio'),
                        ('baixo', 'Baixo'),
                        ('indefinido', 'Indefinido'),
                    ],
                    default='indefinido', max_length=15,
                )),
                ('sensibilidade_preco', models.CharField(
                    choices=[
                        ('baixa', 'Baixa'),
                        ('media', 'Média'),
                        ('alta', 'Alta'),
                        ('indefinido', 'Indefinido'),
                    ],
                    default='indefinido', max_length=15,
                )),
                ('urgencia', models.CharField(
                    choices=[
                        ('imediata', 'Imediata'),
                        ('curto_prazo', 'Curto Prazo'),
                        ('pesquisando', 'Pesquisando'),
                        ('indefinido', 'Indefinido'),
                    ],
                    default='indefinido', max_length=20,
                )),
                ('classificacao_motivo', models.TextField(blank=True, default='')),
                ('tags_automaticas', models.JSONField(default=list)),
                ('is_reserved', models.BooleanField(default=False)),
                ('is_purchased', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lead', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='profile',
                    to='leads.lead',
                )),
            ],
            options={
                'db_table': 'lead_profiles',
            },
        ),
    ]
