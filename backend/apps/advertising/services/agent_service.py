"""
Agente de IA conversacional sobre uma campanha específica (chat na tela de
Anúncios). Usa a mesma OpenAI API key por tenant já usada pelo classificador de
leads (apps/qualifier/ai_classifier.py).

Regra de segurança central: o agente NUNCA mexe direto no banco ou na API do
Google — toda ação passa pelas mesmas CampaignService/MetricsService que a UI
usa. O "tool calling" da OpenAI só decide QUAL método de serviço chamar; quem
executa é sempre a camada de domínio já existente e testada.
"""
import json
import logging

from openai import OpenAI

from apps.advertising.models import AdChatMessage, AdMetric
from apps.advertising.providers import GoogleAdsProviderError
from apps.advertising.services.campaign_service import CampaignService
from apps.advertising.services.metrics_service import MetricsService

logger = logging.getLogger('apps')

MAX_HISTORY_MESSAGES = 20

SYSTEM_PROMPT_TEMPLATE = """Você é o assistente de Omni Ads do Border Omni, ajudando o \
responsável pelo canil a acompanhar e ajustar uma campanha de Google Ads (Pesquisa).

Contexto atual da campanha:
- Nome: {name}
- Status: {status}
- Orçamento diário: R$ {daily_budget}
- Região: {region}
- Ninhada vinculada: {litter_name}

Responda sempre em português do Brasil, de forma direta e objetiva. Use as \
ferramentas disponíveis para consultar métricas reais ou executar ações — nunca \
invente números de desempenho. Antes de aumentar orçamento de forma agressiva \
(mais que o dobro) ou pausar a campanha, confirme com o usuário que é isso mesmo \
que ele quer, a menos que ele já tenha pedido isso claramente na mensagem. Depois \
de executar uma ação, confirme o que foi feito."""

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
        'name': 'pause_campaign',
        'description': 'Pausa a campanha no Google Ads (para de gastar e de exibir anúncios).',
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
    }},
    {'type': 'function', 'function': {
        'name': 'resume_campaign',
        'description': 'Reativa a campanha pausada no Google Ads.',
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
    }},
    {'type': 'function', 'function': {
        'name': 'update_daily_budget',
        'description': 'Altera o orçamento diário da campanha.',
        'parameters': {
            'type': 'object',
            'properties': {'daily_budget': {'type': 'number', 'description': 'Novo orçamento diário em reais (R$).'}},
            'required': ['daily_budget'],
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
        return SYSTEM_PROMPT_TEMPLATE.format(
            name=campaign.name,
            status=campaign.status,
            daily_budget=campaign.daily_budget,
            region=campaign.region or 'não definida',
            litter_name=getattr(campaign.litter, 'name', None) or 'nenhuma (campanha geral)',
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

    def _execute_tool(self, name: str, arguments: dict) -> dict:
        try:
            if name == 'get_campaign_summary':
                return self._campaign_summary_payload()

            if name == 'sync_metrics':
                synced = MetricsService().sync_campaign_metrics(self.campaign)
                return {'synced_days': synced, **self._campaign_summary_payload()}

            if name == 'pause_campaign':
                campaign = CampaignService().pause_campaign(self.organization, self.campaign.id)
                self.campaign = campaign
                return {'status': campaign.status, 'error_message': campaign.error_message}

            if name == 'resume_campaign':
                campaign = CampaignService().resume_campaign(self.organization, self.campaign.id)
                self.campaign = campaign
                return {'status': campaign.status, 'error_message': campaign.error_message}

            if name == 'update_daily_budget':
                campaign = CampaignService().update_daily_budget(
                    self.organization, self.campaign.id, arguments['daily_budget'],
                )
                self.campaign = campaign
                return {'daily_budget': str(campaign.daily_budget), 'error_message': campaign.error_message}

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

        for _ in range(5):  # limite de idas e vindas de tool-calling por mensagem
            response = client.chat.completions.create(
                model='gpt-4o',
                messages=messages,
                tools=TOOLS,
                temperature=0.3,
                max_tokens=700,
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
                if tool_call.function.name != 'get_campaign_summary':
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
