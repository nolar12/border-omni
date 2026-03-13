import json
import logging
import threading
from django.conf import settings

from .embedding_service import EmbeddingService

logger = logging.getLogger('apps')


def store_conversation_pair(agent_config, message_in: str, message_out: str, lead=None):
    """
    Salva um par IN/OUT como embedding no Supabase em background.
    Passa a resposta pela camada de refinamento antes de armazenar.
    """
    if not agent_config or not agent_config.is_ready():
        return
    if not settings.SUPABASE_URL:
        return

    def _store():
        try:
            from supabase import create_client
            from .rag_service import RAGService

            # Refina a resposta antes de armazenar (correção gramatical + tom)
            rag = RAGService(agent_config)
            refined_out = rag.refine_response(message_out)

            embedding_svc = EmbeddingService(agent_config)
            embedding = embedding_svc.embed(message_in)
            if not embedding:
                return

            org_id = agent_config.organization_id
            payload = {
                'organization_id': org_id,
                'message_in': message_in,
                'message_out': refined_out,
                'embedding': embedding,
            }
            if lead:
                payload['lead_score'] = lead.score
                payload['lead_tier'] = lead.tier or ''
                payload['lead_classification'] = getattr(lead, 'lead_classification', '') or ''

            sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
            sb.table('conversation_embeddings').insert(payload).execute()
            logger.info(f'RAG: stored refined pair for org {org_id}')
        except Exception as e:
            logger.warning(f'store_conversation_pair error: {e}')

    threading.Thread(target=_store, daemon=True).start()


def add_knowledge_base_entry(agent_config, title: str, content: str) -> dict | None:
    """Adiciona uma entrada na knowledge_base com embedding gerado."""
    if not settings.SUPABASE_URL:
        raise ValueError('SUPABASE_URL not configured')
    if not agent_config.openai_api_key:
        raise ValueError('OpenAI API key not configured for this organization')

    embedding_svc = EmbeddingService(agent_config)
    embedding = embedding_svc.embed(f"{title}\n{content}")
    if not embedding:
        raise ValueError('Failed to generate embedding')

    from supabase import create_client
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    result = sb.table('knowledge_base').insert({
        'organization_id': agent_config.organization_id,
        'title': title,
        'content': content,
        'embedding': embedding,
    }).execute()
    return result.data[0] if result.data else None


def list_knowledge_base(organization_id: int) -> list[dict]:
    if not settings.SUPABASE_URL:
        return []
    from supabase import create_client
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    result = (
        sb.table('knowledge_base')
        .select('id, title, content, created_at')
        .eq('organization_id', organization_id)
        .order('created_at', desc=True)
        .execute()
    )
    return result.data or []


def delete_knowledge_base_entry(organization_id: int, entry_id: str) -> bool:
    if not settings.SUPABASE_URL:
        return False
    from supabase import create_client
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    sb.table('knowledge_base').delete().eq('id', entry_id).eq('organization_id', organization_id).execute()
    return True


def export_training_jsonl(organization_id: int) -> str:
    """
    Exporta pares de conversa no formato JSONL compatível com fine-tuning da OpenAI.
    Formato: {"messages": [{"role": "user", ...}, {"role": "assistant", ...}]}
    """
    if not settings.SUPABASE_URL:
        return ''
    from supabase import create_client
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    result = (
        sb.table('conversation_embeddings')
        .select('message_in, message_out')
        .eq('organization_id', organization_id)
        .order('created_at')
        .execute()
    )
    rows = result.data or []
    lines = []
    for row in rows:
        record = {
            'messages': [
                {'role': 'user', 'content': row['message_in']},
                {'role': 'assistant', 'content': row['message_out']},
            ]
        }
        lines.append(json.dumps(record, ensure_ascii=False))
    return '\n'.join(lines)
