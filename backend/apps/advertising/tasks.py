import logging

from celery import shared_task

logger = logging.getLogger('apps')


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_all_campaign_metrics(self):
    """Agendado automaticamente via django-celery-beat (mesmo padrão de apps/channels/tasks.py)."""
    from apps.advertising.models import AdCampaign
    from apps.advertising.services.metrics_service import MetricsService

    service = MetricsService()
    synced = 0
    errors = 0
    for campaign in AdCampaign.objects.filter(status='active'):
        try:
            service.sync_campaign_metrics(campaign)
            synced += 1
        except Exception as exc:
            errors += 1
            logger.warning(f'sync_all_campaign_metrics error (campaign={campaign.id}): {exc}')

    logger.info(f'sync_all_campaign_metrics done: {synced} synced, {errors} errors')
    return {'synced': synced, 'errors': errors}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_proactive_campaign_reviews(self):
    """
    Roda a revisão periódica e autônoma do agente para cada campanha ativa —
    ninguém precisa abrir o chat e perguntar "analise a campanha": se houver
    algo relevante (dado o funil comercial, o histórico de decisões, o
    desempenho por cidade/keyword), o agente posta a análise direto no chat
    dessa campanha (AdChatMessage.is_proactive=True). Só LÊ dados (ver
    AdvertisingAgentService.PROACTIVE_TOOLS) — nunca executa uma mudança
    sozinho; sugestões continuam exigindo o usuário pedir "pode executar" no
    chat, como qualquer outra ação.
    """
    from apps.advertising.models import AdCampaign, AdvertisingSettings
    from apps.advertising.services.metrics_service import MetricsService
    from apps.advertising.services.agent_service import AdvertisingAgentService

    reviewed = 0
    posted = 0
    errors = 0

    disabled_org_ids = set(
        AdvertisingSettings.objects.filter(proactive_review_enabled=False).values_list('organization_id', flat=True)
    )

    for campaign in AdCampaign.objects.filter(status='active').select_related('organization'):
        if campaign.organization_id in disabled_org_ids:
            continue

        openai_api_key = getattr(getattr(campaign.organization, 'agent_config', None), 'openai_api_key', '') or ''
        if not openai_api_key:
            continue

        try:
            MetricsService().sync_campaign_metrics(campaign)
        except Exception as exc:
            logger.warning(f'run_proactive_campaign_reviews: falha ao sincronizar métricas (campaign={campaign.id}): {exc}')

        try:
            reviewed += 1
            message = AdvertisingAgentService(campaign).run_proactive_review(openai_api_key=openai_api_key)
            if message:
                posted += 1
        except Exception as exc:
            errors += 1
            logger.warning(f'run_proactive_campaign_reviews error (campaign={campaign.id}): {exc}')

    logger.info(f'run_proactive_campaign_reviews done: {reviewed} reviewed, {posted} posted, {errors} errors')
    return {'reviewed': reviewed, 'posted': posted, 'errors': errors}
