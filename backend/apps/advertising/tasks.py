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
