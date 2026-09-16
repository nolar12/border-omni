"""
Notifica os usuários da organização via WhatsApp quando a revisão proativa do agente
(apps.advertising.tasks.run_proactive_campaign_reviews) posta algo relevante — sem isso,
a única forma de saber é abrir o Border Omni e checar o chat da campanha manualmente.

Espelha o padrão já usado para notificar sobre novas mensagens de leads
(api.views._notify_users_via_whatsapp): sempre via template aprovado da Meta (nunca texto
livre — é uma mensagem iniciada pelo sistema para alguém que nunca abriu uma janela de
conversa de 24h com o número comercial), destinatários = UserProfile com telefone
cadastrado, nunca deixa uma falha de notificação quebrar a revisão em si.
"""
import logging

import requests

from apps.core.models import UserProfile
from apps.channels.models import ChannelProvider
from apps.conversations.models import MessageTemplate

logger = logging.getLogger('apps')

TEMPLATE_NAME = 'revisao_anuncios_v5'


def _send_whatsapp_template(phone_number_id: str, access_token: str, to: str, template_name: str,
                             language_code: str, components: list[dict]) -> str | None:
    """Envio mínimo de template HSM via WhatsApp Cloud API — mesmo formato de payload usado em
    api.views._send_whatsapp_template, duplicado aqui para não criar uma dependência de
    apps.advertising em api.views (direção de import invertida em relação ao resto do projeto)."""
    url = f'https://graph.facebook.com/v22.0/{phone_number_id}/messages'
    payload = {
        'messaging_product': 'whatsapp', 'to': to, 'type': 'template',
        'template': {'name': template_name, 'language': {'code': language_code}, 'components': components},
    }
    try:
        resp = requests.post(
            url, json=payload,
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code >= 400:
            logger.warning(f'notify_service: falha ao enviar template "{template_name}" para {to}: {data}')
            return None
        return (data.get('messages') or [{}])[0].get('id')
    except requests.RequestException as exc:
        logger.warning(f'notify_service: erro de rede ao enviar template "{template_name}" para {to}: {exc}')
        return None


def _sanitize_template_param(text: str) -> str:
    """Parâmetros de template da Meta não podem ter quebras de linha nem múltiplos espaços seguidos."""
    return ' '.join((text or '').split())


def notify_admins_of_ad_review(organization, campaign, message) -> None:
    """
    `message` é o AdChatMessage(is_proactive=True) recém-criado pela revisão — só o nome da
    campanha vai no template (o conteúdo completo da análise fica no chat do Border Omni; um
    template com texto livre da IA embutido foi rejeitado pela Meta como INVALID_FORMAT em
    múltiplas tentativas, então o alerta é deliberadamente curto: "tem novidade, abra o app").
    Nunca lança — qualquer falha (canal desconectado, template ainda não aprovado pela Meta,
    API fora do ar) só fica registrada em log; a revisão em si já foi postada no chat de
    qualquer forma.
    """
    try:
        channel = ChannelProvider.objects.filter(organization=organization, provider='whatsapp', is_active=True).first()
        if not channel or not channel.access_token or not channel.phone_number_id:
            return

        template = MessageTemplate.objects.filter(
            organization=organization, name=TEMPLATE_NAME, status='APPROVED',
        ).first()
        if not template:
            logger.info(
                f'notify_service: template "{TEMPLATE_NAME}" ainda não aprovado pela Meta para '
                f'org {organization.id} — revisão da campanha {campaign.id} não foi notificada por WhatsApp.'
            )
            return

        recipients = list(UserProfile.objects.filter(organization=organization).exclude(phone='').values_list('phone', flat=True))
        if not recipients:
            return

        components = [{'type': 'body', 'parameters': [
            {'type': 'text', 'text': _sanitize_template_param(campaign.name)},
        ]}]

        for phone in recipients:
            _send_whatsapp_template(
                phone_number_id=channel.phone_number_id, access_token=channel.access_token,
                to=phone, template_name=template.name, language_code=template.language,
                components=components,
            )
    except Exception as exc:
        logger.warning(f'notify_admins_of_ad_review error (campaign={campaign.id}): {exc}')
