"""
Geração de sugestões de anúncio (headline/description/keyword) via IA, focada no
público-alvo descrito pelo usuário na tela de "Promover". Usa a mesma OpenAI API
key já configurada por tenant (apps.core.models.AgentConfig.openai_api_key —
o mesmo classificador de leads em apps/qualifier/ai_classifier.py já usa essa key).

Sempre com fallback seguro: qualquer erro (sem key, IA fora do ar, resposta
inválida) cai de volta no gerador de template (copy_suggestions.suggest_ad_copy),
nunca quebra a criação da campanha.
"""
import json
import logging

from openai import OpenAI

from apps.advertising.services.copy_suggestions import suggest_ad_copy

logger = logging.getLogger('apps')

HEADLINE_MAX_LEN = 30
DESCRIPTION_MAX_LEN = 90

SYSTEM_PROMPT = """Você é um especialista em Google Ads (campanhas de Pesquisa) para canis \
de cães de raça. Gere sugestões de anúncio em português do Brasil, focadas especificamente \
no público-alvo descrito pelo usuário.

Regras rígidas do Google Ads Search (Responsive Search Ad):
- "headlines": de 6 a 10 textos, cada um com NO MÁXIMO 30 caracteres.
- "descriptions": de 3 a 4 textos, cada um com NO MÁXIMO 90 caracteres.
- "keywords": de 5 a 10 termos de busca curtos e relevantes, sem sinais de pontuação.

Responda SOMENTE em JSON no formato:
{"headlines": ["..."], "descriptions": ["..."], "keywords": ["..."]}"""


def generate_ad_copy(*, litter, user_profile, audience_description: str, openai_api_key: str) -> dict:
    """
    Gera sugestões via IA a partir dos dados da ninhada + público-alvo descrito.
    Levanta exceção se a IA falhar — o chamador decide o fallback.
    """
    breed = (user_profile.kennel_breed if user_profile and user_profile.kennel_breed else None)
    if not breed:
        first_puppy = litter.puppies.first() if hasattr(litter, 'puppies') else None
        breed = getattr(first_puppy, 'breed', None) or 'Border Collie'

    city = user_profile.kennel_city if user_profile else ''
    state = user_profile.kennel_state if user_profile else ''
    location = f'{city}/{state}' if city and state else (city or state or '')

    user_prompt = (
        f'Raça: {breed}\n'
        f'Localização do canil: {location or "não informada"}\n'
        f'Nome da ninhada: {litter.name}\n'
        f'Notas da ninhada: {litter.notes or "sem notas adicionais"}\n'
        f'Público-alvo descrito pelo usuário: {audience_description}\n'
    )

    client = OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model='gpt-4o',
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_prompt},
        ],
        temperature=0.7,
        max_tokens=700,
        response_format={'type': 'json_object'},
    )
    result = json.loads(response.choices[0].message.content.strip())

    headlines = [str(h)[:HEADLINE_MAX_LEN] for h in result.get('headlines', []) if str(h).strip()]
    descriptions = [str(d)[:DESCRIPTION_MAX_LEN] for d in result.get('descriptions', []) if str(d).strip()]
    keywords = [str(k).strip() for k in result.get('keywords', []) if str(k).strip()]

    if len(headlines) < 3 or len(descriptions) < 2 or not keywords:
        raise ValueError('Resposta da IA incompleta (headlines/descriptions/keywords insuficientes).')

    return {
        'ad_headlines': headlines,
        'ad_descriptions': descriptions,
        'ad_keywords': keywords,
    }


def generate_ad_copy_with_fallback(*, litter, user_profile, audience_description: str, openai_api_key: str) -> dict:
    if audience_description and openai_api_key:
        try:
            return generate_ad_copy(
                litter=litter, user_profile=user_profile,
                audience_description=audience_description, openai_api_key=openai_api_key,
            )
        except Exception as exc:
            logger.warning(f'ai_copy_service: falha na geração por IA, usando template ({exc})')
    return suggest_ad_copy(litter, user_profile)
