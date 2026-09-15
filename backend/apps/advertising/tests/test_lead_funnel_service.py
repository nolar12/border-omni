from django.test import TestCase

from apps.core.models import Organization
from apps.leads.models import Lead, LeadProfile
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdLeadAttribution, AdEvent
from apps.advertising.services.lead_funnel_service import commercial_stage, funnel_summary, breakdown_by_city, breakdown_by_keyword


class CommercialStageTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil L')

    def _lead(self, **kwargs):
        return Lead.objects.create(organization=self.org, phone='55489999' + str(Lead.objects.count()), **kwargs)

    def test_new_lead_defaults_to_new(self):
        lead = self._lead(status='NEW')
        self.assertEqual(commercial_stage(lead), 'NEW')

    def test_qualifying_maps_to_contacted(self):
        lead = self._lead(status='QUALIFYING')
        self.assertEqual(commercial_stage(lead), 'CONTACTED')

    def test_hot_lead_classification_maps_to_qualified(self):
        lead = self._lead(status='QUALIFYING', lead_classification='HOT_LEAD')
        self.assertEqual(commercial_stage(lead), 'QUALIFIED')

    def test_cold_lead_maps_to_unqualified(self):
        lead = self._lead(status='QUALIFYING', lead_classification='COLD_LEAD')
        self.assertEqual(commercial_stage(lead), 'UNQUALIFIED')

    def test_handoff_maps_to_negotiating(self):
        lead = self._lead(status='HANDOFF')
        self.assertEqual(commercial_stage(lead), 'NEGOTIATING')

    def test_reserved_profile_wins_over_status(self):
        lead = self._lead(status='HANDOFF')
        LeadProfile.objects.create(lead=lead, is_reserved=True)
        self.assertEqual(commercial_stage(lead), 'RESERVED')

    def test_purchased_profile_wins_over_reserved(self):
        lead = self._lead(status='HANDOFF')
        LeadProfile.objects.create(lead=lead, is_reserved=True, is_purchased=True)
        self.assertEqual(commercial_stage(lead), 'SOLD')

    def test_archived_without_reservation_maps_to_lost(self):
        lead = self._lead(status='CLOSED', is_archived=True)
        self.assertEqual(commercial_stage(lead), 'LOST')


class FunnelSummaryTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil M')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='2223334445')
        self.campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='Camp M', daily_budget=10,
        )

    def test_counts_leads_by_stage_and_top_of_funnel_events(self):
        lead1 = Lead.objects.create(organization=self.org, phone='554890000001', status='NEW')
        AdLeadAttribution.objects.create(lead=lead1, campaign=self.campaign, gclid='g1')

        lead2 = Lead.objects.create(organization=self.org, phone='554890000002', status='HANDOFF')
        LeadProfile.objects.create(lead=lead2, is_purchased=True)
        AdLeadAttribution.objects.create(lead=lead2, campaign=self.campaign, gclid='g2')

        AdEvent.objects.create(organization=self.org, campaign=self.campaign, event_type='page_view')
        AdEvent.objects.create(organization=self.org, campaign=self.campaign, event_type='page_view')
        AdEvent.objects.create(organization=self.org, campaign=self.campaign, event_type='whatsapp_click')

        summary = funnel_summary(self.campaign)

        self.assertEqual(summary['page_views'], 2)
        self.assertEqual(summary['whatsapp_clicks'], 1)
        self.assertEqual(summary['total_leads'], 2)
        self.assertEqual(summary['stages']['NEW'], 1)
        self.assertEqual(summary['stages']['SOLD'], 1)


class BreakdownByCityAndKeywordTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil R')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='7778889990')
        self.campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='Camp R', daily_budget=10,
        )

    def _lead(self, city, phone_suffix):
        return Lead.objects.create(organization=self.org, phone=f'554890000{phone_suffix}', city=city)

    def test_breakdown_by_city_groups_and_ranks_by_volume(self):
        lead_floripa_qualified = self._lead('Florianópolis', '001')
        lead_floripa_qualified.status = 'QUALIFIED'
        lead_floripa_qualified.save()
        AdLeadAttribution.objects.create(lead=lead_floripa_qualified, campaign=self.campaign, gclid='g1', keyword='border collie filhote')

        lead_joinville_lost = self._lead('Joinville', '002')
        lead_joinville_lost.is_archived = True
        lead_joinville_lost.save()
        AdLeadAttribution.objects.create(lead=lead_joinville_lost, campaign=self.campaign, gclid='g2', keyword='border collie preço')

        lead_floripa_new = self._lead('Florianópolis', '003')
        AdLeadAttribution.objects.create(lead=lead_floripa_new, campaign=self.campaign, gclid='g3', keyword='border collie filhote')

        result = breakdown_by_city(self.campaign)
        self.assertEqual(result[0]['group'], 'Florianópolis')  # mais leads, vem primeiro
        self.assertEqual(result[0]['total_leads'], 2)
        self.assertEqual(result[0]['qualified_leads'], 1)
        joinville = next(r for r in result if r['group'] == 'Joinville')
        self.assertEqual(joinville['stages']['LOST'], 1)

    def test_breakdown_by_city_uses_placeholder_for_missing_city(self):
        lead = self._lead('', '004')
        AdLeadAttribution.objects.create(lead=lead, campaign=self.campaign, gclid='g4')
        result = breakdown_by_city(self.campaign)
        self.assertEqual(result[0]['group'], 'Não informado')

    def test_breakdown_by_keyword_distinguishes_keyword_from_search_term(self):
        lead_sold = self._lead('Itajaí', '005')
        from apps.leads.models import LeadProfile
        LeadProfile.objects.create(lead=lead_sold, is_reserved=True, is_purchased=True)
        AdLeadAttribution.objects.create(
            lead=lead_sold, campaign=self.campaign, gclid='g5',
            keyword='border collie filhote', search_term='quanto custa um border collie filhote de verdade',
        )

        result = breakdown_by_keyword(self.campaign)
        self.assertEqual(result[0]['group'], 'border collie filhote')
        self.assertEqual(result[0]['sales'], 1)
        # A quebra nunca usa search_term como se fosse a keyword
        self.assertNotIn('quanto custa um border collie filhote de verdade', [r['group'] for r in result])
