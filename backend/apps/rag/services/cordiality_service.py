import json
import logging
import random
import re

from datetime import datetime
from openai import OpenAI

import pytz

logger = logging.getLogger('apps')

SP_TZ = pytz.timezone('America/Sao_Paulo')

GREETINGS = {
    'morning': [
        "Bom dia, {name}!",
        "Olá {name}, bom dia!",
        "Bom dia! Tudo bem, {name}?",
    ],
    'afternoon': [
        "Boa tarde, {name}!",
        "Olá {name}, boa tarde!",
        "Boa tarde! Como vai, {name}?",
    ],
    'evening': [
        "Boa noite, {name}!",
        "Olá {name}, boa noite!",
        "Boa noite! Tudo bem, {name}?",
    ],
}

SHORT_GREETINGS = [
    "Olá novamente, {name}!",
    "Oi {name}!",
    "{name}, tudo bem?",
]

DELAY_ACKNOWLEDGMENTS = [
    "Obrigado por aguardar.",
    "Desculpe pela demora na resposta.",
    "Agradeço a paciência.",
    "Obrigado pela compreensão com o tempo de resposta.",
]

CLOSINGS = [
    "Qualquer dúvida, estamos à disposição.",
    "Conte conosco para o que precisar.",
    "Se surgir qualquer outra questão, é só chamar.",
    "Permanecemos à disposição para ajudar.",
    "Estamos sempre por aqui caso precise.",
    "Ficamos à disposição para mais esclarecimentos.",
    "Não hesite em nos procurar se precisar de algo mais.",
]

TONE_ANALYSIS_PROMPT = """\
Você é um especialista em análise de tom de comunicação empresarial.

## Sua Missão
Analisar se a mensagem do agente contém tom negativo, grosseiro, irritado ou excessivamente seco.

## Critérios de Análise

Identifique se a mensagem possui:
- Tom grosseiro ou rude
- Irritação ou impaciência
- Frieza excessiva ou indiferença
- Linguagem passivo-agressiva
- Respostas secas demais ou monossilábicas
- Falta de profissionalismo
- Respostas que parecem "dar bronca" no cliente

## Formato de Resposta

Retorne APENAS um objeto JSON válido (sem markdown):
{
  "has_negative_tone": true/false,
  "tone_type": "grosseiro|irritado|seco|passivo_agressivo|neutro",
  "severity": 1-10,
  "issues": ["lista de problemas identificados"]
}"""

TONE_CORRECTION_PROMPT = """\
Você é um especialista em comunicação profissional e empática.

## Sua Missão
Corrigir o tom negativo da mensagem, tornando-a profissional e cordial,
SEM alterar o conteúdo informativo.

## Regras OBRIGATÓRIAS

1. Mantenha 100% das informações, valores, datas e dados da mensagem original
2. NÃO invente informações novas
3. NÃO adicione saudação no início (será adicionada separadamente)
4. NÃO adicione fechamento no final (será adicionado separadamente)
5. Remova qualquer tom de irritação, grosseria ou impaciência
6. Substitua linguagem passivo-agressiva por linguagem neutra e cordial
7. Transforme respostas secas em respostas completas e educadas
8. Use linguagem profissional mas acolhedora
9. NÃO use markdown, emojis ou formatação especial

## Exemplos de Correção

ANTES: "Já expliquei isso antes. Você precisa confirmar os dados."
DEPOIS: "Conforme informado anteriormente, precisamos da sua confirmação dos dados para prosseguir."

ANTES: "Não é assim que funciona."
DEPOIS: "Na verdade, o procedimento funciona da seguinte forma:"

ANTES: "Isso já foi respondido."
DEPOIS: "Conforme mencionamos, a informação sobre este assunto é a seguinte:"

ANTES: "Você não enviou os documentos."
DEPOIS: "Verificamos que ainda não recebemos os documentos necessários."

ANTES: "Ok."
DEPOIS: "Certo, entendido."

Retorne APENAS o texto corrigido, sem explicações ou comentários."""

CORDIALITY_PROMPT = """\
Você é um especialista em comunicação cordial e empática para atendimento ao cliente.

## Sua Missão
Transformar a mensagem do agente para torná-la mais cordial, empática e humana,
SEM alterar o conteúdo informativo.

## Regras OBRIGATÓRIAS

1. Mantenha 100% das informações técnicas, valores, datas e dados da mensagem original
2. NÃO invente informações novas
3. NÃO adicione saudação no início (será adicionada separadamente)
4. NÃO adicione fechamento no final (será adicionado separadamente)
5. Use linguagem natural e conversacional em português do Brasil
6. NÃO use markdown, emojis ou formatação especial
7. Suavize linguagem muito direta ou fria
8. Adicione conectores empáticos quando apropriado
9. Mantenha o texto conciso - não expanda desnecessariamente

## Exemplos de Transformação

ANTES: "Confirmação necessária para prosseguir."
DEPOIS: "Assim que você confirmar, podemos dar continuidade ao processo."

ANTES: "Não há recolhimentos pendentes."
DEPOIS: "Fico feliz em informar que não há recolhimentos pendentes."

ANTES: "Segue o documento em anexo."
DEPOIS: "Segue em anexo o documento solicitado."

Retorne APENAS o texto transformado, sem explicações ou comentários."""

MIN_LENGTH_FOR_AI = 30

GREETING_PATTERNS = [
    re.compile(r'^\s*(bom\s+dia|boa\s+tarde|boa\s+noite|olá|oi|prezad[oa])', re.IGNORECASE),
]

CLOSING_PATTERNS = [
    re.compile(r'(qualquer\s+dúvida|estamos\s+à\s+disposição|conte\s+conosco)', re.IGNORECASE),
    re.compile(r'(atenciosamente|cordialmente|abraços?|att\.?)', re.IGNORECASE),
    re.compile(r'(é\s+só\s+chamar|permanecemos|ficamos\s+à\s+disposição)', re.IGNORECASE),
]


def _extract_first_name(lead) -> str:
    full_name = getattr(lead, 'full_name', '') or getattr(lead, 'name', '') or ''
    full_name = full_name.strip()
    if not full_name:
        return 'Cliente'
    first = full_name.split()[0]
    return first.capitalize()


def _time_period() -> str:
    hour = datetime.now(SP_TZ).hour
    if 5 <= hour < 12:
        return 'morning'
    if 12 <= hour < 18:
        return 'afternoon'
    return 'evening'


def _build_greeting(client_name: str) -> str:
    period = _time_period()
    template = random.choice(GREETINGS[period])
    return template.format(name=client_name)


def _build_short_greeting(client_name: str) -> str:
    template = random.choice(SHORT_GREETINGS)
    return template.format(name=client_name)


def _build_closing() -> str:
    return random.choice(CLOSINGS)


def _has_greeting(text: str) -> bool:
    return any(p.match(text) for p in GREETING_PATTERNS)


def _has_closing(text: str) -> bool:
    return any(p.search(text) for p in CLOSING_PATTERNS)


def _format_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    return text.strip()


class CordialityEnhancementService:
    def __init__(self, agent_config, lead):
        self._agent_config = agent_config
        self._lead = lead
        self._client_name = _extract_first_name(lead)
        self._openai = None

    def _get_openai(self) -> OpenAI:
        if not self._openai:
            self._openai = OpenAI(api_key=self._agent_config.openai_api_key)
        return self._openai

    def enhance(self, content: str) -> str:
        """
        Transforma o conteúdo para ser mais cordial e profissional.
        Retorna o conteúdo original em caso de erro ou se a funcionalidade estiver desabilitada.
        """
        if not content or not content.strip():
            return content
        if not self._is_enabled():
            return content

        try:
            working = content.strip()

            # 1. Detectar e corrigir tom negativo
            if self._use_ai() and len(working) >= MIN_LENGTH_FOR_AI:
                tone = self._analyze_tone(working)
                if tone and tone.get('has_negative_tone') and int(tone.get('severity', 0)) >= 4:
                    logger.info(
                        f'Cordiality: tom negativo detectado ({tone.get("tone_type")}, '
                        f'severidade {tone.get("severity")})'
                    )
                    corrected = self._correct_negative_tone(working)
                    if corrected:
                        working = corrected

            # 2. Verificar saudação/fechamento existentes
            already_has_greeting = _has_greeting(working)
            already_has_closing = _has_closing(working)

            # 3. Melhorar tom do conteúdo via IA
            if self._use_ai() and len(working) >= MIN_LENGTH_FOR_AI and not already_has_greeting:
                improved = self._improve_tone(working)
                if improved:
                    working = improved

            # 4. Montar mensagem final
            parts = []
            if not already_has_greeting:
                parts.append(_build_greeting(self._client_name))
            parts.append(working)
            if not already_has_closing:
                parts.append(_build_closing())

            return '\n\n'.join(parts)

        except Exception as e:
            logger.error(f'CordialityEnhancementService.enhance error: {e}')
            return content

    def _analyze_tone(self, text: str) -> dict | None:
        try:
            resp = self._get_openai().chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': TONE_ANALYSIS_PROMPT},
                    {'role': 'user', 'content': text},
                ],
                temperature=0.2,
                max_tokens=300,
            )
            raw = resp.choices[0].message.content.strip()
            cleaned = re.sub(r'```json\n?', '', raw)
            cleaned = re.sub(r'```\n?', '', cleaned).strip()
            return json.loads(cleaned)
        except Exception as e:
            logger.warning(f'CordialityEnhancementService._analyze_tone error: {e}')
            return None

    def _correct_negative_tone(self, text: str) -> str | None:
        try:
            resp = self._get_openai().chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': TONE_CORRECTION_PROMPT},
                    {'role': 'user', 'content': text},
                ],
                temperature=0.3,
                max_tokens=800,
            )
            result = resp.choices[0].message.content.strip()
            return _format_text(result) if result else None
        except Exception as e:
            logger.warning(f'CordialityEnhancementService._correct_negative_tone error: {e}')
            return None

    def _improve_tone(self, text: str) -> str | None:
        try:
            resp = self._get_openai().chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': CORDIALITY_PROMPT},
                    {'role': 'user', 'content': text},
                ],
                temperature=0.4,
                max_tokens=800,
            )
            result = resp.choices[0].message.content.strip()
            return _format_text(result) if result else None
        except Exception as e:
            logger.warning(f'CordialityEnhancementService._improve_tone error: {e}')
            return None

    def _is_enabled(self) -> bool:
        return bool(getattr(self._agent_config, 'cordiality_enabled', False))

    def _use_ai(self) -> bool:
        return bool(
            getattr(self._agent_config, 'cordiality_use_ai', False)
            and self._agent_config.openai_api_key
        )
