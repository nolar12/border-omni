"""
MetaConversionsService — envia eventos de qualificação de leads para a Meta Conversions API (CAPI).

Fluxo:
  classificação muda → _map_to_db chama send_if_applicable()
  → verifica CAPI ativo + dedup → monta payload → POST /v22.0/{pixel_id}/events
  → registra MetaConversionEvent (sucesso ou erro)

Segurança: meta_capi_token nunca é logado.
"""

import hashlib
import logging
import re
import uuid as _uuid
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

GRAPH_URL = 'https://graph.facebook.com/v22.0'

# Mapeamento: classificação interna → event_name da Meta
_CLASSIFICATION_TO_EVENT = {
    'HOT_LEAD': 'Lead',
    'WARM_LEAD': 'QualifiedLead',
}

# Tags de reforço de pontuação
_BOOST_TAGS = {'reserva', 'pagamento', 'pedigree', 'entrega', 'familia', 'crianca'}
# Tags de redução
_REDUCE_TAGS = {'desconto': -1.0, 'valor': -0.5}


def _compute_profile_classification(result: dict) -> str | None:
    """
    Determina HOT_LEAD / WARM_LEAD / COLD_LEAD a partir dos parâmetros de perfil
    retornados pelo classificador AI.

    Pontuação máxima: 13 pts base + 2 pts em tags = 15.
    HOT >= 8 | WARM >= 4 | COLD < 4

    Exportada aqui para ser importada pelo ai_classifier também.
    """
    SCORES = {
        'potencial_compra': {'alto': 5, 'medio': 2, 'baixo': 0, 'indefinido': 1},
        'sensibilidade_preco': {'baixa': 3, 'media': 1, 'alta': 0, 'indefinido': 1},
        'urgencia_compra': {'imediata': 3, 'curto_prazo': 2, 'pesquisando': 1, 'indefinido': 1},
        'intencao_uso': {
            'reproducao': 3, 'familia_companhia': 2,
            'curiosidade': 0, 'trabalho_rural': 0, 'indefinido': 1,
        },
        'perfil_localizacao': {
            'capital_grande_centro': 1, 'cidade_media': 1,
            'rural_interior': 0, 'outro_estado_distante': 0, 'indefinido': 0,
        },
    }

    score = 0.0
    for field, mapping in SCORES.items():
        val = result.get(field, 'indefinido')
        score += mapping.get(val, 0)

    tags = result.get('tags_automaticas', [])
    if isinstance(tags, list):
        boost = sum(0.5 for t in tags if t in _BOOST_TAGS)
        score += min(boost, 2.0)
        for tag, penalty in _REDUCE_TAGS.items():
            if tag in tags:
                score += penalty

    if score >= 8:
        return 'HOT_LEAD'
    if score >= 4:
        return 'WARM_LEAD'
    return 'COLD_LEAD'


class MetaConversionsService:
    """Serviço isolado para envio de eventos à Meta Conversions API."""

    # ------------------------------------------------------------------ #
    # Ponto de entrada principal
    # ------------------------------------------------------------------ #

    def send_if_applicable(self, lead, new_classification: str, org, event_name: str | None = None):
        """
        Verifica condições e, se aplicável, envia evento para a Meta CAPI.

        lead             : instância de Lead
        new_classification: HOT_LEAD / WARM_LEAD / COLD_LEAD / DANGER_LEAD ou None
        org              : instância de Organization (com .agent_config)
        event_name       : forçar nome do evento (para reserved/purchased)
        """
        try:
            cfg = getattr(org, 'agent_config', None)
            if not cfg or not cfg.meta_conversions_enabled or not cfg.meta_pixel_id:
                return

            resolved_event = event_name or self._map_event_name(new_classification, cfg)
            if not resolved_event:
                return

            if not self._should_send(lead, resolved_event):
                return

            payload = self._build_payload(lead, resolved_event, new_classification or '', cfg)
            resp_data, error = self._send(payload, cfg)

            if error:
                self._record(lead, resolved_event, new_classification or '', 'error',
                             payload, None, org, error_message=error)
            else:
                self._record(lead, resolved_event, new_classification or '', 'sent',
                             payload, resp_data, org)
        except Exception as exc:
            logger.warning('MetaConversionsService.send_if_applicable error: %s', exc)

    # ------------------------------------------------------------------ #
    # Deduplicação
    # ------------------------------------------------------------------ #

    def _should_send(self, lead, event_name: str) -> bool:
        from apps.channels.models import MetaConversionEvent
        already_sent = MetaConversionEvent.objects.filter(
            lead=lead, event_name=event_name, status='sent'
        ).exists()
        return not already_sent

    # ------------------------------------------------------------------ #
    # Mapeamento classificação → evento
    # ------------------------------------------------------------------ #

    def _map_event_name(self, classification: str | None, cfg) -> str | None:
        if not classification:
            return None
        if classification == 'COLD_LEAD':
            return None
        if classification == 'HOT_LEAD' and not cfg.send_hot_events:
            return None
        if classification == 'WARM_LEAD' and not cfg.send_warm_events:
            return None
        return _CLASSIFICATION_TO_EVENT.get(classification)

    # ------------------------------------------------------------------ #
    # Normalização e hash de telefone
    # ------------------------------------------------------------------ #

    def _normalize_phone(self, phone: str) -> str:
        digits = re.sub(r'\D', '', phone or '')
        if digits and not digits.startswith('55'):
            digits = '55' + digits
        return digits

    def _hash_phone(self, phone: str) -> str:
        normalized = self._normalize_phone(phone)
        return hashlib.sha256(normalized.encode()).hexdigest()

    # ------------------------------------------------------------------ #
    # Extração de IDs de anúncio do referral
    # ------------------------------------------------------------------ #

    def _extract_ad_ids(self, lead) -> tuple[str, str, str]:
        referral = lead.ad_referral or {}
        campaign_id = referral.get('campaign_id', '')
        adset_id = referral.get('adset_id', '')
        ad_id = referral.get('ad_id', '')
        return campaign_id, adset_id, ad_id

    # ------------------------------------------------------------------ #
    # Montagem do payload CAPI
    # ------------------------------------------------------------------ #

    def _build_payload(self, lead, event_name: str, lead_status: str, cfg) -> dict:
        phone_hash = self._hash_phone(lead.phone)
        campaign_id, adset_id, ad_id = self._extract_ad_ids(lead)
        event_id = str(_uuid.uuid4())
        now_ts = int(datetime.now(timezone.utc).timestamp())

        user_data: dict = {'ph': [phone_hash]}
        if lead.full_name:
            name_parts = lead.full_name.lower().split()
            if name_parts:
                user_data['fn'] = [hashlib.sha256(name_parts[0].encode()).hexdigest()]
            if len(name_parts) > 1:
                user_data['ln'] = [hashlib.sha256(name_parts[-1].encode()).hexdigest()]

        custom_data: dict = {}
        if event_name == 'Purchase' and hasattr(lead, 'profile') and lead.profile.is_purchased:
            custom_data = {'currency': 'BRL', 'value': 0}

        event: dict = {
            'event_name': event_name,
            'event_time': now_ts,
            'event_id': event_id,
            'action_source': 'other',
            'user_data': user_data,
        }
        if custom_data:
            event['custom_data'] = custom_data
        if campaign_id:
            event['data_processing_options'] = []

        payload: dict = {
            'data': [event],
            'access_token': cfg.meta_capi_token,
        }
        if cfg.meta_test_event_code:
            payload['test_event_code'] = cfg.meta_test_event_code

        return payload

    # ------------------------------------------------------------------ #
    # Envio HTTP
    # ------------------------------------------------------------------ #

    def _send(self, payload: dict, cfg) -> tuple[dict | None, str | None]:
        url = f'{GRAPH_URL}/{cfg.meta_pixel_id}/events'
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json(), None
        except requests.HTTPError as exc:
            try:
                error_body = exc.response.json()
            except Exception:
                error_body = str(exc)
            return None, str(error_body)
        except Exception as exc:
            return None, str(exc)

    # ------------------------------------------------------------------ #
    # Registro do evento no banco
    # ------------------------------------------------------------------ #

    def _record(self, lead, event_name: str, lead_status: str, status: str,
                payload: dict, response, org, error_message: str = ''):
        from apps.channels.models import MetaConversionEvent
        from django.utils import timezone as dj_tz

        safe_payload = {k: v for k, v in payload.items() if k != 'access_token'}

        campaign_id, adset_id, ad_id = self._extract_ad_ids(lead)

        MetaConversionEvent.objects.create(
            organization=org,
            lead=lead,
            event_name=event_name,
            lead_status=lead_status,
            event_id=str(_uuid.uuid4()),
            phone_hash=self._hash_phone(lead.phone),
            campaign_id=campaign_id,
            adset_id=adset_id,
            ad_id=ad_id,
            payload=safe_payload,
            response=response,
            status=status,
            error_message=error_message,
            sent_at=dj_tz.now() if status == 'sent' else None,
        )
        logger.info(
            'MetaConversionEvent: lead=%s event=%s status=%s',
            lead.pk, event_name, status,
        )
