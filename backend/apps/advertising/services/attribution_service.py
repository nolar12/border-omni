import logging
import re

from django.utils import timezone

from apps.advertising.models import AdClickToken, AdLeadAttribution, AdEvent

logger = logging.getLogger('apps')

# Formato embutido na mensagem pré-preenchida do WhatsApp pelo site: "(ref: AB12CD34)"
REF_TOKEN_PATTERN = re.compile(r'\(ref:\s*([A-Za-z0-9]{4,16})\)')


class AttributionService:
    def create_click_token(self, *, organization, gclid: str = '', utm_source: str = '',
                            utm_medium: str = '', utm_campaign: str = '', utm_content: str = '',
                            litter=None, campaign=None) -> AdClickToken:
        return AdClickToken.objects.create(
            organization=organization,
            gclid=gclid,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_content=utm_content,
            litter=litter,
            campaign=campaign,
        )

    def extract_ref_token(self, text: str) -> str | None:
        if not text:
            return None
        match = REF_TOKEN_PATTERN.search(text)
        return match.group(1).upper() if match else None

    def match_lead_to_click_token(self, *, organization, lead, text: str) -> AdLeadAttribution | None:
        """
        Procura um código de referência (ex.: "(ref: AB12CD34)") no texto da mensagem
        recebida e, se encontrado, cria a atribuição definitiva do Lead à campanha/gclid.

        Chamado a partir do webhook de WhatsApp já existente — nunca deve lançar exceção
        que interrompa o processamento normal da mensagem (o chamador também protege
        com try/except, mas mantemos a mesma cautela aqui).
        """
        token_code = self.extract_ref_token(text)
        if not token_code:
            return None

        click_token = AdClickToken.objects.filter(organization=organization, token=token_code).first()
        if not click_token:
            return None

        attribution, _ = AdLeadAttribution.objects.update_or_create(
            lead=lead,
            defaults={
                'campaign': click_token.campaign,
                'gclid': click_token.gclid,
                'gbraid': click_token.gbraid,
                'wbraid': click_token.wbraid,
                'utm_source': click_token.utm_source,
                'utm_medium': click_token.utm_medium,
                'utm_campaign': click_token.utm_campaign,
                'utm_content': click_token.utm_content,
                'ad_group_id': click_token.ad_group_id,
                'ad_id': click_token.ad_id,
                'keyword': click_token.keyword,
                'search_term': click_token.search_term,
            },
        )

        # Primeira mensagem que resgata este token = melhor proxy disponível para "clique no
        # WhatsApp que virou conversa" (o clique real no botão acontece na landing externa,
        # fora deste repositório, e não pode ser instrumentado por este código).
        is_first_match = not click_token.consumed_at
        if is_first_match:
            click_token.consumed_at = timezone.now()
            click_token.save(update_fields=['consumed_at'])

        if lead.source != 'GOOGLE_AD':
            lead.source = 'GOOGLE_AD'
            lead.save(update_fields=['source'])

        if is_first_match:
            AdEvent.objects.create(
                organization=organization,
                lead=lead,
                campaign=click_token.campaign,
                event_type='whatsapp_click',
                metadata={'gclid': click_token.gclid, 'token': token_code},
            )

        AdEvent.objects.create(
            organization=organization,
            lead=lead,
            campaign=click_token.campaign,
            event_type='lead_created',
            metadata={'gclid': click_token.gclid, 'token': token_code},
        )

        return attribution
