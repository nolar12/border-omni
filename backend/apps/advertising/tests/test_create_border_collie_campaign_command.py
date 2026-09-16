from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.core.models import Organization
from apps.kennel.models import Litter, Dog, DogHealthRecord
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdCampaignBriefing
from apps.advertising.management.commands.create_border_collie_campaign import (
    build_ad_groups, validate_ad_group_lengths, HEADLINE_MAX_LEN, DESCRIPTION_MAX_LEN,
)


class BuildAdGroupsLengthTests(TestCase):
    """As constantes reais usadas pela campanha nunca devem estourar os limites do Google Ads."""

    def test_real_ad_group_content_respects_length_limits(self):
        violations = validate_ad_group_lengths(build_ad_groups())
        self.assertEqual(violations, [])

    def test_headline_over_limit_is_reported_never_silently_truncated(self):
        ad_groups = [{
            'name': 'Teste',
            'keywords': [],
            'ads': [{'headlines': ['H' * (HEADLINE_MAX_LEN + 1)], 'descriptions': ['ok']}],
        }]
        violations = validate_ad_group_lengths(ad_groups)
        self.assertEqual(len(violations), 1)
        self.assertIn('headline', violations[0])

    def test_description_over_limit_is_reported(self):
        ad_groups = [{
            'name': 'Teste',
            'keywords': [],
            'ads': [{'headlines': ['ok'], 'descriptions': ['D' * (DESCRIPTION_MAX_LEN + 1)]}],
        }]
        violations = validate_ad_group_lengths(ad_groups)
        self.assertEqual(len(violations), 1)
        self.assertIn('description', violations[0])


@override_settings(GOOGLE_ADS_ENABLED=False)
class CreateBorderCollieCampaignCommandTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Border Collie Sul')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='1112223334', is_active=True)

    def test_creates_draft_campaign_with_real_differentiators(self):
        father = Dog.objects.create(organization=self.org, name='Trooper', sex='M', pedigree_number='CBKC-123')
        litter = Litter.objects.create(organization=self.org, name='Ninhada Setembro', is_featured=True, father=father)
        DogHealthRecord.objects.create(dog=father, record_type='vaccine', description='V10', date='2026-01-01')

        out = StringIO()
        call_command('create_border_collie_campaign', '--org-id', self.org.id, '--yes', stdout=out)

        campaign = AdCampaign.objects.get(organization=self.org)
        self.assertEqual(campaign.status, 'draft')
        self.assertEqual(campaign.litter_id, litter.id)
        self.assertEqual(float(campaign.daily_budget), 40.0)
        self.assertEqual(campaign.landing_url, 'https://www.bordercolliesul.com.br/')
        self.assertTrue(AdCampaignBriefing.objects.filter(campaign=campaign).exists())

        output = out.getvalue()
        self.assertIn('CBKC-123', output)
        self.assertIn('vacinação', output)

        # Idempotente: rodar de novo não cria uma segunda campanha.
        call_command('create_border_collie_campaign', '--org-id', self.org.id, '--yes', stdout=StringIO())
        self.assertEqual(AdCampaign.objects.filter(organization=self.org).count(), 1)

    def test_no_differentiators_found_is_stated_explicitly_never_invented(self):
        Litter.objects.create(organization=self.org, name='Ninhada Sem Dados', is_featured=True)

        out = StringIO()
        call_command('create_border_collie_campaign', '--org-id', self.org.id, '--yes', stdout=out)

        self.assertIn('Nenhum diferencial estruturado', out.getvalue())

    def test_requires_org_id_when_multiple_organizations_exist(self):
        Organization.objects.create(name='Outro Canil')
        with self.assertRaises(CommandError):
            call_command('create_border_collie_campaign', '--yes', stdout=StringIO())

    def test_fails_without_advertising_account(self):
        self.account.delete()
        with self.assertRaises(CommandError):
            call_command('create_border_collie_campaign', '--org-id', self.org.id, '--yes', stdout=StringIO())
