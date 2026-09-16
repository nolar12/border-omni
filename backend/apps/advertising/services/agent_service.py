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
claramente; se ele recusar ou pedir para descartar, chame reject_campaign_plan.

Para "qual cidade está melhor?" use get_city_breakdown; para "qual palavra-chave
trouxe compradores/reservas?" use get_keyword_breakdown — lembre-se de que
keyword (o termo do ValueTrack que casou o clique) e search_term (o texto real
digitado, de get_search_terms) são coisas diferentes, nunca trate como
sinônimos."""

PROACTIVE_REVIEW_INSTRUCTION = """Faça uma revisão periódica e autônoma desta campanha — ninguém está
perguntando nada agora, isso roda sozinho, agendado. Sincronize métricas se fizer sentido, olhe o
desempenho recente, o funil comercial (por cidade e por palavra-chave) e o histórico de decisões.

Nesta revisão você só pode LER dados — nunca execute uma mudança (pausar, orçamento, negativas,
criar campanha); no máximo, sugira e diga que o usuário pode pedir para executar no chat depois.

Se houver algo relevante para o dono do canil saber (uma cidade ou keyword se destacando bem ou mal,
desperdício de orçamento, um alerta de status, uma decisão anterior que já dá para avaliar), escreva
um resumo curto e objetivo em português. Se, depois de olhar os dados, não houver nada novo ou
relevante desde a última vez, responda EXATAMENTE com a palavra NADA_A_REPORTAR e mais nada."""

READ_ONLY_TOOL_NAMES = {
    'get_campaign_summary', 'sync_metrics', 'get_search_terms', 'get_lead_funnel',
    'get_city_breakdown', 'get_keyword_breakdown', 'get_decision_history',
    'evaluate_decision', 'fetch_official_documentation', 'get_campaign_diagnostics',
}

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
        'name': 'get_campaign_diagnostics',
        'description': (
            'Traz o motivo REAL de a campanha não estar veiculando (campaign.primary_status_reasons — ex.: '
            'AD_GROUP_ADS_PAUSED, PAUSED, PENDING_REVIEW, DISAPPROVED) e a força do anúncio (ad_strength: '
            'POOR/AVERAGE/GOOD/EXCELLENT) e status de aprovação de política de cada anúncio — a mesma informação '
            'que o painel "Campaign diagnostics" do Google Ads mostra. Use sempre que o usuário perguntar por que '
            'a campanha está "not eligible"/parada/sem veicular, ou quando for investigar problemas por conta própria.'
        ),
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
    }},
    {'type': 'function', 'function': {
        'name': 'update_ad_content',
        'description': (
            'Atualiza as headlines e descriptions do anúncio (Responsive Search Ad) já publicado — use quando o '
            'ad_strength estiver POOR/AVERAGE ou o usuário pedir para melhorar o texto do anúncio. Google recomenda '
            'até 15 headlines (≤30 caracteres cada) e até 4 descriptions (≤90 caracteres cada), com variedade real '
            '(não repita a mesma ideia com palavras diferentes) — inclua preço, localização, diferenciais, urgência, '
            'chamada para ação. Pode executar direto, sem pedir confirmação — é conteúdo, não gasto.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'headlines': {'type': 'array', 'items': {'type': 'string'}, 'description': '8 a 15 headlines, cada uma com no máximo 30 caracteres.'},
                'descriptions': {'type': 'array', 'items': {'type': 'string'}, 'description': '2 a 4 descriptions, cada uma com no máximo 90 caracteres.'},
                'reason': {'type': 'string'},
            },
            'required': ['headlines', 'descriptions'],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'get_lead_funnel',
        'description': 'Retorna o funil comercial dos leads originados desta campanha (visitas, cliques no WhatsApp, e leads por estágio: NEW/CONTACTED/QUALIFIED/UNQUALIFIED/NEGOTIATING/RESERVED/SOLD/LOST) — dados reais do CRM, não do Google Ads.',
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
    }},
    {'type': 'function', 'function': {
        'name': 'get_city_breakdown',
        'description': (
            'Quebra os leads desta campanha por cidade (dado real do CRM: quantos leads, qualificados, '
            'reservas e vendas por cidade) — use para responder "qual cidade está performando melhor?". '
            'Não inclui gasto por cidade (essa quebra de custo por localidade ainda não existe) — nunca '
            'estime ou invente um custo por cidade; fale só do que a ferramenta retornar.'
        ),
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
    }},
    {'type': 'function', 'function': {
        'name': 'get_keyword_breakdown',
        'description': (
            'Quebra os leads desta campanha pela keyword do ValueTrack que casou o clique (não é o texto '
            'literal que a pessoa buscou — isso é o search_term, de get_search_terms) — use para responder '
            '"qual palavra-chave trouxe compradores/reservas/leads qualificados?".'
        ),
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
            'ninhada") e a salva como rascunho — NUNCA cria a campanha de verdade. Prefira sempre `ad_groups` '
            '(vários grupos temáticos, cada um com suas keywords em Exact/Phrase e ≥1 RSA) em vez de deixar '
            'a IA gerar um único grupo genérico — só omita ad_groups se o usuário pedir algo muito simples '
            'de propósito. Retorna o plano completo para você apresentar em português, de forma legível, e '
            'pedir aprovação explícita ao usuário antes de chamar execute_campaign_plan. Se litter_id não for '
            'informado, assume a ninhada desta campanha atual.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'daily_budget': {'type': 'number', 'description': 'Orçamento diário proposto em reais (R$).'},
                'litter_id': {'type': 'integer', 'description': 'ID da ninhada a promover; se omitido, usa a ninhada da campanha atual (se houver).'},
                'name': {'type': 'string'},
                'region': {'type': 'string', 'description': 'Cidades separadas por vírgula.'},
                'radius_km': {'type': 'integer'},
                'audience_description': {'type': 'string', 'description': 'Público-alvo — usado só se ad_groups não for informado, para gerar headlines/descriptions por IA no formato legado (1 grupo).'},
                'ad_groups': {
                    'type': 'array',
                    'description': 'Estrutura recomendada: vários ad groups temáticos (ex.: "Comprar", "Preço", "Localização").',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'name': {'type': 'string'},
                            'keywords': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'text': {'type': 'string'},
                                        'match_type': {'type': 'string', 'enum': ['EXACT', 'PHRASE', 'BROAD']},
                                    },
                                    'required': ['text'],
                                },
                            },
                            'ads': {
                                'type': 'array',
                                'description': '≥2 RSAs por grupo, com diversidade real de proposta.',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'headlines': {'type': 'array', 'items': {'type': 'string'}},
                                        'descriptions': {'type': 'array', 'items': {'type': 'string'}},
                                    },
                                    'required': ['headlines', 'descriptions'],
                                },
                            },
                        },
                        'required': ['name', 'keywords', 'ads'],
                    },
                },
                'negative_keywords': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'text': {'type': 'string'},
                            'match_type': {'type': 'string', 'enum': ['EXACT', 'PHRASE', 'BROAD']},
                        },
                        'required': ['text'],
                    },
                },
                'bid_strategy': {'type': 'string', 'description': 'Informativo — campanhas novas sempre nascem em Manual CPC (ver skill: automatizado exige histórico).'},
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
        'name': 'add_keywords',
        'description': (
            'Adiciona palavra(s)-chave positivas a um ad group JÁ EXISTENTE desta campanha (nunca cria '
            'ad group novo — use create_ad_group pra isso). Informe o nome (ou parte do nome) do ad '
            'group de destino, exatamente como aparece nesta campanha.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'ad_group_name': {'type': 'string', 'description': 'Nome (ou parte do nome) do ad group de destino.'},
                'keywords': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'text': {'type': 'string'},
                            'match_type': {'type': 'string', 'enum': ['EXACT', 'PHRASE', 'BROAD']},
                        },
                        'required': ['text'],
                    },
                },
                'reason': {'type': 'string'},
            },
            'required': ['ad_group_name', 'keywords'],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'set_keyword_status',
        'description': (
            'Pausa ou reativa uma keyword individual já configurada — não confunda com negativar '
            '(isso não bloqueia buscas, só ativa/desativa a keyword como critério positivo).'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'keyword_text': {'type': 'string'},
                'match_type': {
                    'type': 'string', 'enum': ['EXACT', 'PHRASE', 'BROAD'],
                    'description': 'Use para desambiguar se a mesma keyword existir em mais de um match type/ad group.',
                },
                'status': {'type': 'string', 'enum': ['ENABLED', 'PAUSED']},
                'reason': {'type': 'string'},
            },
            'required': ['keyword_text', 'status'],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'create_ad_group',
        'description': (
            'Cria um ad group NOVO nesta campanha já existente (ex.: testar um tema/keyword diferente '
            'sem mexer nos grupos atuais) — nasce PAUSED, precisa ser ativado manualmente depois. Não '
            'cria campanha nova (use propose_campaign_plan pra isso).'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'description': 'Nome do novo ad group (curto, descreve o tema).'},
                'keywords': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'text': {'type': 'string'},
                            'match_type': {'type': 'string', 'enum': ['EXACT', 'PHRASE', 'BROAD']},
                        },
                        'required': ['text'],
                    },
                },
                'ads': {
                    'type': 'array',
                    'description': '1 ou mais RSAs para o grupo.',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'headlines': {'type': 'array', 'items': {'type': 'string'}},
                            'descriptions': {'type': 'array', 'items': {'type': 'string'}},
                        },
                        'required': ['headlines', 'descriptions'],
                    },
                },
                'reason': {'type': 'string'},
                'hypothesis': {'type': 'string'},
            },
            'required': ['name'],
        },
    }},
    {'type': 'function', 'function': {
        'name': 'update_bidding_strategy',
        'description': (
            'Troca a estratégia de lance da campanha (Manual CPC / Maximize Conversions / Target CPA) — '
            'SEMPRE mudança estrutural relevante, exige confirmação explícita do usuário. Sem '
            'confirmed=true, a ferramenta NÃO executa e retorna requires_approval=true. Só recomende '
            'Maximize Conversions/Target CPA quando já houver volume de conversão razoável (ver skill — '
            'estratégias automatizadas com pouco histórico aprendem mal).'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'strategy': {'type': 'string', 'enum': ['MANUAL_CPC', 'MAXIMIZE_CONVERSIONS', 'TARGET_CPA']},
                'target_cpa': {'type': 'number', 'description': 'Obrigatório só para TARGET_CPA (custo por aquisição alvo, em R$).'},
                'reason': {'type': 'string'},
                'hypothesis': {'type': 'string'},
                'confirmed': {'type': 'boolean', 'description': 'true somente após o usuário confirmar explicitamente.'},
            },
            'required': ['strategy'],
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

# Subconjunto de TOOLS oferecido na revisão proativa (agendada, sem humano no
# loop) — só leitura. A restrição é reforçada pela própria API da OpenAI (o
# modelo não consegue chamar uma ferramenta que não está nesta lista), não só
# pelo texto do prompt.
PROACTIVE_TOOLS = [tool for tool in TOOLS if tool['function']['name'] in READ_ONLY_TOOL_NAMES]


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
            # Mesmos números (e mesma função) usados em cada AdAgentDecision — "quanto gastamos",
            # "quantos leads", "quantos qualificados/reservas/vendas" respondem com os dados reais
            # já agregados, em vez de forçar somar recent_metrics na mão.
            'snapshot': MetricsService().build_snapshot(campaign),
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
            'ad_groups': plan.ad_groups,
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

            if name == 'get_campaign_diagnostics':
                return CampaignService().get_campaign_diagnostics(self.campaign)

            if name == 'update_ad_content':
                campaign = CampaignService().update_ad_content(
                    self.organization, self.campaign.id,
                    arguments['headlines'], arguments['descriptions'],
                    reason=arguments.get('reason', ''), performed_by='agent',
                )
                self.campaign = campaign
                return {
                    'ad_headlines': campaign.ad_headlines, 'ad_descriptions': campaign.ad_descriptions,
                    'error_message': campaign.error_message,
                }

            if name == 'get_lead_funnel':
                return lead_funnel_service.funnel_summary(self.campaign)

            if name == 'get_city_breakdown':
                return {'cities': lead_funnel_service.breakdown_by_city(self.campaign)}

            if name == 'get_keyword_breakdown':
                return {'keywords': lead_funnel_service.breakdown_by_keyword(self.campaign)}

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

            if name == 'add_keywords':
                keywords = arguments.get('keywords', [])
                campaign = CampaignService().add_keywords(
                    self.organization, self.campaign.id, arguments['ad_group_name'], keywords,
                    reason=arguments.get('reason', ''), performed_by='agent',
                )
                self.campaign = campaign
                if campaign.error_message:
                    return {'error_message': campaign.error_message}
                return {'status': 'ok', 'ad_group_name': arguments['ad_group_name'], 'keywords_added': keywords}

            if name == 'set_keyword_status':
                campaign = CampaignService().set_keyword_status(
                    self.organization, self.campaign.id, arguments['keyword_text'], arguments['status'],
                    match_type=arguments.get('match_type'), reason=arguments.get('reason', ''), performed_by='agent',
                )
                self.campaign = campaign
                if campaign.error_message:
                    return {'error_message': campaign.error_message}
                return {'status': arguments['status'], 'keyword_text': arguments['keyword_text']}

            if name == 'create_ad_group':
                campaign = CampaignService().create_ad_group(
                    self.organization, self.campaign.id, arguments['name'],
                    keywords=arguments.get('keywords', []), ads=arguments.get('ads', []),
                    reason=arguments.get('reason', ''), hypothesis=arguments.get('hypothesis', ''), performed_by='agent',
                )
                self.campaign = campaign
                if campaign.error_message:
                    return {'error_message': campaign.error_message}
                return {'status': 'created', 'ad_group_name': arguments['name']}

            if name == 'update_bidding_strategy':
                strategy = arguments['strategy']
                if not arguments.get('confirmed'):
                    return {
                        'requires_approval': True,
                        'message': (
                            f'Trocar a estratégia de lance para {strategy} é sempre uma mudança estrutural '
                            'relevante. Explique a mudança ao usuário e só chame esta ferramenta de novo '
                            'com confirmed=true depois que ele concordar explicitamente.'
                        ),
                    }
                campaign = CampaignService().update_bidding_strategy(
                    self.organization, self.campaign.id, strategy, target_cpa=arguments.get('target_cpa'),
                    reason=arguments.get('reason', ''), hypothesis=arguments.get('hypothesis', ''),
                    performed_by='agent', approval_status='confirmed_by_user',
                )
                self.campaign = campaign
                if campaign.error_message:
                    return {'error_message': campaign.error_message}
                return {'strategy': strategy, 'target_cpa': arguments.get('target_cpa')}

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
                        'ad_groups': arguments.get('ad_groups', []),
                        'negative_keywords': arguments.get('negative_keywords', []),
                        'bid_strategy': arguments.get('bid_strategy', 'manual_cpc'),
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

    def _recent_history_messages(self) -> list[dict]:
        history = list(
            self.campaign.chat_messages.order_by('-created_at')[:MAX_HISTORY_MESSAGES].values('role', 'content')
        )[::-1]
        return [{'role': m['role'], 'content': m['content']} for m in history]

    def _run_completion_loop(self, *, messages: list[dict], tools: list[dict], client: OpenAI) -> tuple[str | None, list]:
        """
        Loop de tool-calling compartilhado por chat() (interativo) e
        run_proactive_review() (agendado) — a única diferença entre os dois é
        QUAIS tools são oferecidas e o que entra em `messages`, nunca a lógica
        de execução em si. Retorna (texto_final_ou_None, ações_executadas).
        """
        allowed_names = {tool['function']['name'] for tool in tools}
        actions_taken = []
        for _ in range(MAX_TOOL_ROUNDTRIPS):
            response = client.chat.completions.create(
                model='gpt-4o',
                messages=messages,
                tools=tools,
                temperature=0.3,
                max_tokens=800,
            )
            choice = response.choices[0].message

            if not choice.tool_calls:
                return choice.content or '', actions_taken

            messages.append({
                'role': 'assistant',
                'content': choice.content or '',
                'tool_calls': [tc.model_dump() for tc in choice.tool_calls],
            })
            for tool_call in choice.tool_calls:
                args = json.loads(tool_call.function.arguments or '{}')
                # Defesa em profundidade: nunca executa uma tool fora da lista
                # oferecida nesta chamada — não confia só na OpenAI respeitar
                # o `tools=` enviado (importante sobretudo na revisão proativa,
                # que roda sem humano no loop e só pode ler dados).
                if tool_call.function.name not in allowed_names:
                    result = {'error': f'Ferramenta "{tool_call.function.name}" não está disponível neste contexto.'}
                else:
                    result = self._execute_tool(tool_call.function.name, args)
                    if tool_call.function.name not in READ_ONLY_TOOL_NAMES:
                        actions_taken.append({'tool': tool_call.function.name, 'arguments': args, 'result': result})
                messages.append({
                    'role': 'tool',
                    'tool_call_id': tool_call.id,
                    'content': json.dumps(result, ensure_ascii=False),
                })

        return None, actions_taken

    def chat(self, *, user_message: str, openai_api_key: str) -> AdChatMessage:
        AdChatMessage.objects.create(
            organization=self.organization, campaign=self.campaign, role='user', content=user_message,
        )

        messages = [{'role': 'system', 'content': self._build_system_prompt()}]
        messages += self._recent_history_messages()

        client = self._get_openai(openai_api_key)
        reply_text, actions_taken = self._run_completion_loop(messages=messages, tools=TOOLS, client=client)

        if reply_text is None:
            reply_text = 'Desculpe, não consegui concluir essa solicitação agora. Pode tentar reformular?'

        return AdChatMessage.objects.create(
            organization=self.organization, campaign=self.campaign, role='assistant',
            content=reply_text, actions_taken=actions_taken,
        )

    def run_proactive_review(self, *, openai_api_key: str) -> AdChatMessage | None:
        """
        Revisão agendada, sem humano no loop — só ferramentas de LEITURA
        (PROACTIVE_TOOLS). Não persiste nada se o modelo concluir que não há
        nada relevante desde a última vez (sentinela NADA_A_REPORTAR), para
        não poluir o chat com mensagens vazias toda semana.
        """
        messages = [{'role': 'system', 'content': self._build_system_prompt()}]
        messages += self._recent_history_messages()
        messages.append({'role': 'user', 'content': PROACTIVE_REVIEW_INSTRUCTION})

        client = self._get_openai(openai_api_key)
        reply_text, actions_taken = self._run_completion_loop(messages=messages, tools=PROACTIVE_TOOLS, client=client)

        if not reply_text or reply_text.strip().upper().startswith('NADA_A_REPORTAR'):
            return None

        return AdChatMessage.objects.create(
            organization=self.organization, campaign=self.campaign, role='assistant',
            content=reply_text, actions_taken=actions_taken, is_proactive=True,
        )
