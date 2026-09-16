"""
Cria (em rascunho/pausada, nunca ativada) a campanha "SC | Border Collie | Ninhada Atual |
Search" — primeira campanha real de Google Ads Search do Border Omni, com 4 ad groups
(Comprar/Santa Catarina/Preço/Canil), keywords Exact+Phrase, negativas por categoria e
geo targeting "Presence". Reutiliza CampaignService.create_campaign — nunca fala com o
provider diretamente — para se comportar exatamente como o fluxo manual/chat já usados
pelo produto (mesmo respeito a GOOGLE_ADS_ENABLED/DRY_RUN, mesmo "nasce PAUSED").

Idempotente via client_request_id: rodar de novo não duplica a campanha.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Organization
from apps.kennel.models import Litter, DogHealthRecord, LitterHealthRecord
from apps.advertising.models import AdvertisingAccount, AdCampaignBriefing
from apps.advertising.services.campaign_service import CampaignService

CAMPAIGN_NAME = 'SC | Border Collie | Ninhada Atual | Search'
DAILY_BUDGET = 40.0
LANDING_URL = 'https://www.bordercolliesul.com.br/'
# CPC máximo (teto do leilão, não preço fixo) — sem isso, a Google Ads API cria os ad groups com
# o mínimo técnico (1 centavo), inelegíveis para competir em qualquer leilão real (bug real
# observado na primeira execução desta campanha, corrigido depois via set_ad_group_cpc_bids).
DEFAULT_CPC_BID = 2.50

HEADLINE_MAX_LEN = 30
DESCRIPTION_MAX_LEN = 90

TIER_1_CITIES = [
    'Florianópolis', 'São José', 'Palhoça', 'Biguaçu',
    'Balneário Camboriú', 'Itajaí', 'Blumenau', 'Brusque', 'Camboriú', 'Navegantes',
    'Joinville', 'Jaraguá do Sul',
]
TIER_2_CITIES = ['Criciúma', 'Tubarão', 'Chapecó', 'Rio do Sul']

DESCRIPTIONS = {
    'geral_1': 'Conheça nossa ninhada de Border Collie em Santa Catarina. Veja fotos e informações.',
    'geral_2': 'Filhotes Border Collie disponíveis. Conheça a ninhada e fale diretamente conosco.',
    'geral_3': 'Veja fotos, informações e disponibilidade dos filhotes da nossa ninhada atual.',
    'sc_1': 'Procura Border Collie em SC? Conheça os filhotes e fale conosco pelo WhatsApp.',
    'canil_1': 'Conheça os filhotes, veja disponibilidade e converse diretamente com o criador.',
    'sc_2': 'Nova ninhada de Border Collie em SC. Veja informações, fotos e disponibilidade.',
}


def exact(text: str) -> dict:
    return {'text': text, 'match_type': 'EXACT'}


def phrase(text: str) -> dict:
    return {'text': text, 'match_type': 'PHRASE'}


def build_ad_groups() -> list[dict]:
    return [
        {
            'name': 'Comprar',
            'keywords': [
                exact('comprar border collie'), exact('comprar filhote border collie'),
                exact('border collie a venda'), exact('border collie à venda'),
                exact('filhote border collie'), exact('filhote de border collie'),
                exact('border collie filhote'), exact('filhotes border collie'),
                phrase('comprar border collie'), phrase('comprar filhote border collie'),
                phrase('border collie a venda'), phrase('border collie à venda'),
                phrase('filhote border collie'), phrase('filhote de border collie'),
                phrase('border collie filhote'),
            ],
            'ads': [
                {
                    'headlines': ['Filhotes Border Collie', 'Border Collie à Venda', 'Conheça Nossa Ninhada',
                                  'Filhotes Disponíveis', 'Reserve Seu Border Collie', 'Conheça os Filhotes'],
                    'descriptions': [DESCRIPTIONS['geral_1'], DESCRIPTIONS['geral_2']],
                },
                {
                    'headlines': ['Ninhada Border Collie', 'Border Collie Disponível', 'Veja Nossos Filhotes',
                                  'Fale Conosco no WhatsApp', 'Fotos da Ninhada', 'Consulte Disponibilidade'],
                    'descriptions': [DESCRIPTIONS['geral_3'], DESCRIPTIONS['sc_1']],
                },
            ],
        },
        {
            'name': 'Santa Catarina',
            'keywords': [
                exact('border collie sc'), exact('border collie santa catarina'),
                exact('filhote border collie sc'), exact('filhote border collie santa catarina'),
                exact('filhotes border collie sc'), exact('border collie florianopolis'),
                exact('border collie joinville'), exact('border collie blumenau'),
                exact('border collie itajai'), exact('border collie balneario camboriu'),
                phrase('border collie santa catarina'), phrase('filhote border collie santa catarina'),
                phrase('border collie sc'), phrase('filhote border collie sc'),
                phrase('canil border collie santa catarina'), phrase('canil border collie sc'),
            ],
            'ads': [
                {
                    'headlines': ['Filhotes Border Collie SC', 'Border Collie em SC', 'Filhotes em Santa Catarina',
                                  'Border Collie Santa Catarina', 'Canil em Santa Catarina', 'Criador em Santa Catarina'],
                    'descriptions': [DESCRIPTIONS['geral_1'], DESCRIPTIONS['sc_2']],
                },
                {
                    'headlines': ['Border Collie em Florianópolis', 'Border Collie no Sul', 'Nova Ninhada Border Collie',
                                  'Conheça os Filhotes', 'Fale Conosco no WhatsApp', 'Consulte Disponibilidade'],
                    'descriptions': [DESCRIPTIONS['sc_1'], DESCRIPTIONS['geral_3']],
                },
            ],
        },
        {
            'name': 'Preço',
            'keywords': [
                exact('border collie preço'), exact('preço border collie'),
                exact('filhote border collie preço'), exact('preço filhote border collie'),
                exact('border collie valor'), exact('valor border collie'), exact('valor filhote border collie'),
                phrase('border collie preço'), phrase('preço border collie'),
                phrase('filhote border collie preço'), phrase('border collie valor'), phrase('valor border collie'),
            ],
            'ads': [
                {
                    'headlines': ['Border Collie: Consulte Valor', 'Valor do Border Collie', 'Consulte Disponibilidade',
                                  'Filhotes Border Collie', 'Fale Conosco no WhatsApp', 'Conheça os Filhotes'],
                    'descriptions': [DESCRIPTIONS['geral_1'], DESCRIPTIONS['geral_3']],
                },
                {
                    'headlines': ['Filhotes Disponíveis', 'Border Collie Disponível', 'Reserve Seu Border Collie',
                                  'Ninhada Border Collie', 'Veja Nossos Filhotes', 'Conheça Nossa Ninhada'],
                    'descriptions': [DESCRIPTIONS['geral_2'], DESCRIPTIONS['canil_1']],
                },
            ],
        },
        {
            'name': 'Canil',
            'keywords': [
                exact('canil border collie'), exact('canil border collie sc'), exact('canil border collie santa catarina'),
                exact('criador border collie'), exact('criador border collie sc'),
                phrase('canil border collie'), phrase('canil border collie sc'),
                phrase('canil border collie santa catarina'), phrase('criador border collie'),
            ],
            'ads': [
                {
                    'headlines': ['Criador em Santa Catarina', 'Canil em Santa Catarina', 'Conheça Nossa Ninhada',
                                  'Filhotes Border Collie', 'Consulte Disponibilidade', 'Fale Conosco no WhatsApp'],
                    'descriptions': [DESCRIPTIONS['canil_1'], DESCRIPTIONS['geral_1']],
                },
                {
                    'headlines': ['Nova Ninhada Border Collie', 'Border Collie no Sul', 'Fotos da Ninhada',
                                  'Veja Nossos Filhotes', 'Conheça os Filhotes', 'Reserve Seu Border Collie'],
                    'descriptions': [DESCRIPTIONS['geral_3'], DESCRIPTIONS['sc_2']],
                },
            ],
        },
    ]


NEGATIVE_KEYWORDS = [
    # Adoção / gratuito
    'adoção', 'adotar', 'adote', 'doação', 'doar', 'grátis', 'gratuito', 'de graça',
    'resgate', 'abandonado', 'ong', 'abrigo',
    # Conteúdo puramente informativo
    'wikipedia', 'história', 'origem', 'trabalho escolar', 'trabalho faculdade',
    'pdf', 'livro', 'desenho', 'papel de parede', 'imagem',
    # Emprego / profissional
    'emprego', 'vaga', 'salário', 'curso', 'curso adestramento', 'adestrador',
    # Produtos pet
    'ração', 'coleira', 'brinquedo', 'cama', 'casinha', 'roupa', 'shampoo', 'pet shop',
    # Serviços
    'veterinário', 'veterinária', 'castração', 'clínica veterinária', 'hotel para cães', 'banho e tosa',
]
DO_NOT_NEGATE_KEYWORDS = [
    'preço', 'valor', 'comprar', 'venda', 'canil', 'criador', 'pedigree', 'filhote', 'disponível',
]


def validate_ad_group_lengths(ad_groups: list[dict]) -> list[str]:
    """Retorna a lista de violações (nunca trunca — o chamador decide o que fazer)."""
    violations = []
    for ad_group in ad_groups:
        for ad in ad_group['ads']:
            for headline in ad['headlines']:
                if len(headline) > HEADLINE_MAX_LEN:
                    violations.append(
                        f'[{ad_group["name"]}] headline com {len(headline)} caracteres '
                        f'(máx {HEADLINE_MAX_LEN}): "{headline}"'
                    )
            for description in ad['descriptions']:
                if len(description) > DESCRIPTION_MAX_LEN:
                    violations.append(
                        f'[{ad_group["name"]}] description com {len(description)} caracteres '
                        f'(máx {DESCRIPTION_MAX_LEN}): "{description}"'
                    )
    return violations


class Command(BaseCommand):
    help = 'Cria a campanha "SC | Border Collie | Ninhada Atual | Search" em rascunho/pausada.'

    def add_arguments(self, parser):
        parser.add_argument('--org-id', type=int, default=None, help='ID da Organization (obrigatório se houver mais de uma).')
        parser.add_argument('--litter-id', type=int, default=None, help='ID da Litter (padrão: is_featured=True mais recente).')
        parser.add_argument('--yes', action='store_true', help='Não pede confirmação interativa.')

    def handle(self, *args, **options):
        ad_groups = build_ad_groups()
        violations = validate_ad_group_lengths(ad_groups)
        if violations:
            raise CommandError(
                'Textos fora do limite do Google Ads — corrija antes de continuar (nunca truncamos '
                'automaticamente):\n' + '\n'.join(f'  - {v}' for v in violations)
            )

        organization = self._resolve_organization(options['org_id'])
        account = AdvertisingAccount.objects.filter(organization=organization, is_active=True).first()
        if not account:
            raise CommandError(
                f'Nenhuma AdvertisingAccount ativa para a organização "{organization.name}". '
                'Conecte uma conta Google Ads primeiro (fluxo OAuth já existente no produto).'
            )

        litter = self._resolve_litter(organization, options['litter_id'])
        differentiators = self._collect_real_differentiators(litter)

        self.stdout.write(f'Organização: {organization.name}')
        self.stdout.write(f'Conta Google Ads: {account.customer_id} (login: {account.login_customer_id or account.customer_id})')
        if litter:
            self.stdout.write(f'Ninhada vinculada (rastreio interno): #{litter.id} — {litter.name}')
        else:
            self.stdout.write(self.style.WARNING(
                'Nenhuma Litter com is_featured=True (ou recente) encontrada — a campanha será '
                'criada sem vínculo a uma ninhada específica. Confira em /canil/ninhadas.'
            ))
        if differentiators:
            self.stdout.write('Diferenciais reais encontrados: ' + '; '.join(differentiators))
        else:
            self.stdout.write('Nenhum diferencial estruturado (pedigree/exame/vacina/vermífugo) encontrado — anúncios não citam nenhum.')

        if not options['yes']:
            confirm = input('Confirma a criação desta campanha (rascunho/pausada)? [s/N] ')
            if confirm.strip().lower() not in ('s', 'sim', 'y', 'yes'):
                self.stdout.write(self.style.WARNING('Cancelado.'))
                return

        region = ', '.join(TIER_1_CITIES + TIER_2_CITIES)
        negative_keywords = [{'text': kw, 'match_type': 'BROAD'} for kw in NEGATIVE_KEYWORDS]

        client_request_id = f'border-collie-set-2026-{litter.id if litter else "no-litter"}'
        campaign = CampaignService().create_campaign(
            organization=organization,
            advertising_account=account,
            litter=litter,
            data={
                'name': CAMPAIGN_NAME,
                'daily_budget': DAILY_BUDGET,
                'region': region,
                'landing_url': LANDING_URL,
                'ad_groups': ad_groups,
                'negative_keywords': negative_keywords,
                'geo_target_type': 'PRESENCE',
                'default_cpc_bid': DEFAULT_CPC_BID,
            },
            client_request_id=client_request_id,
        )

        if litter:
            AdCampaignBriefing.objects.update_or_create(
                campaign=campaign,
                defaults={
                    'product_description': 'Filhotes de Border Collie (ninhada atual) — venda direta pelo canil.',
                    'objective': (
                        'Pesquisa de alta intenção -> visita ao site -> contato -> conversa via WhatsApp -> '
                        'lead qualificado -> reserva -> venda. CTR/CPC/impressões são métricas intermediárias.'
                    ),
                    'price_info': 'Consultar valor diretamente com o canil (não divulgado em texto de anúncio).',
                    'primary_conversion': 'lead/whatsapp (sem histórico de conversão confiável ainda para qualified_lead/reservation/sale)',
                    'priority_regions': {'tier_1': TIER_1_CITIES, 'tier_2': TIER_2_CITIES},
                    'positive_intent_keywords': [kw['text'] for ag in ad_groups for kw in ag['keywords']],
                    'negative_keywords': NEGATIVE_KEYWORDS,
                    'do_not_negate_keywords': DO_NOT_NEGATE_KEYWORDS,
                    'notes': (
                        'Bidding: Manual CPC — conta sem histórico confiável de conversão para este produto ainda; '
                        'reavaliar Maximize Conversions após ~5-7 dias de dados. Geo targeting: PRESENCE (não '
                        'Presence-or-Interest). Landing page é a home (ninhada em destaque), não uma página dedicada.'
                    ),
                },
            )

        self._print_summary(campaign, ad_groups, negative_keywords, region)

    def _resolve_organization(self, org_id):
        if org_id:
            try:
                return Organization.objects.get(id=org_id)
            except Organization.DoesNotExist:
                raise CommandError(f'Organization #{org_id} não encontrada.')
        orgs = list(Organization.objects.all()[:2])
        if len(orgs) == 1:
            return orgs[0]
        raise CommandError('Mais de uma Organization encontrada — informe --org-id.')

    def _resolve_litter(self, organization, litter_id):
        if litter_id:
            try:
                return Litter.objects.get(organization=organization, id=litter_id)
            except Litter.DoesNotExist:
                raise CommandError(f'Litter #{litter_id} não encontrada nesta organização.')
        featured = Litter.objects.filter(organization=organization, is_featured=True).order_by(
            '-birth_date', '-expected_birth_date',
        ).first()
        if featured:
            return featured
        return Litter.objects.filter(organization=organization).order_by('-created_at').first()

    def _collect_real_differentiators(self, litter) -> list[str]:
        if not litter:
            return []
        found = []
        if litter.cbkc_number:
            found.append(f'registro CBKC da ninhada ({litter.cbkc_number})')
        for parent_label, parent in (('pai', litter.father), ('mãe', litter.mother)):
            if parent and parent.pedigree_number:
                found.append(f'pedigree do(a) {parent_label} ({parent.pedigree_number})')
            if parent:
                record_types = set(
                    DogHealthRecord.objects.filter(dog=parent).values_list('record_type', flat=True)
                )
                for record_type, label in (('vaccine', 'vacinação'), ('deworming', 'vermifugação'), ('exam', 'exame')):
                    if record_type in record_types:
                        found.append(f'{label} registrada para o(a) {parent_label}')
        litter_record_types = set(
            LitterHealthRecord.objects.filter(litter=litter).values_list('record_type', flat=True)
        )
        for record_type, label in (('vaccine', 'vacinação'), ('deworming', 'vermifugação'), ('exam', 'exame')):
            if record_type in litter_record_types:
                found.append(f'{label} registrada para a ninhada')
        return found

    def _print_summary(self, campaign, ad_groups, negative_keywords, region):
        total_keywords = sum(len(ag['keywords']) for ag in ad_groups)
        total_ads = sum(len(ag['ads']) for ag in ad_groups)

        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('CAMPAIGN            ' + CAMPAIGN_NAME)
        self.stdout.write('STATUS               ' + campaign.status.upper() + (
            ' (Google Ads: PAUSED nos 3 níveis — nunca ativado automaticamente)'
            if campaign.status in ('active', 'pending') else ''
        ))
        self.stdout.write(f'BUDGET               R$ {DAILY_BUDGET:.2f}/dia')
        self.stdout.write('NETWORK              Google Search (Google Search + Search Partners; Display/Content desligado)')
        self.stdout.write(f'LOCATIONS            {region}')
        self.stdout.write('LOCATION MODE        Presence (positiveGeoTargetType=PRESENCE)')
        self.stdout.write(f'AD GROUPS            {len(ad_groups)} ({", ".join(ag["name"] for ag in ad_groups)})')
        self.stdout.write(f'KEYWORDS             {total_keywords} (Exact+Phrase, sem Broad)')
        self.stdout.write(f'NEGATIVES            {len(negative_keywords)}')
        self.stdout.write(f'ADS                  {total_ads} RSAs ({len(ad_groups)} ad groups x 2)')
        self.stdout.write(f'FINAL URL            {LANDING_URL}')
        self.stdout.write('PRIMARY CONVERSION   lead/whatsapp (qualified_lead/reservation/sale como macro, sem volume ainda)')
        self.stdout.write(
            f'BIDDING              Manual CPC, teto de R$ {DEFAULT_CPC_BID:.2f}/clique por ad group '
            '(conta nova para este produto — sem histórico confiável de conversão)'
        )
        self.stdout.write('TRACKING             GCLID via ValueTrack (finalUrlSuffix) + UTMs utm_source=google&utm_medium=cpc')
        self.stdout.write('=' * 70)

        self.stdout.write('\nAD GROUPS E KEYWORDS:')
        for ag in ad_groups:
            self.stdout.write(f'  {ag["name"]}: {len(ag["keywords"])} keywords, {len(ag["ads"])} RSAs')
            for ad in ag['ads']:
                self.stdout.write(f'    - Headlines: {", ".join(ad["headlines"])}')
                self.stdout.write(f'      Descriptions: {" | ".join(ad["descriptions"])}')

        self.stdout.write('\nNEGATIVAS: ' + ', '.join(NEGATIVE_KEYWORDS))
        self.stdout.write('NÃO NEGATIVAR: ' + ', '.join(DO_NOT_NEGATE_KEYWORDS))

        self.stdout.write('\nWARNINGS / LIMITAÇÕES:')
        self.stdout.write('  - A landing page é a home do site (a ninhada está em destaque lá), não uma página '
                           'dedicada /ninhada/{id} — reavaliar se/quando existir uma página própria da ninhada atual.')
        self.stdout.write('  - A estrutura por ad group não é espelhada localmente no Border Omni ainda (precisa de uma '
                           'migration nova, ad_groups no AdCampaign, que não pôde ser aplicada ao banco de produção '
                           'nesta sessão) — o Google Ads é a fonte de verdade da estrutura real criada.')
        self.stdout.write('  - update_ad_content/get_campaign_diagnostics (usados pelo agente de chat) hoje assumem '
                           '"1 anúncio por campanha" — com 4 ad groups x 2 RSAs, editar copy de um grupo específico '
                           'via chat ainda não é suportado.')
        self.stdout.write('  - Sitelinks/callouts e troca automática de bid strategy (Manual CPC -> Maximize '
                           'Conversions) não foram implementados nesta entrega — ficam como recomendação para quando '
                           'houver ~5-7 dias de dados.')
        self.stdout.write('  - Conversion actions já configuradas manualmente no Google Ads fora deste sistema (se '
                           'houver) não são detectadas automaticamente — só o que este sistema já criou em '
                           'AdvertisingAccount.metadata é reconhecido.')
        self.stdout.write(f'  - Cache local de conversion actions desta conta: {account_conversion_actions_summary(campaign)}')

        self.stdout.write('\nRECOMENDAÇÕES ANTES DE ATIVAR:')
        self.stdout.write('  1. Revisar headlines/descriptions no próprio Google Ads (aprovação de política).')
        self.stdout.write('  2. Aguardar 5-7 dias de dados antes de qualquer mudança relevante de orçamento.')
        self.stdout.write('  3. Nos dias 3-5, revisar Search Terms e negativar termos ruins (get_search_terms já existe).')
        self.stdout.write('  4. Só ativar (resume_campaign) após sua aprovação explícita.')


def account_conversion_actions_summary(campaign) -> str:
    metadata = campaign.advertising_account.metadata or {}
    actions = metadata.get('conversion_actions') or {}
    return ', '.join(actions.keys()) if actions else 'nenhuma criada ainda (serão criadas sob demanda no primeiro evento)'
