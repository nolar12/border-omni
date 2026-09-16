from django.test import TestCase

from apps.core.models import Organization
from apps.leads.models import Lead
from apps.advertising.models import AdClickToken, AdLeadAttribution, AdEvent
from apps.advertising.services.attribution_service import AttributionService


class AttributionServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil D')
        self.lead = Lead.objects.create(organization=self.org, phone='554899990000', source='OTHER')

    def test_extract_ref_token_from_message(self):
        service = AttributionService()
        token = service.extract_ref_token('Olá! Quero saber mais sobre a ninhada.\n\n(ref: AB12CD34)')
        self.assertEqual(token, 'AB12CD34')

    def test_extract_ref_token_returns_none_without_pattern(self):
        service = AttributionService()
        self.assertIsNone(service.extract_ref_token('Olá! Quero saber mais sobre a ninhada.'))

    def test_match_lead_to_click_token_creates_attribution_and_sets_source(self):
        click_token = AdClickToken.objects.create(
            organization=self.org, gclid='Cj0KCQtest', utm_source='google', utm_medium='cpc',
        )
        service = AttributionService()
        attribution = service.match_lead_to_click_token(
            organization=self.org, lead=self.lead,
            text=f'Olá! Quero saber mais.\n\n(ref: {click_token.token})',
        )

        self.assertIsNotNone(attribution)
        self.assertEqual(attribution.gclid, 'Cj0KCQtest')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.source, 'GOOGLE_AD')

        click_token.refresh_from_db()
        self.assertIsNotNone(click_token.consumed_at)

    def test_match_lead_to_click_token_no_op_without_token(self):
        service = AttributionService()
        result = service.match_lead_to_click_token(
            organization=self.org, lead=self.lead, text='Olá, quero saber mais sobre os filhotes.',
        )
        self.assertIsNone(result)
        self.assertFalse(AdLeadAttribution.objects.filter(lead=self.lead).exists())
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.source, 'OTHER')

    def test_match_lead_to_click_token_unknown_token_is_no_op(self):
        service = AttributionService()
        result = service.match_lead_to_click_token(
            organization=self.org, lead=self.lead, text='Olá! (ref: NAOEXISTE)',
        )
        self.assertIsNone(result)

    def test_match_lead_to_click_token_fires_whatsapp_click_once(self):
        click_token = AdClickToken.objects.create(
            organization=self.org, gclid='Cj0KCQtest', utm_source='google', utm_medium='cpc',
        )
        service = AttributionService()
        text = f'Olá! Quero saber mais.\n\n(ref: {click_token.token})'

        service.match_lead_to_click_token(organization=self.org, lead=self.lead, text=text)
        self.assertEqual(
            AdEvent.objects.filter(lead=self.lead, event_type='whatsapp_click').count(), 1,
        )

        # Segunda mensagem citando o mesmo ref-token não deve duplicar o whatsapp_click.
        service.match_lead_to_click_token(organization=self.org, lead=self.lead, text=text)
        self.assertEqual(
            AdEvent.objects.filter(lead=self.lead, event_type='whatsapp_click').count(), 1,
        )
