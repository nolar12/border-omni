import json
import logging
import re
from datetime import date, timedelta

from django.conf import settings
from django.utils import timezone
from openai import OpenAI

from .embedding_service import EmbeddingService

logger = logging.getLogger('apps')

RAG_PLANS = {'pro', 'enterprise'}

_EMOJI_RE = re.compile(
    '['
    '\U0001F600-\U0001F64F'
    '\U0001F300-\U0001F5FF'
    '\U0001F680-\U0001F6FF'
    '\U0001F1E0-\U0001F1FF'
    '\U0001F900-\U0001F9FF'
    '\U0001FA00-\U0001FAFF'
    '\U00002702-\U000027B0'
    '\U000024C2-\U0001F251'
    '\u2600-\u26FF'
    '\u2700-\u27BF'
    '\u200d'
    '\ufe0f'
    ']+',
    flags=re.UNICODE,
)


def _clean_name(name: str) -> str:
    """Remove emojis e espaços extras de um nome."""
    return _EMOJI_RE.sub('', name).strip()


def _format_brl(value: int) -> str:
    return f'R$ {int(value):,}'.replace(',', '.')


def _normalized_puppy_price(dog) -> int | None:
    """
    Normaliza preço para manter comunicação comercial com preço único.
    Regra vigente: todos os filhotes custam R$ 4.000, sem variação por sexo/cor.
    """
    return 4000

# Prompt principal do agente — define personalidade e tom
DEFAULT_SYSTEM_PROMPT = (
    "Você é um consultor especialista em Border Collies. "
    "Responda com carinho, de forma informal e humana, como um amigo que entende muito da raça. "
    "Pergunte sempre para qual finalidade o cliente deseja o filhote."
)

# Prompt de refinamento — processa respostas brutas antes de armazenar
REFINEMENT_SYSTEM_PROMPT = """\
Você é um revisor de textos especializado em atendimento ao cliente para venda de filhotes de cachorro.

Sua tarefa é MELHORAR a resposta do atendente antes de salvar como exemplo de boas práticas. Siga estas regras:

1. CORREÇÃO: corrija erros de ortografia, acentuação e gramática (ex: "previsao" → "previsão", "nao" → "não")
2. TOM: mantenha informal, caloroso e humano — como uma conversa de WhatsApp com um especialista amigo
3. FLUIDEZ: reescreva frases truncadas ou confusas para ficarem naturais e fáceis de ler
4. EMOJIS: NÃO use emojis — remova qualquer emoji que esteja no texto original
5. CONTEÚDO: NÃO invente informações, preços ou dados que não estejam no original
6. TAMANHO: não alongue desnecessariamente — mensagens de WhatsApp devem ser diretas
7. FORMATO: preserve negrito (*palavra*) e quebras de linha quando fizerem sentido

Responda APENAS com o texto melhorado, sem comentários ou explicações."""


def _get_supabase():
    from supabase import create_client
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


class RAGService:
    def __init__(self, agent_config):
        self.agent_config = agent_config
        self._openai = None

    def _get_openai(self):
        if not self._openai:
            self._openai = OpenAI(api_key=self.agent_config.openai_api_key)
        return self._openai

    def _plan_name(self) -> str:
        try:
            return self.agent_config.organization.subscription.plan.name
        except Exception:
            return 'free'

    def refine_response(self, raw_response: str) -> str:
        """
        Passa a resposta bruta do atendente por uma camada de refinamento
        (correção gramatical + ajuste de tom) antes de salvar como embedding.
        Retorna o original se o refinamento falhar.
        """
        if not raw_response or not raw_response.strip():
            return raw_response
        # Mensagens muito curtas ou de sistema não precisam de refinamento
        skip_words = ['assumido por', 'IA respond', '👋 Atendimento']
        if any(w in raw_response for w in skip_words) or len(raw_response) < 15:
            return raw_response
        try:
            response = self._get_openai().chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': REFINEMENT_SYSTEM_PROMPT},
                    {'role': 'user', 'content': raw_response},
                ],
                temperature=0.3,
                max_tokens=600,
            )
            refined = response.choices[0].message.content.strip()
            logger.info(f'RAG refine: "{raw_response[:40]}" → "{refined[:40]}"')
            return refined
        except Exception as e:
            logger.warning(f'RAGService.refine_response error: {e}')
            return raw_response

    def suggest(self, lead, message_text: str) -> str | None:
        cfg = self.agent_config

        if not cfg.is_ready():
            return None

        if self._plan_name() not in RAG_PLANS:
            return None

        embedding_svc = EmbeddingService(cfg)
        query_embedding = embedding_svc.embed(message_text)
        if not query_embedding:
            return None

        org_id = cfg.organization_id
        kb_results = self._search_knowledge_base(query_embedding, org_id)
        conv_results = self._search_conversations(query_embedding, org_id)
        history = self._get_history(lead)

        prompt_messages = self._build_messages(
            system_prompt=cfg.system_prompt or DEFAULT_SYSTEM_PROMPT,
            kb_results=kb_results,
            conv_results=conv_results,
            history=history,
            current_message=message_text,
        )

        return self._generate(prompt_messages)

    def _search_knowledge_base(self, embedding: list[float], org_id: int) -> list[dict]:
        if not settings.SUPABASE_URL:
            return []
        try:
            sb = _get_supabase()
            result = sb.rpc('match_knowledge_base', {
                'query_embedding': embedding,
                'p_match_threshold': self.agent_config.match_threshold,
                'p_match_count': self.agent_config.match_count,
                'p_organization_id': org_id,
            }).execute()
            return result.data or []
        except Exception as e:
            logger.warning(f'RAGService.search_knowledge_base error: {e}')
            return []

    def _search_conversations(self, embedding: list[float], org_id: int) -> list[dict]:
        if not settings.SUPABASE_URL:
            return []
        try:
            sb = _get_supabase()
            result = sb.rpc('match_conversations', {
                'query_embedding': embedding,
                'p_match_threshold': self.agent_config.match_threshold,
                'p_match_count': min(self.agent_config.match_count, 3),
                'p_organization_id': org_id,
            }).execute()
            return result.data or []
        except Exception as e:
            logger.warning(f'RAGService.search_conversations error: {e}')
            return []

    def _get_history(self, lead) -> list[dict]:
        from apps.conversations.models import Message
        try:
            msgs = (
                Message.objects
                .filter(conversation__lead=lead)
                .order_by('-created_at')[:self.agent_config.max_history_messages]
            )
            history = []
            for m in reversed(list(msgs)):
                role = 'user' if m.direction == 'IN' else 'assistant'
                history.append({'role': role, 'content': m.text})
            return history
        except Exception as e:
            logger.warning(f'RAGService._get_history error: {e}')
            return []

    def _build_messages(
        self,
        system_prompt: str,
        kb_results: list[dict],
        conv_results: list[dict],
        history: list[dict],
        current_message: str,
    ) -> list[dict]:
        context_parts = []

        if kb_results:
            context_parts.append("=== Base de conhecimento ===")
            for item in kb_results:
                context_parts.append(f"[{item.get('title', '')}]\n{item.get('content', '')}")

        if conv_results:
            context_parts.append("=== Exemplos de respostas anteriores (use como referência de tom e abordagem) ===")
            for item in conv_results:
                context_parts.append(
                    f"Cliente: {item.get('message_in', '')}\n"
                    f"Resposta: {item.get('message_out', '')}"
                )

        full_system = system_prompt
        if context_parts:
            full_system += "\n\n" + "\n\n".join(context_parts)

        full_system += (
            "\n\n---\n"
            "Com base no contexto acima, escreva UMA resposta para o cliente.\n"
            "Regras:\n"
            "- Tom informal e caloroso, como WhatsApp de um especialista amigo\n"
            "- Sem erros de português\n"
            "- Direto ao ponto, sem enrolação\n"
            "- Responda APENAS com o texto da mensagem, sem aspas nem prefixos"
        )

        messages = [{'role': 'system', 'content': full_system}]
        messages.extend(history)
        messages.append({'role': 'user', 'content': current_message})
        return messages

    def _generate(self, messages: list[dict]) -> str | None:
        try:
            response = self._get_openai().chat.completions.create(
                model=self.agent_config.model,
                messages=messages,
                temperature=self.agent_config.temperature,
                max_tokens=500,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f'RAGService._generate error: {e}')
            return None

    # ── Agente 2: Sugestão de 3 respostas com persona Border Collie Sul ──────

    def suggest_three_options(self, lead, message_text: str, conv=None, brief: str = '', agent_name: str = '') -> list[str]:
        """
        Gera 3 opções de resposta para o atendente usando a persona Border Collie Sul.
        Não requer rag_enabled — funciona apenas com openai_api_key.
        brief: contexto adicional digitado pelo atendente para guiar as sugestões.
        agent_name: nome do atendente humano (usado na saudação inicial).
        """
        if not self.agent_config.openai_api_key:
            return []

        try:
            org = self.agent_config.organization
            litters_ctx = _build_litters_context(org)
            greeting_instruction = _build_greeting_instruction(lead, conv, agent_name=agent_name)
            ai_profile = getattr(lead, 'ai_profile', None) or {}

            history = self._get_history(lead)

            kb_context = ''
            if self.agent_config.is_ready():
                embedding_svc = EmbeddingService(self.agent_config)
                query_embedding = embedding_svc.embed(message_text)
                if query_embedding:
                    kb_results = self._search_knowledge_base(query_embedding, org.id)
                    conv_results = self._search_conversations(query_embedding, org.id)
                    parts = []
                    if kb_results:
                        parts.append('=== Exemplos da base de conhecimento ===')
                        for item in kb_results:
                            parts.append(f"[{item.get('title', '')}]\n{item.get('content', '')}")
                    if conv_results:
                        parts.append('=== Respostas anteriores similares (use como referência de tom) ===')
                        for item in conv_results:
                            parts.append(
                                f"Cliente: {item.get('message_in', '')}\n"
                                f"Resposta: {item.get('message_out', '')}"
                            )
                    if parts:
                        kb_context = '\n\n'.join(parts)

            system_prompt = _build_conversation_system_prompt(
                litters_ctx=litters_ctx,
                greeting_instruction=greeting_instruction,
                ai_profile=ai_profile,
                kb_context=kb_context,
            )

            messages_list = [{'role': 'system', 'content': system_prompt}]
            messages_list.extend(history)

            # Monta a mensagem do usuário, incluindo o brief do atendente se houver
            user_content = message_text
            if brief:
                user_content = (
                    f'{message_text}\n\n'
                    f'[INSTRUÇÃO DO ATENDENTE — use isso para guiar as 3 opções de resposta]: {brief}'
                )
            messages_list.append({'role': 'user', 'content': user_content})

            response = self._get_openai().chat.completions.create(
                model='gpt-4o',
                messages=messages_list,
                temperature=0.7,
                max_tokens=800,
                response_format={'type': 'json_object'},
            )
            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)
            options = parsed.get('options', [])
            return [str(o).strip() for o in options if o][:3]
        except Exception as e:
            logger.exception(f'RAGService.suggest_three_options error: {e}')
            return []


# ── Helpers do Agente 2 ──────────────────────────────────────────────────────

def _build_litters_context(org) -> str:
    """Consulta ninhadas com filhotes disponíveis e calcula data estimada de entrega."""
    try:
        from apps.kennel.models import Litter
        today = date.today()
        litters = (
            Litter.objects
            .filter(organization=org, birth_date__isnull=False)
            .prefetch_related('puppies')
        )
        lines = []
        for litter in litters:
            available_dogs = litter.puppies.filter(status='available')
            if not available_dogs.exists():
                continue
            age_days = (today - litter.birth_date).days
            days_to_delivery = max(0, 60 - age_days)
            est_date = today + timedelta(days=days_to_delivery)

            dogs_desc = []
            for dog in available_dogs:
                normalized_price = _normalized_puppy_price(dog)
                price_str = _format_brl(normalized_price) if normalized_price else 'sob consulta'
                sex_label = 'macho' if dog.sex == 'M' else 'fêmea'
                color_part = f', {dog.color}' if dog.color else ''
                dogs_desc.append(f'  - {dog.name or "filhote"} ({sex_label}{color_part}) — {price_str}')

            if days_to_delivery == 0:
                delivery_info = f'já pode ser entregue (nasceu em {litter.birth_date.strftime("%d/%m/%Y")})'
            else:
                delivery_info = (
                    f'entrega estimada em ~{days_to_delivery} dias '
                    f'({est_date.strftime("%d/%m/%Y")})'
                )

            lines.append(
                f'Ninhada "{litter.name}" — {delivery_info}\n' + '\n'.join(dogs_desc)
            )

        if not lines:
            return 'Nenhuma ninhada com filhotes disponíveis no momento.'
        return '\n\n'.join(lines)
    except Exception as e:
        logger.warning(f'_build_litters_context error: {e}')
        return 'Informações de ninhadas indisponíveis no momento.'


def _build_greeting_instruction(lead, conv, agent_name: str = '') -> str:
    """
    Define como o modelo deve (ou não) saudar o cliente baseado no histórico
    e no tempo desde a última mensagem enviada pelo atendente/bot.
    agent_name: nome do atendente humano que será usado na saudação.
    """
    try:
        from apps.conversations.models import Message as ConvMessage
        first_name = ''
        if lead.full_name:
            clean = _clean_name(lead.full_name)
            parts = clean.split()
            candidate = parts[0].capitalize() if parts else ''
            # Só usa como nome se tiver pelo menos 2 letras reais
            if candidate and sum(1 for c in candidate if c.isalpha()) >= 2:
                first_name = candidate

        # Parte "aqui é o X" só aparece se o atendente tiver nome
        agent_intro = f', aqui é o {agent_name}' if agent_name else ''

        if conv is None:
            if first_name:
                return (
                    f'ATENÇÃO — REGRA OBRIGATÓRIA: Este é o PRIMEIRO contato humano. '
                    f'TODAS AS 3 OPÇÕES DEVEM OBRIGATORIAMENTE começar com a frase exata: '
                    f'"Oi {first_name}{agent_intro}, tudo bem?" '
                    f'Após essa saudação, quebre uma linha antes de continuar. '
                    f'Não omita a saudação em nenhuma das 3 opções.'
                )
            return (
                'ATENÇÃO — REGRA OBRIGATÓRIA: Este é o PRIMEIRO contato humano. '
                'TODAS AS 3 OPÇÕES DEVEM OBRIGATORIAMENTE começar com a frase exata: '
                f'"Oi{agent_intro}, tudo bem?" '
                'Após essa saudação, quebre uma linha antes de continuar. '
                'Não omita a saudação em nenhuma das 3 opções.'
            )

        messages = list(
            ConvMessage.objects
            .filter(conversation=conv)
            .order_by('created_at')
            .values('direction', 'created_at', 'provider_message_id')
        )

        out_msgs = [m for m in messages if m['direction'] == 'OUT']
        in_msgs  = [m for m in messages if m['direction'] == 'IN']

        # Mensagens humanas: OUT com provider_message_id preenchido
        human_out_msgs = [m for m in out_msgs if m.get('provider_message_id')]
        last_human_out = human_out_msgs[-1] if human_out_msgs else None
        last_out = out_msgs[-1] if out_msgs else None

        # PRIMEIRO CONTATO HUMANO: nenhuma mensagem de humano enviada ainda.
        # Pode ter bot/template respondido, mas nenhuma resposta personalizada do atendente.
        if not human_out_msgs:
            _rule = (
                'Este é o PRIMEIRO contato humano — o bot já pode ter respondido automaticamente, '
                'mas o atendente ainda não se apresentou.'
            )
            if first_name:
                return (
                    f'ATENÇÃO — REGRA OBRIGATÓRIA: {_rule} '
                    f'TODAS AS 3 OPÇÕES DEVEM OBRIGATORIAMENTE começar com a frase exata: '
                    f'"Oi {first_name}{agent_intro}, tudo bem?" '
                    f'Após essa saudação, quebre uma linha antes de continuar. '
                    f'Não omita a saudação em nenhuma das 3 opções.'
                )
            return (
                f'ATENÇÃO — REGRA OBRIGATÓRIA: {_rule} '
                'TODAS AS 3 OPÇÕES DEVEM OBRIGATORIAMENTE começar com a frase exata: '
                f'"Oi{agent_intro}, tudo bem?" '
                'Após essa saudação, quebre uma linha antes de continuar. '
                'Não omita a saudação em nenhuma das 3 opções.'
            )

        # A partir daqui, já há pelo menos 1 resposta humana
        ref_out = last_human_out or last_out
        elapsed = timezone.now() - ref_out['created_at']
        hours_elapsed = elapsed.total_seconds() / 3600

        if hours_elapsed > 1:
            hours_label = f'{int(hours_elapsed)}h'
            if first_name:
                return (
                    f'Retomada após {hours_label} de silêncio. '
                    f'Pode saudar com o nome do cliente ("{first_name}") de forma natural e curta. '
                    f'Apenas uma vez, no início da resposta.'
                )
            return f'Retomada após {hours_label} de silêncio. Uma saudação curta é adequada.'

        return (
            'Conversa ativa (menos de 1 hora desde a última resposta). '
            'NÃO repita saudação nem use o nome do cliente. Continue o assunto naturalmente.'
        )
    except Exception as e:
        logger.warning(f'_build_greeting_instruction error: {e}')
        return 'Continue a conversa de forma natural.'


CONVERSATION_SYSTEM_PROMPT_TEMPLATE = """\
Você é um atendente humano do Border Collie Sul, canil especializado em Border Collie.

Seu objetivo NÃO é vender. É criar conexão e entender a intenção do cliente.

FORMA DE COMUNICAÇÃO:
- Escreva como uma pessoa real digitando no WhatsApp
- Linguagem simples, direta, sem formalidade
- Frases quebradas, naturais — nunca parecer texto pronto
- Nunca soe como script ou atendimento automático

TOM: humano, direto, tranquilo. Sem intimidade forçada. Sem "super fofo" ou sentimentalismo artificial.

PRINCÍPIO CENTRAL — ESPELHAMENTO EMOCIONAL:
Calibre o tom da resposta proporcionalmente ao tom da mensagem do lead.
- Mensagem fria, objetiva, curta → resposta fria, objetiva, curta
- Mensagem com leve calor, curiosidade → resposta com leve calor, aberta
- Mensagem claramente emocional (perda, presente, história pessoal, entusiasmo genuíno) → resposta com emoção proporcional, acolhedora, humana
- Mensagem muito emocional e aberta → você pode ser mais próximo, mais pessoal, mais presente
A regra é: nunca vá além do que o lead trouxe. Mas também nunca seja frio quando ele foi quente.
Intimidade cresce na medida em que o lead abre espaço — não antes.

ESTRATÉGIA: entender o que a pessoa quer → responder com clareza → só então detalhar filhotes
PROIBIDO: escassez falsa, pressão, linguagem genérica de vendedor, "super", "adorável", "fofo", "incrível", "perfeito", "maravilhoso"
FRASES PREFERIDAS: "me conta uma coisa…", "deixa eu te perguntar…", "aqui a gente costuma…"
EMOJI: pode usar no máximo 1 emoji simples quando ficar natural (ex.: 👍 ou 👀). Nunca exagerar.

CONSIDERAÇÕES DE RESPOSTA (fluxo prático):
1) PRIMEIRA RESPOSTA (quebra de gelo):
- "Fala! Tudo bem?"
- "Vi aqui que você chamou por causa dos filhotes"
- "Qual deles te chamou mais atenção?"
- Se a conversa estiver no início, puxar para o site e ninhada completa.

2) SE A PESSOA PERGUNTA "quanto custa?" direto:
- Não travar.
- Responder e qualificar com pergunta curta:
  "Claro, te passo sim. Mas antes me conta… é mais pra companhia/família ou trabalho/treino específico?"
- Reforçar posicionamento de temperamento e convivência familiar.

3) DEPOIS DA RESPOSTA (perfil do cliente):
- Entrar com valor + posicionamento:
  "Eles estão saindo na faixa de R$ 4.000."
- Complementar com contexto de perfil/comportamento (mais ativos x mais tranquilos).

4) SE DEMONSTRA INTERESSE:
- Aproximar com CTA leve:
  "Se quiser, te mando mais vídeos dele(a) aqui."

5) ENVIO DE VÍDEO + CONEXÃO:
- Após enviar, puxar percepção:
  "Dá pra ter uma ideia boa do jeito dele(a), né?"

6) FECHAMENTO LEVE:
- Sem pressão:
  "Hoje ainda tenho disponibilidade sim. Se fizer sentido pra você, dá pra garantir com reserva."

7) SE DEMORA / ESFRIA:
- Follow-up leve:
  "E aí, chegou a ver os vídeos?"

ATALHOS IMPORTANTES:
- Transporte: envio para todo Brasil por transportadora especializada.
- Garantia/procedência: pedigree, pais selecionados, acompanhamento.
- Reserva: 30% para reservar e restante antes da entrega.

DICA DE OURO:
- Nunca responder seco só com preço.
- Sempre usar: conversa → contexto → valor.

---

BASE DE CONHECIMENTO DO CANIL:

LOCALIZAÇÃO: Santa Catarina — atendimento e entrega para todo o Brasil

SITE OFICIAL (USE COM PRIORIDADE quando a conversa está no início ou o lead não viu os filhotes ainda):
- Site oficial (lá estão todos os filhotes disponíveis com fotos e detalhes): https://bordercolliesul.com.br
- Quando a conversa ainda está fria ou o lead acabou de entrar em contato, OBRIGATÓRIO incluir o link em pelo menos uma das opções de resposta
- SEMPRE diga que lá estão todos os filhotes disponíveis — exemplo: "no site tem todos os filhotes disponíveis agora"
- O link DEVE estar em parágrafo separado, com linha em branco antes:
  "[texto da mensagem]

  no site tem todos os filhotes disponíveis agora

  https://bordercolliesul.com.br"
- NUNCA coloque o link na mesma linha ou no mesmo parágrafo do restante da mensagem
- NÃO mencione Instagram

SOBRE OS FILHOTES:
- Raça: Border Collie
- Criação com foco em temperamento equilibrado, inteligência, vínculo e socialização
- Todos vacinados conforme a idade, vermifugados, acompanhamento profissional

PREÇOS (use somente se o cliente perguntar, de forma simples e direta):
- Todos os filhotes: R$ 4.000 (preço único, sem variação por sexo/cor).
- Mesmo quando falar preço, evite resposta seca; contextualize e faça 1 pergunta curta.

ENTREGA — REGRAS:
- Filhotes liberados com ~60 dias de vida
- Nunca crave data exata — use linguagem aproximada:
  "eles ainda estão bem novinhos… normalmente com uns 60 dias já podem ir"
  "faltam mais ou menos X dias ainda"
  "provavelmente nas próximas semanas já começa a liberar"

PEDIGREE E GENÉTICA:
- Todos têm pedigree CBKC (entidade oficial no Brasil, ligada à FCI)
- Se fizer sentido: "posso te mostrar o pedigree dos pais e até o mapeamento genético"

TRANSPORTE:
- Principal: van especializada própria para transporte de cães — segura e tranquila
- "a maioria dos envios a gente faz por van especializada, própria para transporte de cães"

RESERVA E PAGAMENTO:
- Reserva: 30% do valor — restante antes da entrega
- Parcelamento: só mencionar se o cliente demonstrar interesse + dificuldade

REGRAS: Nunca despeje tudo de uma vez. Adapte à pergunta. Nunca parecer "texto pronto".

---

FILHOTES E NINHADAS DISPONÍVEIS AGORA:
{litters_context}

---

INSTRUÇÃO DE SAUDAÇÃO:
{greeting_instruction}

---

{profile_section}{kb_section}\
Gere EXATAMENTE 3 opções diferentes para responder à última mensagem do cliente.
Cada opção com um ângulo distinto:
1. Direta e clara — responde o que foi perguntado sem rodeios
2. Abre espaço — responde e faz uma pergunta simples para entender melhor o que o cliente quer; se a conversa está no início ou o lead ainda não conhece os filhotes, inclua o site nesta opção com a frase "no site tem todos os filhotes disponíveis agora" seguida do link em parágrafo separado
3. Mais curta e simples — uma resposta enxuta, natural, como alguém digitando rápido no WhatsApp

EMOÇÃO — ESPELHAMENTO PROPORCIONAL:
- Leia o tom da última mensagem do lead antes de escolher o ângulo de cada opção
- Se a mensagem foi neutra → as 3 opções devem ser diretas e sem carga emocional
- Se a mensagem teve algum calor ou curiosidade → uma das opções pode ser mais próxima
- Se a mensagem foi claramente emocional → pelo menos uma opção deve espelhar esse calor com naturalidade
- Nunca force emoção onde não havia. Nunca suprima emoção onde ela existia.

REGRA DO SITE:
- Se a conversa tem poucas mensagens ou o lead ainda não demonstrou ver os filhotes → OBRIGATÓRIO incluir o link em pelo menos uma das 3 opções
- Sempre diga que lá estão todos os filhotes disponíveis: "no site tem todos os filhotes disponíveis agora"
- Se o lead já está engajado → inclua somente se for natural no contexto
- O link deve estar em parágrafo separado com linha em branco antes:
  https://bordercolliesul.com.br
- NÃO mencione Instagram

Antes de cada opção, pergunte mentalmente:
- "Isso parece algo que uma pessoa escreveria agora?"
- "Estou forçando emoção onde ela não foi convidada?"
- "Estou tentando vender ou estou conversando?"
Se parecer artificial ou íntimo demais, simplifique e distancie um pouco.

Responda APENAS com JSON válido:
{{"options": ["opção1", "opção2", "opção3"]}}"""

_MATURIDADE_TONE = {
    'muito_quente': 'facilite o próximo passo de forma natural e direta. Não pressione.',
    'quente': 'responda com clareza e detalhes práticos. Abra espaço para avanço sem forçar.',
    'morno': 'responda as dúvidas com calma. Sem pressão, sem intimidade excessiva.',
    'frio': 'responda o que foi perguntado de forma simples. Não tente fechar nada.',
}

_INTERESSE_TONE = {
    'emocional': 'O lead demonstrou interesse emocional ao longo da conversa — espelhe esse tom proporcionalmente. Se ele foi muito aberto, você pode ser mais próximo. Se foi só levemente emocional, seja levemente mais caloroso. Nunca finja mais emoção do que ele mostrou.',
    'racional': 'O lead é objetivo — vá direto ao ponto, sem floreios, sem tentar criar calor que ele não pediu.',
    'misto': 'O lead mistura objetivo e emocional — responda o prático, e se ele tocou em algo pessoal, reconheça com uma frase simples antes de seguir.',
}


def _build_conversation_system_prompt(
    litters_ctx: str,
    greeting_instruction: str,
    ai_profile: dict,
    kb_context: str,
) -> str:
    profile_section = ''
    if ai_profile:
        nivel = ai_profile.get('nivel_maturidade', '')
        tipo = ai_profile.get('tipo_interesse', '')
        sinais = ai_profile.get('sinais_emocionais', [])
        urgencia = ai_profile.get('urgencia', '')
        perfil = ai_profile.get('perfil_cliente', '')
        resumo = ai_profile.get('resumo_intencao', '')

        tone_maturidade = _MATURIDADE_TONE.get(nivel, '')
        tone_interesse = _INTERESSE_TONE.get(tipo, '')

        lines = ['PERFIL DO LEAD (use para adaptar tom e abordagem):']
        if nivel:
            lines.append(f'- Maturidade: {nivel}')
            if tone_maturidade:
                lines.append(f'  → Tom: {tone_maturidade}')
        if tipo:
            lines.append(f'- Tipo de interesse: {tipo}')
            if tone_interesse:
                lines.append(f'  → {tone_interesse}')
        if sinais:
            lines.append(f'- Sinais emocionais detectados: {", ".join(sinais)}')
        if urgencia:
            lines.append(f'- Urgência: {urgencia}')
        if perfil:
            lines.append(f'- Perfil: {perfil}')
        if resumo:
            lines.append(f'- Resumo: {resumo}')
        profile_section = '\n'.join(lines) + '\n\n---\n\n'

    kb_section = ''
    if kb_context:
        kb_section = kb_context + '\n\n---\n\n'

    return CONVERSATION_SYSTEM_PROMPT_TEMPLATE.format(
        litters_context=litters_ctx,
        greeting_instruction=greeting_instruction,
        profile_section=profile_section,
        kb_section=kb_section,
    )
