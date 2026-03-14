from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.core.models import Organization, UserProfile, Plan, Subscription
from apps.leads.models import LeadTag
from apps.quick_replies.models import QuickReply, QuickReplyCategory


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
        org, _ = Organization.objects.get_or_create(
            name='Border Collie Brasil',
            defaults={'is_active': True},
        )

        # Primary user — marcelo12souza@gmail.com (single l)
        admin_email = 'marcelo12souza@gmail.com'
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

        UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={'organization': org, 'role': 'admin'},
        )

        pro_plan = Plan.objects.filter(name='pro').first()
        if pro_plan:
            Subscription.objects.get_or_create(
                organization=org,
                defaults={'plan': pro_plan, 'status': 'active'},
            )

        for tag_name in ['tier-a', 'tier-b', 'tier-c', 'casa', 'apartamento', 'urgente', 'experiente']:
            LeadTag.objects.get_or_create(organization=org, name=tag_name)

        # Legacy quick replies (tenant-level, no user, no category_ref)
        legacy_qrs = [
            {'category': 'GREETING',    'shortcut': '/ola',    'text': 'Olá {lead_name}! Tudo bem? Sou {user_name} da Border Collie Brasil.'},
            {'category': 'INFO',        'shortcut': '/info',   'text': 'O Border Collie é uma raça inteligente e ativa. Ideal para famílias que têm espaço e tempo.'},
            {'category': 'PRICING',     'shortcut': '/preco',  'text': 'Nossos filhotes ficam entre R$ 2.500 - R$ 4.500, com procedimentos e garantia de saúde.'},
            {'category': 'AVAILABILITY','shortcut': '/disp',   'text': 'Temos filhotes disponíveis! Posso te enviar fotos e mais informações.'},
            {'category': 'SCHEDULING',  'shortcut': '/visita', 'text': 'Que tal agendar uma visita? Temos horários disponíveis de segunda a sábado, das 9h às 18h.'},
            {'category': 'CLOSING',     'shortcut': '/fechar', 'text': 'Ótimo! Vou preparar tudo para você. Qualquer dúvida estou à disposição!'},
        ]
        for qr in legacy_qrs:
            QuickReply.objects.get_or_create(
                organization=org,
                shortcut=qr['shortcut'],
                defaults={**qr, 'is_active': True},
            )

        self._seed_quick_replies_border_collie_sul(org, admin_user)

        self.stdout.write(f"  Org: {org.name} (API key: {org.api_key})")

    def _seed_quick_replies_border_collie_sul(self, org, user):
        """
        Seed structured quick replies for Border Collie Sul / marcelo12souza@gmail.com.

        Replies with user set are personal to this operator.
        Replies with user=None would be tenant-level.
        """
        categories_data = [
            {'name': 'Apresentação',          'sort_order': 1},
            {'name': 'Ninhada atual',         'sort_order': 2},
            {'name': 'Disponibilidade',       'sort_order': 3},
            {'name': 'Valores',               'sort_order': 4},
            {'name': 'Linhagem e procedência','sort_order': 5},
            {'name': 'Entrega e documentação','sort_order': 6},
            {'name': 'Qualificação',          'sort_order': 7},
            {'name': 'Follow-up',             'sort_order': 8},
        ]

        cats = {}
        for cat_data in categories_data:
            cat, _ = QuickReplyCategory.objects.get_or_create(
                organization=org,
                name=cat_data['name'],
                defaults={'sort_order': cat_data['sort_order']},
            )
            cats[cat_data['name']] = cat

        replies_data = [
            {
                'category_name': 'Apresentação',
                'title': 'Apresentação inicial',
                'body': (
                    'Olá! Aqui é a Border Collie Sul.\n\n'
                    'Obrigado pelo seu contato!\n\n'
                    'Nossos filhotes são filhos do Sky e da Leia e são criados em ambiente '
                    'familiar com muito cuidado.'
                ),
                'sort_order': 1,
            },
            {
                'category_name': 'Ninhada atual',
                'title': 'Idade da ninhada',
                'body': (
                    'A ninhada atual está com aproximadamente {{days}} dias.\n\n'
                    'Nos próximos dias vou fazer as fotos oficiais, mas já temos algumas '
                    'reservas feitas.'
                ),
                'sort_order': 1,
            },
            {
                'category_name': 'Disponibilidade',
                'title': 'Filhotes disponíveis',
                'body': (
                    'Já temos alguns filhotes reservados, mas ainda há alguns disponíveis.\n\n'
                    'Se quiser, posso te mostrar quais ainda estão disponíveis da ninhada atual.'
                ),
                'sort_order': 1,
            },
            {
                'category_name': 'Valores',
                'title': 'Faixa de preço',
                'body': (
                    'Nossos filhotes, com pedigree, microchip e acompanhamento inicial, '
                    'têm valor a partir de R$ 5.000.'
                ),
                'sort_order': 1,
            },
            {
                'category_name': 'Linhagem e procedência',
                'title': 'Pais da ninhada',
                'body': (
                    'Você pode ver os pais da ninhada no nosso Instagram @bordercolliesul\n\n'
                    'E conhecer mais sobre o nosso trabalho no site da Border Collie Sul:\n'
                    'https://bordercolliesul.com.br'
                ),
                'sort_order': 1,
            },
            {
                'category_name': 'Entrega e documentação',
                'title': 'Entrega completa',
                'body': (
                    'Eles são entregues com:\n\n'
                    '✔ Pedigree\n'
                    '✔ Microchip\n'
                    '✔ Registro do canil\n'
                    '✔ Vermifugação\n'
                    '✔ Primeira vacina'
                ),
                'sort_order': 1,
            },
            {
                'category_name': 'Qualificação',
                'title': 'Pergunta sobre prazo',
                'body': 'Para quando você está pensando em trazer seu Border Collie para casa?',
                'sort_order': 1,
            },
            {
                'category_name': 'Follow-up',
                'title': 'Retomar conversa',
                'body': (
                    'Oi! Passando para saber se você ainda tem interesse em conhecer os '
                    'filhotes disponíveis desta ninhada.\n\n'
                    'Se quiser, posso te enviar fotos e mais informações.'
                ),
                'sort_order': 1,
            },
        ]

        for r in replies_data:
            cat = cats[r['category_name']]
            exists = QuickReply.objects.filter(
                organization=org,
                user=user,
                category_ref=cat,
                title=r['title'],
            ).exists()
            if not exists:
                QuickReply.objects.create(
                    organization=org,
                    user=user,
                    category_ref=cat,
                    title=r['title'],
                    body=r['body'],
                    sort_order=r['sort_order'],
                    is_active=True,
                )
                self.stdout.write(f"    QR created: [{r['category_name']}] {r['title']}")
            else:
                self.stdout.write(f"    QR exists:  [{r['category_name']}] {r['title']}")
