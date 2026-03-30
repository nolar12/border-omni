import time

from django.core.management.base import BaseCommand

from apps.leads.models import Lead
from apps.core.models import AgentConfig
from apps.qualifier.ai_classifier import AILeadClassifier


class Command(BaseCommand):
    help = 'Classifica retroativamente todos os leads usando o agente de IA psicológico'

    def add_arguments(self, parser):
        parser.add_argument(
            '--org-id',
            type=int,
            default=None,
            help='Filtrar por ID de organização (opcional)',
        )
        parser.add_argument(
            '--only-unclassified',
            action='store_true',
            help='Processa apenas leads sem lead_classification definida',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='Pausa entre requisições em segundos (padrão: 0.5)',
        )

    def handle(self, *args, **options):
        org_id = options.get('org_id')
        only_unclassified = options.get('only_unclassified')
        delay = options.get('delay')

        leads_qs = (
            Lead.objects
            .filter(conversations__messages__direction='IN')
            .distinct()
            .select_related('organization__agent_config')
        )

        if org_id:
            leads_qs = leads_qs.filter(organization_id=org_id)

        if only_unclassified:
            leads_qs = leads_qs.filter(lead_classification__isnull=True)

        total = leads_qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('Nenhum lead encontrado com os filtros aplicados.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Classificando {total} leads...\n'))

        counts = {'HOT_LEAD': 0, 'WARM_LEAD': 0, 'COLD_LEAD': 0, 'DANGER_LEAD': 0, 'novo': 0, 'erro': 0, 'sem_config': 0}

        for idx, lead in enumerate(leads_qs.iterator(), start=1):
            name = lead.full_name or lead.phone or f'lead-{lead.pk}'

            try:
                agent_config = lead.organization.agent_config
            except AgentConfig.DoesNotExist:
                self.stdout.write(f'  [{idx}/{total}] {name} → sem AgentConfig, pulando')
                counts['sem_config'] += 1
                continue

            if not agent_config.openai_api_key:
                self.stdout.write(f'  [{idx}/{total}] {name} → sem openai_api_key, pulando')
                counts['sem_config'] += 1
                continue

            try:
                classifier = AILeadClassifier(lead, agent_config)
                result = classifier.classify()
                if result is None:
                    self.stdout.write(f'  [{idx}/{total}] {name} → sem resultado (conversa vazia?)')
                    counts['erro'] += 1
                elif result == {}:
                    # Novo lead — dados insuficientes para classificar
                    self.stdout.write(f'  [{idx}/{total}] {name} → novo (aguardando interação)')
                    counts['novo'] += 1
                else:
                    classifier._map_to_db(result)
                    lead.refresh_from_db(fields=['lead_classification'])
                    classification = result.get('nivel_maturidade', '?')
                    prob = result.get('probabilidade_conversao', '?')
                    resumo = result.get('resumo_intencao', '')
                    db_class = lead.lead_classification or '?'
                    self.stdout.write(
                        f'  [{idx}/{total}] {name} → {db_class} '
                        f'(prob={prob}%, maturidade={classification}) — {resumo}'
                    )
                    if db_class in counts:
                        counts[db_class] += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  [{idx}/{total}] {name} → ERRO: {e}'))
                counts['erro'] += 1

            if delay > 0:
                time.sleep(delay)

        self.stdout.write('\n' + '─' * 50)
        self.stdout.write(self.style.SUCCESS('Resumo:'))
        self.stdout.write(f'  DANGER_LEAD:{counts["DANGER_LEAD"]}')
        self.stdout.write(f'  HOT_LEAD:  {counts["HOT_LEAD"]}')
        self.stdout.write(f'  WARM_LEAD: {counts["WARM_LEAD"]}')
        self.stdout.write(f'  COLD_LEAD: {counts["COLD_LEAD"]}')
        self.stdout.write(f'  Novos:     {counts["novo"]}')
        self.stdout.write(f'  Erros:     {counts["erro"]}')
        self.stdout.write(f'  Sem config:{counts["sem_config"]}')
        self.stdout.write('─' * 50)
