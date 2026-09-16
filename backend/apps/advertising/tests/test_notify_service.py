from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from apps.core.models import Organization, UserProfile
from apps.channels.models import ChannelProvider
from apps.conversations.models import MessageTemplate
from apps.advertising.models import AdvertisingAccount, AdCampaign, AdChatMessage
from apps.advertising.services.notify_service import notify_admins_of_ad_review, TEMPLATE_NAME


class NotifyAdminsOfAdReviewTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Canil Notify')
        self.account = AdvertisingAccount.objects.create(organization=self.org, customer_id='1112223330')
        self.campaign = AdCampaign.objects.create(
            organization=self.org, advertising_account=self.account, name='SC | Border Collie | Ninhada Atual | Search',
            daily_budget=40, status='active', external_campaign_id='ext-1',
        )
        self.message = AdChatMessage.objects.create(
            organization=self.org, campaign=self.campaign, role='assistant',
            content='CTR caiu 30% na keyword "border collie preço".\nRecomendo revisar o anúncio dela.',
            is_proactive=True,
        )
        self.channel = ChannelProvider.objects.create(
            organization=self.org, provider='whatsapp', is_active=True,
            phone_number_id='123', access_token='tok',
        )
        UserProfile.objects.create(
            user=User.objects.create_user(username='admin-notify'), organization=self.org,
            phone='+5521999990000', role='admin',
        )

    def test_does_nothing_without_approved_template(self):
        with patch('apps.advertising.services.notify_service._send_whatsapp_template') as mock_send:
            notify_admins_of_ad_review(self.org, self.campaign, self.message)
        mock_send.assert_not_called()

    def test_sends_to_every_recipient_with_sanitized_params_when_approved(self):
        MessageTemplate.objects.create(
            organization=self.org, name=TEMPLATE_NAME, language='pt_BR', category='UTILITY',
            body_text='Atualizacao disponivel para a campanha {{1}}. Confira no Border Omni.',
            status='APPROVED', channel=self.channel,
        )
        UserProfile.objects.create(
            user=User.objects.create_user(username='agent-notify'), organization=self.org,
            phone='+5521888880000', role='agent',
        )

        with patch('apps.advertising.services.notify_service._send_whatsapp_template') as mock_send:
            notify_admins_of_ad_review(self.org, self.campaign, self.message)

        self.assertEqual(mock_send.call_count, 2)
        call = mock_send.call_args_list[0]
        self.assertEqual(call.kwargs['phone_number_id'], '123')
        self.assertEqual(call.kwargs['template_name'], TEMPLATE_NAME)
        params = call.kwargs['components'][0]['parameters']
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0]['text'], self.campaign.name)

    def test_never_raises_when_something_goes_wrong(self):
        MessageTemplate.objects.create(
            organization=self.org, name=TEMPLATE_NAME, language='pt_BR', category='UTILITY',
            body_text='Atualizacao disponivel para a campanha {{1}}. Confira no Border Omni.',
            status='APPROVED', channel=self.channel,
        )
        with patch('apps.advertising.services.notify_service._send_whatsapp_template', side_effect=RuntimeError('boom')):
            notify_admins_of_ad_review(self.org, self.campaign, self.message)  # não deve lançar

    def test_noop_without_recipients(self):
        UserProfile.objects.all().delete()
        MessageTemplate.objects.create(
            organization=self.org, name=TEMPLATE_NAME, language='pt_BR', category='UTILITY',
            body_text='Atualizacao disponivel para a campanha {{1}}. Confira no Border Omni.',
            status='APPROVED', channel=self.channel,
        )
        with patch('apps.advertising.services.notify_service._send_whatsapp_template') as mock_send:
            notify_admins_of_ad_review(self.org, self.campaign, self.message)
        mock_send.assert_not_called()

    def test_noop_without_active_whatsapp_channel(self):
        self.channel.is_active = False
        self.channel.save()
        MessageTemplate.objects.create(
            organization=self.org, name=TEMPLATE_NAME, language='pt_BR', category='UTILITY',
            body_text='Atualizacao disponivel para a campanha {{1}}. Confira no Border Omni.',
            status='APPROVED',
        )
        with patch('apps.advertising.services.notify_service._send_whatsapp_template') as mock_send:
            notify_admins_of_ad_review(self.org, self.campaign, self.message)
        mock_send.assert_not_called()
