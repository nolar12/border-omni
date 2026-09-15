"""
Agente de IA conversacional sobre uma campanha específica (chat na tela de
Anúncios). Usa a mesma OpenAI API key por tenant já usada pelo classificador de
leads (apps/qualifier/ai_classifier.py).

Arquitetura em camadas (ver apps/advertising/skills/google_ads_performance_manager.md
para a metodologia completa):
  1. SKILL — conhecimento permanente/universal (arquivo .md versionado).
  2. BRIEFING — contexto comercial desta campanha (AdCampaignBriefing, no banco).
  3. DADOS REAIS do Google Ads — via tools (get_campaign_summary, get_search_terms).
  4. DADOS COMERCIAIS do nosso sistema — via tools (get_lead_funnel), reaproveitando
     Lead.status/lead_classification/LeadProfile.is_reserved/is_purchased já existentes.
  5. AÇÕES — sempre through CampaignService (nunca direto no banco/API).
  6. MEMÓRIA — cada ação vira um AdAgentDecision, consultável via get_decision_history.

Regra de segurança central: o agente NUNCA mexe direto no banco ou na API do
Google — toda ação passa pelas mesmas CampaignService/MetricsService que a UI
usa. O "tool calling" da OpenAI só decide QUAL método de serviço chamar.
"""
import json
import logging

from openai import OpenAI

from apps.kennel.models import Litter
from apps.advertising.models import AdChatMessage, AdvertisingSettings, AdAgentDecision, AdCampaignPlan
from apps.advertising.providers import GoogleAdsProviderError
from apps.advertising.services.campaign_service import CampaignService
from apps.advertising.services.metrics_service import MetricsService
from apps.advertising.services.campaign_plan_service import CampaignPlanService
from apps.advertising.services.docs_research_service import fetch_official_documentation
from apps.advertising.services import lead_funnel_service
from apps.advertising.services.skill_service import load_skill, format_briefing

logger = logging.getLogger('apps')

MAX_HISTORY_MESSAGES = 20
MAX_TOOL_ROUNDTRIPS = 6

SYSTEM_PROMPT_TEMPLATE = """{skill}

## Briefing desta campanha

{briefing}

## Contexto técnico atual da campanha

- Nome: {name}
- Status: {status}
- Orçamento diário: R$ {daily_budget}
- Região configurada: {region}
- Ninhada vinculada: {litter_name}
- Limite de variação de orçamento que você pode executar sozinho: {max_auto_budget_change_percent}%
  (acima disso, use update_daily_budget normalmente uma primeira vez — ela vai te
  avisar que precisa de confirmação; explique a mudança ao usuário e só chame de
  novo com confirmed=true depois que ele concordar explicitamente).

Responda sempre em português do Brasil, de forma direta e objetiva. Use as
ferramentas disponíveis para consultar dados reais — nunca invente métricas,
número de leads, vendas ou qualquer estatística. Depois de executar uma ação,
confirme claramente o que foi feito.

Quando o usuário perguntar como uma mudança passada se saiu ("como foi aquela
mudança?", "aquilo funcionou?"), use get_decision_history para achar a decisão
e depois evaluate_decision para comparar antes/depois com números reais. Se a
ferramenta indicar has_before_snapshot=false, diga claramente que não há dado
histórico suficiente para essa decisão específica — nunca estime ou invente.

Quando o usuário pedir para CRIAR uma campanha nova (ex.: "crie uma campanha
para esta ninhada"), NUNCA execute direto: primeiro chame propose_campaign_plan,
apresente o plano retornado de forma legível (orçamento, região, anúncios,
palavras-chave, estimativa/justificativa) e peça aprovação explícita. Só chame
execute_campaign_plan com confirmed=true depois que o usuário concordar
claramente; se ele recusar ou pedir para descartar, chame reject_campaign_plan."""

TOOLS = [
    {'type': 'function', 'function': {
        'name': 'get_campaign_summary',
        'description': 'Retorna nome, status, orçamento, região, texto do anúncio atual e métricas agregadas já sincronizadas da campanha.',
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
    }},
    {'type': 'function', 'function': {
        'name': 'sync_metrics',
        'description': 'Sincroniza as métricas mais recentes da campanha com o Google Ads (use antes de analisar performance se os dados podem estar desatualizados).',
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
    }},
    {'type': 'function', 'function': {
        'name': 'get_search_terms',
        'description': 'Lista os termos de busca reais (search terms) que dispararam o anúncio nos últimos N dias, com clique/custo/conversões — use para achar desperdício ou novas keywords.',
        'parameters': {
            'type': 'object',
            'properties': {'days_back': {'type': 'integer', 'description': 'Janela em dias (padrão 30).'}},
            'required': [],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'get_lead_funnel',
        'description': 'Retorna o funil comercial dos leads originados desta campanha (visitas, cliques no WhatsApp, e leads por estágio: NEW/CONTACTED/QUALIFIED/UNQUALIFIED/NEGOTIATING/RESERVED/SOLD/LOST) — dados reais do CRM, não do Google Ads.',
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
    }},
    {'type': 'function', 'function': {
        'name': 'get_decision_history',
        'description': 'Lista as últimas decisões/ações já tomadas nesta campanha (por você ou pelo usuário), com o motivo e a hipótese declarados na época — consulte antes de repetir uma otimização.',
        'parameters': {
            'type': 'object',
            'properties': {'limit': {'type': 'integer', 'description': 'Quantas decisões recentes retornar (padrão 10).'}},
            'required': [],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'pause_campaign',
        'description': 'Pausa a campanha no Google Ads (para de gastar e de exibir anúncios). Ação estrutural relevante — confirme com o usuário antes, a menos que ele já tenha pedido isso claramente.',
        'parameters': {
            'type': 'object',
            'properties': {'reason': {'type': 'string', 'description': 'Motivo da pausa, para registro histórico.'}},
            'required': [],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'resume_campaign',
        'description': 'Reativa a campanha pausada no Google Ads.',
        'parameters': {
            'type': 'object',
            'properties': {'reason': {'type': 'string'}},
            'required': [],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'update_daily_budget',
        'description': (
            'Altera o orçamento diário da campanha. Se a variação exceder o limite de '
            'auto-execução da organização, a ferramenta NÃO executa e retorna requires_approval=true — '
            'nesse caso, explique a mudança ao usuário e só chame de novo com confirmed=true '
            'depois que ele concordar explicitamente.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'daily_budget': {'type': 'number', 'description': 'Novo orçamento diário em reais (R$).'},
                'reason': {'type': 'string'},
                'hypothesis': {'type': 'string', 'description': 'O que você espera que aconteça com essa mudança.'},
                'confirmed': {'type': 'boolean', 'description': 'true somente depois que o usuário confirmou explicitamente uma mudança acima do limite de auto-execução.'},
            },
            'required': ['daily_budget'],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'evaluate_decision',
        'description': (
            'Compara o estado ANTES e DEPOIS de uma decisão passada (pause/resume/orçamento/negativas), '
            'usando o metrics_snapshot real gravado no momento da decisão + um snapshot novo de agora. '
            'Use para responder perguntas como "como foi aquela mudança?" ou "aquilo funcionou?". '
            'Se a decisão for antiga e não tiver metrics_snapshot salvo, a ferramenta avisa isso explicitamente '
            '— nesse caso, diga ao usuário que não há dado histórico suficiente, NUNCA invente números.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {'decision_id': {'type': 'integer', 'description': 'ID da decisão (retornado por get_decision_history).'}},
            'required': ['decision_id'],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'add_negative_keywords',
        'description': 'Adiciona palavras-chave negativas de campanha (bloqueiam buscas irrelevantes). Use apenas para termos inequivocamente fora do propósito comercial — nunca negative termos do briefing marcados como "nunca negativar".',
        'parameters': {
            'type': 'object',
            'properties': {
                'keywords': {'type': 'array', 'items': {'type': 'string'}},
                'reason': {'type': 'string'},
            },
            'required': ['keywords'],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'propose_campaign_plan',
        'description': (
            'Monta uma PROPOSTA de campanha nova (ex.: quando o usuário pedir "crie uma campanha para esta '
            'ninhada") e a salva como rascunho — NUNCA cria a campanha de verdade. Retorna o plano completo '
            '(nome, orçamento, região, headlines/descriptions/keywords, negativas, estimativa) para você '
            'apresentar em português, de forma legível, e pedir aprovação explícita ao usuário antes de '
            'chamar execute_campaign_plan. Se litter_id não for informado, assume a ninhada desta campanha atual.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'daily_budget': {'type': 'number', 'description': 'Orçamento diário proposto em reais (R$).'},
                'litter_id': {'type': 'integer', 'description': 'ID da ninhada a promover; se omitido, usa a ninhada da campanha atual (se houver).'},
                'name': {'type': 'string'},
                'region': {'type': 'string', 'description': 'Cidades separadas por vírgula.'},
                'radius_km': {'type': 'integer'},
                'audience_description': {'type': 'string', 'description': 'Público-alvo, para gerar headlines/descriptions por IA.'},
                'negative_keywords': {'type': 'array', 'items': {'type': 'string'}},
                'justification': {'type': 'string', 'description': 'Sua estimativa/justificativa para esta proposta — o porquê do orçamento, região e segmentação escolhidos.'},
            },
            'required': ['daily_budget'],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'execute_campaign_plan',
        'description': (
            'Executa de fato um plano de campanha já proposto (cria a campanha real no Google Ads, pausada, '
            'reaproveitando o mesmo fluxo do botão "Nova Campanha"). SÓ chame com confirmed=true depois que o '
            'usuário aprovar explicitamente o resumo do plano — nunca antecipe essa confirmação.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'plan_id': {'type': 'integer'},
                'confirmed': {'type': 'boolean', 'description': 'true somente após o usuário aprovar explicitamente o plano.'},
            },
            'required': ['plan_id'],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'reject_campaign_plan',
        'description': 'Descarta um plano de campanha proposto que o usuário não quis aprovar.',
        'parameters': {
            'type': 'object',
            'properties': {'plan_id': {'type': 'integer'}},
            'required': ['plan_id'],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'fetch_official_documentation',
        'description': (
            'Busca o texto de UMA página de documentação oficial do Google (só developers.google.com ou '
            'support.google.com — qualquer outro domínio é recusado). Use apenas quando a pergunta depender '
            'de algo volátil que pode ter mudado desde o seu treinamento: API/Data Manager do Google Ads, '
            'políticas de anúncio, tipos de campanha, ValueTrack, conversões, estratégias de lance, ou '
            'recursos novos/descontinuados. Não use para metodologia geral (isso já está na sua skill) nem '
            'para dados desta conta (isso vem das outras ferramentas).'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'description': 'URL completa da página de documentação oficial do Google.'},
            },
            'required': ['url'],
        },
    }},
]


class AdvertisingAgentService:
    def __init__(self, campaign):
        self.campaign = campaign
        self.organization = campaign.organization

    def _get_openai(self, api_key: str) -> OpenAI:
        return OpenAI(api_key=api_key)

    def _build_system_prompt(self) -> str:
        campaign = self.campaign
        briefing = getattr(campaign, 'briefing', None)
        ad_settings = AdvertisingSettings.objects.filter(organization=self.organization).first()
        max_pct = ad_settings.max_auto_budget_change_percent if ad_settings else 20

        return SYSTEM_PROMPT_TEMPLATE.format(
            skill=load_skill(),
            briefing=format_briefing(briefing),
            name=campaign.name,
            status=campaign.status,
            daily_budget=campaign.daily_budget,
            region=campaign.region or 'não definida',
            litter_name=getattr(campaign.litter, 'name', None) or 'nenhuma (campanha geral)',
            max_auto_budget_change_percent=max_pct,
        )

    def _campaign_summary_payload(self) -> dict:
        campaign = self.campaign
        campaign.refresh_from_db()
        metrics = list(campaign.metrics.order_by('-date')[:7].values(
            'date', 'impressions', 'clicks', 'cost', 'conversions', 'cost_per_conversion',
        ))
        return {
            'name': campaign.name,
            'status': campaign.status,
            'daily_budget': str(campaign.daily_budget),
            'region': campaign.region,
            'landing_url': campaign.landing_url,
            'ad_headlines': campaign.ad_headlines,
            'ad_descriptions': campaign.ad_descriptions,
            'ad_keywords': campaign.ad_keywords,
            'error_message': campaign.error_message,
            'recent_metrics': [
                {**m, 'date': m['date'].isoformat(), 'cost': str(m['cost']),
                 'cost_per_conversion': str(m['cost_per_conversion']) if m['cost_per_conversion'] is not None else None}
                for m in metrics
            ],
        }

    def _max_auto_budget_change_percent(self) -> int:
        ad_settings = AdvertisingSettings.objects.filter(organization=self.organization).first()
        return ad_settings.max_auto_budget_change_percent if ad_settings else 20

    @staticmethod
    def _plan_payload(plan) -> dict:
        return {
            'plan_id': plan.id,
            'status': plan.status,
            'name': plan.name,
            'litter_id': plan.litter_id,
            'daily_budget': str(plan.daily_budget),
            'region': plan.region,
            'radius_km': plan.radius_km,
            'bid_strategy': plan.bid_strategy,
            'landing_url': plan.landing_url,
            'headlines': plan.headlines,
            'descriptions': plan.descriptions,
            'keywords': plan.keywords,
            'negative_keywords': plan.negative_keywords,
            'conversions_tracked': plan.conversions_tracked,
            'tracking_notes': plan.tracking_notes,
            'justification': plan.justification,
        }

    def _execute_tool(self, name: str, arguments: dict) -> dict:
        try:
            if name == 'get_campaign_summary':
                return self._campaign_summary_payload()

            if name == 'sync_metrics':
                synced = MetricsService().sync_campaign_metrics(self.campaign)
                return {'synced_days': synced, **self._campaign_summary_payload()}

            if name == 'get_search_terms':
                terms = CampaignService().get_search_terms(self.campaign, arguments.get('days_back', 30))
                return {'search_terms': terms}

            if name == 'get_lead_funnel':
                return lead_funnel_service.funnel_summary(self.campaign)

            if name == 'get_decision_history':
                limit = arguments.get('limit', 10)
                decisions = AdAgentDecision.objects.filter(campaign=self.campaign)[:limit]
                return {'decisions': [{
                    'timestamp': d.created_at.isoformat(),
                    'action': d.action,
                    'before': d.before,
                    'after': d.after,
                    'reason': d.reason,
                    'hypothesis': d.hypothesis,
                    'performed_by': d.performed_by,
                    'approval_status': d.approval_status,
                } for d in decisions]}

            if name == 'pause_campaign':
                campaign = CampaignService().pause_campaign(
                    self.organization, self.campaign.id, reason=arguments.get('reason', ''), performed_by='agent',
                )
                self.campaign = campaign
                return {'status': campaign.status, 'error_message': campaign.error_message}

            if name == 'resume_campaign':
                campaign = CampaignService().resume_campaign(
                    self.organization, self.campaign.id, reason=arguments.get('reason', ''), performed_by='agent',
                )
                self.campaign = campaign
                return {'status': campaign.status, 'error_message': campaign.error_message}

            if name == 'update_daily_budget':
                new_budget = float(arguments['daily_budget'])
                current_budget = float(self.campaign.daily_budget)
                change_percent = abs(new_budget - current_budget) / current_budget * 100 if current_budget else 100
                max_pct = self._max_auto_budget_change_percent()

                if change_percent > max_pct and not arguments.get('confirmed'):
                    return {
                        'requires_approval': True,
                        'change_percent': round(change_percent, 1),
                        'max_auto_percent': max_pct,
                        'message': (
                            f'Mudar de R$ {current_budget:.2f} para R$ {new_budget:.2f} é uma variação de '
                            f'{change_percent:.0f}%, acima do limite de auto-execução ({max_pct}%). '
                            'Peça confirmação explícita ao usuário antes de chamar esta ferramenta de novo com confirmed=true.'
                        ),
                    }

                campaign = CampaignService().update_daily_budget(
                    self.organization, self.campaign.id, new_budget,
                    reason=arguments.get('reason', ''), hypothesis=arguments.get('hypothesis', ''),
                    performed_by='agent',
                    approval_status='confirmed_by_user' if arguments.get('confirmed') else 'auto_executed',
                )
                self.campaign = campaign
                return {'daily_budget': str(campaign.daily_budget), 'error_message': campaign.error_message}

            if name == 'evaluate_decision':
                try:
                    decision = AdAgentDecision.objects.get(campaign=self.campaign, id=arguments['decision_id'])
                except AdAgentDecision.DoesNotExist:
                    return {'error': 'Decisão não encontrada para esta campanha.'}

                before_snapshot = decision.metrics_snapshot or {}
                if not before_snapshot:
                    return {
                        'has_before_snapshot': False,
                        'message': (
                            'Esta decisão não tem um snapshot de métricas gravado no momento em que foi tomada '
                            '(decisão anterior à instrumentação de snapshots). Não é possível comparar antes/depois '
                            'com dados reais — não invente números, apenas informe isso ao usuário.'
                        ),
                        'decision': {
                            'action': decision.action, 'before': decision.before, 'after': decision.after,
                            'reason': decision.reason, 'created_at': decision.created_at.isoformat(),
                        },
                    }

                after_snapshot = MetricsService().build_snapshot(self.campaign)
                numeric_keys = [
                    'cost', 'impressions', 'clicks', 'ctr', 'average_cpc', 'conversions', 'conversion_rate',
                    'total_leads', 'cost_per_lead', 'qualified_leads', 'cost_per_qualified_lead',
                    'negotiations', 'reservations', 'sales', 'cac',
                ]
                deltas = {}
                for key in numeric_keys:
                    before_val = before_snapshot.get(key)
                    after_val = after_snapshot.get(key)
                    if before_val is None or after_val is None:
                        deltas[key] = None
                    else:
                        deltas[key] = round(after_val - before_val, 2)

                return {
                    'has_before_snapshot': True,
                    'decision': {
                        'action': decision.action, 'before': decision.before, 'after': decision.after,
                        'reason': decision.reason, 'hypothesis': decision.hypothesis,
                        'created_at': decision.created_at.isoformat(),
                    },
                    'metrics_before': before_snapshot,
                    'metrics_now': after_snapshot,
                    'delta': deltas,
                }

            if name == 'add_negative_keywords':
                briefing = getattr(self.campaign, 'briefing', None)
                protected = {kw.lower() for kw in (briefing.do_not_negate_keywords if briefing else [])}
                requested = arguments.get('keywords', [])
                blocked = [kw for kw in requested if kw.lower() in protected]
                allowed = [kw for kw in requested if kw.lower() not in protected]
                campaign = CampaignService().add_negative_keywords(
                    self.organization, self.campaign.id, allowed,
                    reason=arguments.get('reason', ''), performed_by='agent',
                )
                self.campaign = campaign
                result = {'added': allowed, 'error_message': campaign.error_message}
                if blocked:
                    result['blocked_by_briefing'] = blocked
                return result

            if name == 'propose_campaign_plan':
                litter_id = arguments.get('litter_id') or getattr(self.campaign, 'litter_id', None)
                litter = Litter.objects.filter(organization=self.organization, id=litter_id).first() if litter_id else None
                plan = CampaignPlanService().propose(
                    organization=self.organization,
                    litter=litter,
                    data={
                        'daily_budget': arguments['daily_budget'],
                        'name': arguments.get('name', ''),
                        'region': arguments.get('region', ''),
                        'radius_km': arguments.get('radius_km'),
                        'audience_description': arguments.get('audience_description', ''),
                        'negative_keywords': arguments.get('negative_keywords', []),
                    },
                    justification=arguments.get('justification', ''),
                )
                return {'requires_approval': True, 'plan': self._plan_payload(plan)}

            if name == 'execute_campaign_plan':
                if not arguments.get('confirmed'):
                    try:
                        plan = AdCampaignPlan.objects.get(organization=self.organization, id=arguments['plan_id'])
                    except AdCampaignPlan.DoesNotExist:
                        return {'error': 'Plano não encontrado.'}
                    return {
                        'requires_approval': True,
                        'plan': self._plan_payload(plan),
                        'message': 'Peça confirmação explícita ao usuário antes de chamar esta ferramenta de novo com confirmed=true.',
                    }
                campaign = CampaignPlanService().execute(organization=self.organization, plan_id=arguments['plan_id'])
                return {
                    'status': campaign.status, 'campaign_id': campaign.id,
                    'external_campaign_id': campaign.external_campaign_id, 'error_message': campaign.error_message,
                }

            if name == 'reject_campaign_plan':
                plan = CampaignPlanService().reject(organization=self.organization, plan_id=arguments['plan_id'])
                return {'status': plan.status}

            if name == 'fetch_official_documentation':
                return fetch_official_documentation(arguments['url'])

            return {'error': f'Ferramenta desconhecida: {name}'}
        except GoogleAdsProviderError as exc:
            return {'error': exc.user_message}
        except Exception as exc:
            logger.exception(f'AdvertisingAgentService tool "{name}" failed')
            return {'error': str(exc)}

    def chat(self, *, user_message: str, openai_api_key: str) -> AdChatMessage:
        AdChatMessage.objects.create(
            organization=self.organization, campaign=self.campaign, role='user', content=user_message,
        )

        history = list(
            self.campaign.chat_messages.order_by('-created_at')[:MAX_HISTORY_MESSAGES].values('role', 'content')
        )[::-1]

        messages = [{'role': 'system', 'content': self._build_system_prompt()}]
        messages += [{'role': m['role'], 'content': m['content']} for m in history]

        client = self._get_openai(openai_api_key)
        actions_taken = []

        for _ in range(MAX_TOOL_ROUNDTRIPS):
            response = client.chat.completions.create(
                model='gpt-4o',
                messages=messages,
                tools=TOOLS,
                temperature=0.3,
                max_tokens=800,
            )
            choice = response.choices[0].message

            if not choice.tool_calls:
                reply_text = choice.content or ''
                return AdChatMessage.objects.create(
                    organization=self.organization, campaign=self.campaign, role='assistant',
                    content=reply_text, actions_taken=actions_taken,
                )

            messages.append({
                'role': 'assistant',
                'content': choice.content or '',
                'tool_calls': [tc.model_dump() for tc in choice.tool_calls],
            })
            for tool_call in choice.tool_calls:
                args = json.loads(tool_call.function.arguments or '{}')
                result = self._execute_tool(tool_call.function.name, args)
                if tool_call.function.name not in ('get_campaign_summary', 'sync_metrics', 'get_search_terms', 'get_lead_funnel', 'get_decision_history', 'evaluate_decision', 'fetch_official_documentation'):
                    actions_taken.append({'tool': tool_call.function.name, 'arguments': args, 'result': result})
                messages.append({
                    'role': 'tool',
                    'tool_call_id': tool_call.id,
                    'content': json.dumps(result, ensure_ascii=False),
                })

        return AdChatMessage.objects.create(
            organization=self.organization, campaign=self.campaign, role='assistant',
            content='Desculpe, não consegui concluir essa solicitação agora. Pode tentar reformular?',
            actions_taken=actions_taken,
        )
