from django.test import TestCase

from apps.core.models import Organization
from apps.leads.models import Lead, LeadProfile
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdLeadAttribution, AdEvent
from apps.advertising.services.lead_funnel_service import commercial_stage, funnel_summary


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
