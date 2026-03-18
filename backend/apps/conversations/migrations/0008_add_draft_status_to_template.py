from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conversations', '0007_add_header_type_to_template'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagetemplate',
            name='status',
            field=models.CharField(
                choices=[
                    ('DRAFT', 'Rascunho'),
                    ('PENDING', 'Pending'),
                    ('APPROVED', 'Approved'),
                    ('REJECTED', 'Rejected'),
                    ('PAUSED', 'Paused'),
                    ('DISABLED', 'Disabled'),
                ],
                default='PENDING',
                max_length=20,
            ),
        ),
    ]
