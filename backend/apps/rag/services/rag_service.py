import logging
from django.conf import settings
from openai import OpenAI

from .embedding_service import EmbeddingService

logger = logging.getLogger('apps')

RAG_PLANS = {'pro', 'enterprise'}

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
4. EMOJIS: mantenha emojis que já existam; adicione 1 no máximo se a mensagem ficar muito seca
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
