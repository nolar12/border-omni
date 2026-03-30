import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0010_gallerymedia_description'),
        ('leads', '0006_add_is_archived'),
    ]

    operations = [
        migrations.CreateModel(
            name='SaleContract',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('puppy_sex', models.CharField(choices=[('M', 'Macho'), ('F', 'Fêmea')], max_length=1)),
                ('puppy_color', models.CharField(max_length=100)),
                ('puppy_microchip', models.CharField(blank=True, max_length=100)),
                ('puppy_father', models.CharField(blank=True, max_length=200)),
                ('puppy_mother', models.CharField(blank=True, max_length=200)),
                ('puppy_birth_date', models.DateField(blank=True, null=True)),
                ('price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('deposit_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('buyer_name', models.CharField(blank=True, max_length=200)),
                ('buyer_cpf', models.CharField(blank=True, max_length=14)),
                ('buyer_marital_status', models.CharField(blank=True, max_length=50)),
                ('buyer_address', models.CharField(blank=True, max_length=500)),
                ('buyer_cep', models.CharField(blank=True, max_length=9)),
                ('buyer_email', models.EmailField(blank=True, max_length=254)),
                ('status', models.CharField(choices=[('draft', 'Rascunho'), ('sent', 'Enviado ao comprador'), ('buyer_filled', 'Preenchido pelo comprador'), ('approved', 'Aprovado'), ('signed', 'Assinado')], default='draft', max_length=20)),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('signature_data', models.TextField(blank=True)),
                ('signature_type', models.CharField(blank=True, max_length=20)),
                ('pdf_file', models.FileField(blank=True, null=True, upload_to='contracts/pdfs/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('buyer_filled_at', models.DateTimeField(blank=True, null=True)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('signed_at', models.DateTimeField(blank=True, null=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contracts', to='core.organization')),
                ('lead', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='contracts', to='leads.lead')),
            ],
            options={
                'db_table': 'sale_contracts',
                'ordering': ['-created_at'],
            },
        ),
    ]
