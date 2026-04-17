from django.db import migrations, models


def seed_conversation_template(apps, schema_editor):
    """
    Popula conversation_template de todas as orgs existentes com o template
    hard-coded atual, preservando o comportamento já em produção.
    """
    # Import inline para evitar dependência circular com o módulo de serviço
    from apps.rag.services.rag_service import CONVERSATION_SYSTEM_PROMPT_TEMPLATE

    AgentConfig = apps.get_model('core', 'AgentConfig')
    AgentConfig.objects.filter(conversation_template='').update(
        conversation_template=CONVERSATION_SYSTEM_PROMPT_TEMPLATE,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_agentconfig_link_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentconfig',
            name='conversation_template',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='agentconfig',
            name='use_conversation_template',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(seed_conversation_template, migrations.RunPython.noop),
    ]
