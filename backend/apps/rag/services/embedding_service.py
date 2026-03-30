import logging
from openai import OpenAI

logger = logging.getLogger('apps')


class EmbeddingService:
    EMBEDDING_MODEL = 'text-embedding-ada-002'

    def __init__(self, agent_config):
        self.agent_config = agent_config
        self._client = None

    def _get_client(self):
        if not self._client:
            self._client = OpenAI(api_key=self.agent_config.openai_api_key)
        return self._client

    def embed(self, text: str) -> list[float] | None:
        if not text or not text.strip():
            return None
        try:
            response = self._get_client().embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=text.strip(),
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f'EmbeddingService.embed error: {e}')
            return None
