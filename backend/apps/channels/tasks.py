import logging
import requests
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

RATING_ORDER = {'GREEN': 0, 'YELLOW': 1, 'RED': 2, 'UNKNOWN': 3}


def _fetch_quality_rating(phone_number_id: str, access_token: str) -> str | None:
    """Consulta o quality_rating via Graph API. Retorna a string do rating ou None em falha."""
    try:
        resp = requests.get(
            f'https://graph.facebook.com/v22.0/{phone_number_id}',
            params={'fields': 'quality_rating', 'access_token': access_token},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get('quality_rating') or None
        logger.warning(f'quality_rating API {phone_number_id}: HTTP {resp.status_code} — {resp.text[:200]}')
    except Exception as exc:
        logger.warning(f'quality_rating fetch error {phone_number_id}: {exc}')
    return None


def _record_change(cp, previous: str, new_rating: str):
    """Persiste o evento de mudança e loga alertas conforme severidade."""
    from .models import QualityRatingEvent

    event = QualityRatingEvent.objects.create(
        channel=cp,
        previous_rating=previous,
        new_rating=new_rating,
    )

    prev_order = RATING_ORDER.get(previous, -1)
    new_order = RATING_ORDER.get(new_rating, 3)
    is_degradation = new_order > prev_order

    org_name = cp.organization.name if cp.organization else f'org-{cp.pk}'
    phone = cp.phone_number_id

    if new_rating == 'RED':
        logger.error(
            f'[QUALITY ALERT] Canal {phone} ({org_name}) caiu para RED. '
            f'Risco de banimento do número. Verifique opt-ins e templates. event_id={event.pk}'
        )
    elif new_rating == 'YELLOW' and is_degradation:
        logger.warning(
            f'[QUALITY WARNING] Canal {phone} ({org_name}) caiu para YELLOW. '
            f'Monitore mensagens não solicitadas. event_id={event.pk}'
        )
    elif not is_degradation and previous in ('RED', 'YELLOW'):
        logger.info(
            f'[QUALITY RECOVERED] Canal {phone} ({org_name}) voltou para {new_rating}. event_id={event.pk}'
        )

    return event


def sync_single_channel(cp) -> dict:
    """
    Sincroniza o quality_rating de um único ChannelProvider.
    Retorna {'changed': bool, 'rating': str, 'event_id': int|None}.
    """
    new_rating = _fetch_quality_rating(cp.phone_number_id, cp.access_token)
    now = timezone.now()

    if new_rating is None:
        cp.quality_synced_at = now
        cp.save(update_fields=['quality_synced_at', 'updated_at'])
        return {'changed': False, 'rating': cp.quality_rating, 'event_id': None}

    previous = cp.quality_rating or ''
    changed = new_rating != previous

    update_fields = ['quality_synced_at', 'updated_at']
    if changed:
        cp.quality_rating = new_rating
        update_fields.append('quality_rating')

    cp.quality_synced_at = now
    cp.save(update_fields=update_fields)

    event_id = None
    if changed:
        event = _record_change(cp, previous, new_rating)
        event_id = event.pk

    return {'changed': changed, 'rating': new_rating, 'event_id': event_id}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_whatsapp_quality_ratings(self):
    """
    Busca o quality_rating de cada phone number WhatsApp ativo via Graph API.
    Cria QualityRatingEvent quando o rating muda e emite alertas via log.
    Agendado automaticamente via django-celery-beat a cada 6 horas.
    """
    from .models import ChannelProvider

    providers = ChannelProvider.objects.filter(
        provider='whatsapp',
        is_active=True,
        is_simulated=False,
    ).exclude(phone_number_id='').exclude(access_token='').select_related('organization')

    total = providers.count()
    changed = 0
    errors = 0

    for cp in providers:
        try:
            result = sync_single_channel(cp)
            if result['changed']:
                changed += 1
        except Exception as exc:
            errors += 1
            logger.warning(f'Erro ao sincronizar channel {cp.pk}: {exc}')

    logger.info(
        f'sync_whatsapp_quality_ratings: {total} canal(is) verificados, '
        f'{changed} atualizados, {errors} erros'
    )
    return {'total': total, 'changed': changed, 'errors': errors}
