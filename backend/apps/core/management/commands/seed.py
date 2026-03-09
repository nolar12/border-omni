from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.core.models import Organization, UserProfile, Plan, Subscription
from apps.leads.models import LeadTag
from apps.quick_replies.models import QuickReply


class Command(BaseCommand):
    help = 'Seeds the database with initial data (safe to run multiple times)'

    def handle(self, *args, **options):
        self._seed_plans()
        self._seed_org_and_admin()
        self.stdout.write(self.style.SUCCESS('✅ Seed completed.'))

    def _seed_plans(self):
        plans = [
            {'name': 'free',       'max_leads': 50,    'max_agents': 1,  'max_channels': 1,  'price_monthly': 0},
            {'name': 'pro',        'max_leads': 500,   'max_agents': 5,  'max_channels': 3,  'price_monthly': 197},
            {'name': 'enterprise', 'max_leads': 99999, 'max_agents': 99, 'max_channels': 10, 'price_monthly': 597},
        ]
        for p in plans:
            obj, created = Plan.objects.get_or_create(name=p['name'], defaults=p)
            if created:
                self.stdout.write(f"  Plan created: {p['name']}")
            else:
                self.stdout.write(f"  Plan exists: {p['name']}")

    def _seed_org_and_admin(self):
        # Org
        org, _ = Organization.objects.get_or_create(
            name='Border Collie Brasil',
            defaults={'is_active': True},
        )

        # Admin user — marcello12souza@gmail.com
        admin_email = 'marcello12souza@gmail.com'
        admin_user, created = User.objects.get_or_create(
            email=admin_email,
            defaults={
                'username': admin_email,
                'first_name': 'Marcelo',
                'last_name': 'Souza',
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(f"  Admin created: {admin_email}")
        else:
            self.stdout.write(f"  Admin exists: {admin_email}")

        # UserProfile
        UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={'organization': org, 'role': 'admin'},
        )

        # Subscription
        pro_plan = Plan.objects.filter(name='pro').first()
        if pro_plan:
            Subscription.objects.get_or_create(
                organization=org,
                defaults={'plan': pro_plan, 'status': 'active'},
            )

        # Tags
        for tag_name in ['tier-a', 'tier-b', 'tier-c', 'casa', 'apartamento', 'urgente', 'experiente']:
            LeadTag.objects.get_or_create(organization=org, name=tag_name)

        # Quick replies
        qrs = [
            {'category': 'GREETING',      'shortcut': '/ola',      'text': 'Olá {lead_name}! Tudo bem? Sou {user_name} da Border Collie Brasil. 🐕'},
            {'category': 'INFO',           'shortcut': '/info',     'text': 'O Border Collie é uma raça inteligente e ativa. Ideal para famílias que têm espaço e tempo. 🐾'},
            {'category': 'PRICING',        'shortcut': '/preco',    'text': 'Nossos filhotes ficam entre R$ 2.500 - R$ 4.500, com procedimentos e garantia de saúde.'},
            {'category': 'AVAILABILITY',   'shortcut': '/disp',     'text': 'Temos filhotes disponíveis! Posso te enviar fotos e mais informações.'},
            {'category': 'SCHEDULING',     'shortcut': '/visita',   'text': 'Que tal agendar uma visita? Temos horários disponíveis de segunda a sábado, das 9h às 18h.'},
            {'category': 'CLOSING',        'shortcut': '/fechar',   'text': 'Ótimo! Vou preparar tudo para você. Qualquer dúvida estou à disposição! 😊'},
        ]
        for qr in qrs:
            QuickReply.objects.get_or_create(
                organization=org,
                shortcut=qr['shortcut'],
                defaults={**qr, 'is_active': True},
            )

        self.stdout.write(f"  Org: {org.name} (API key: {org.api_key})")
