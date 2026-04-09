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

        self._seed_quick_replies_border_collie_sul(org, admin_user)

        self.stdout.write(f"  Org: {org.name} (API key: {org.api_key})")

    def _seed_quick_replies_border_collie_sul(self, org, user):
        """
        Fluxo de vendas WhatsApp — Border Collie Sul.
        Apaga tudo que existia e recria do zero.
        """
        deleted_qr, _ = QuickReply.objects.filter(organization=org).delete()
        deleted_cat, _ = QuickReplyCategory.objects.filter(organization=org).delete()
        self.stdout.write(f"  QRs removidos: {deleted_qr} | Categorias removidas: {deleted_cat}")

        categories = [
            {
                'name': 'Fluxo de Vendas',
                'sort_order': 1,
                'replies': [
                    {
                        'title': 'Abertura',
                        'body': (
                            'Fala! Tudo bem?\n\n'
                            'Vi aqui que você chamou por causa dos filhotes 👀\n'
                            'Qual deles te chamou mais atenção?'
                        ),
                        'sort_order': 1,
                    },
                    {
                        'title': 'Se perguntar preço direto',
                        'body': (
                            'Claro, te passo sim 👍\n\n'
                            'Mas antes me diz uma coisa…\n'
                            'é pra companhia mesmo? família? ou você já tem ideia de treino também?'
                        ),
                        'sort_order': 2,
                    },
                    {
                        'title': 'Resposta com valor',
                        'body': (
                            'Boa…\n\n'
                            'Esses filhotes são de linhagem bem boa, com pedigree, pais selecionados '
                            'e tudo acompanhado certinho.\n\n'
                            'Eles estão saindo na faixa de R$ X.XXX\n\n'
                            'Mas mais importante que o valor é o perfil mesmo — tem alguns mais ativos, '
                            'outros mais tranquilos…\n\n'
                            'Por isso te perguntei antes 👍'
                        ),
                        'sort_order': 3,
                    },
                    {
                        'title': 'Engajamento',
                        'body': (
                            'Se quiser, te mando mais vídeos dele(a) aqui\n\n'
                            'No vídeo dá pra ver bem melhor o comportamento 👌'
                        ),
                        'sort_order': 4,
                    },
                    {
                        'title': 'Pós envio',
                        'body': (
                            'Esse é ele(a) no dia a dia…\n\n'
                            'Dá pra ter uma ideia boa do jeito dele(a), né?'
                        ),
                        'sort_order': 5,
                    },
                    {
                        'title': 'Fechamento',
                        'body': (
                            'Hoje ainda tenho disponibilidade sim\n\n'
                            'Se fizer sentido pra você, dá pra garantir com reserva 👍'
                        ),
                        'sort_order': 6,
                    },
                    {
                        'title': 'Follow-up',
                        'body': (
                            'E aí, chegou a ver os vídeos?\n\n'
                            'Esse perfil dele(a) costuma agradar bastante'
                        ),
                        'sort_order': 7,
                    },
                ],
            },
            {
                'name': 'Respostas Rápidas',
                'sort_order': 2,
                'replies': [
                    {
                        'title': 'Transporte',
                        'body': (
                            'Faço envio pra todo Brasil 👍\n\n'
                            'Normalmente vai por transportadora especializada, bem tranquilo e seguro'
                        ),
                        'sort_order': 1,
                    },
                    {
                        'title': 'Garantia / procedência',
                        'body': (
                            'Tem pedigree, pais selecionados e tudo acompanhado certinho\n\n'
                            'Se quiser te mando também mais detalhes deles'
                        ),
                        'sort_order': 2,
                    },
                    {
                        'title': 'Reserva',
                        'body': (
                            'A reserva é feita com 30%\n\n'
                            'E o restante antes da entrega 👍'
                        ),
                        'sort_order': 3,
                    },
                ],
            },
        ]

        for cat_data in categories:
            cat = QuickReplyCategory.objects.create(
                organization=org,
                name=cat_data['name'],
                sort_order=cat_data['sort_order'],
            )
            for r in cat_data['replies']:
                QuickReply.objects.create(
                    organization=org,
                    user=user,
                    category_ref=cat,
                    title=r['title'],
                    body=r['body'],
                    sort_order=r['sort_order'],
                    is_active=True,
                )
                self.stdout.write(f"    QR criado: [{cat_data['name']}] {r['title']}")
