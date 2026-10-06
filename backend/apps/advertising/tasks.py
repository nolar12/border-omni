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
        account = campaign.advertising_account
        try:
            service.sync_campaign_metrics(campaign)
            synced += 1
            if account.status == 'error':
                account.status = 'connected'
                account.metadata = {**account.metadata, 'last_sync_error': ''}
                account.save(update_fields=['status', 'metadata'])
        except Exception as exc:
            errors += 1
            logger.warning(f'sync_all_campaign_metrics error (campaign={campaign.id}): {exc}')
            account.status = 'error'
            account.metadata = {**account.metadata, 'last_sync_error': str(exc)[:200]}
            account.save(update_fields=['status', 'metadata'])

    logger.info(f'sync_all_campaign_metrics done: {synced} synced, {errors} errors')
    return {'synced': synced, 'errors': errors}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def daily_search_term_review(self):
    """Diário: nega (EXACT) termos casados por Broad sem citar a raça. Pula contas com token
    quebrado — sem acesso ao Google não há o que revisar."""
    from apps.advertising.models import AdCampaign
    from apps.advertising.services.search_term_review_service import SearchTermReviewService

    reviewed = 0
    negated = 0
    errors = 0
    for campaign in AdCampaign.objects.filter(status='active').exclude(external_campaign_id='').select_related('advertising_account'):
        if campaign.advertising_account.status == 'error':
            logger.warning(f'daily_search_term_review: conta com erro, pulando campaign={campaign.id}')
            continue
        try:
            negated += len(SearchTermReviewService().run(campaign))
            reviewed += 1
        except Exception as exc:
            errors += 1
            logger.error(f'daily_search_term_review FALHOU (campaign={campaign.id}): {exc}')

    logger.info(f'daily_search_term_review done: {reviewed} campanhas, {negated} negativas, {errors} erros')
    return {'reviewed': reviewed, 'negated': negated, 'errors': errors}


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
    from apps.advertising.services.notify_service import notify_admins_of_ad_review

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
                notify_admins_of_ad_review(campaign.organization, campaign, message)
        except Exception as exc:
            errors += 1
            logger.warning(f'run_proactive_campaign_reviews error (campaign={campaign.id}): {exc}')

    logger.info(f'run_proactive_campaign_reviews done: {reviewed} reviewed, {posted} posted, {errors} errors')
    return {'reviewed': reviewed, 'posted': posted, 'errors': errors}
