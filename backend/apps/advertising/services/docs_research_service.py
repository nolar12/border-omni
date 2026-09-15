"""
Pesquisa restrita de documentação OFICIAL do Google — nunca uma busca livre na
web. Usada pelo agente só quando a pergunta envolve algo volátil que a skill
(conhecimento permanente/metodológico) não cobre ou pode estar desatualizada:
mudanças na API do Google Ads/Data Manager, políticas, tipos de campanha,
ValueTrack, conversões, bidding, ou recursos novos/descontinuados.

Implementado com um allowlist estrito de domínio + um parser HTML mínimo da
stdlib (html.parser) — sem cliente de busca de terceiros nem dependência nova,
seguindo a mesma convenção de "sem dependências pesadas" já usada no resto da
app (ver providers/google_ads.py).
"""
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

logger = logging.getLogger('apps')

ALLOWED_DOC_HOSTS = {'developers.google.com', 'support.google.com'}
MAX_CONTENT_CHARS = 6000
REQUEST_TIMEOUT = 15


class _TextExtractor(HTMLParser):
    """Extrai só o texto visível de uma página, descartando script/style/nav/footer."""

    _SKIPPED_TAGS = {'script', 'style', 'nav', 'header', 'footer'}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIPPED_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            text = data.strip()
            if text:
                self.chunks.append(text)


def fetch_official_documentation(url: str) -> dict:
    """
    Busca e retorna o texto de UMA página de documentação oficial do Google
    (developers.google.com ou support.google.com). Qualquer outro domínio é
    recusado — a skill permanece a fonte de verdade padrão; isto é só para
    confirmar/atualizar um detalhe pontual e volátil.
    """
    host = (urlparse(url).hostname or '').lower()
    if host not in ALLOWED_DOC_HOSTS:
        return {
            'error': (
                f'Domínio não permitido: "{host}". Só é possível consultar '
                f'{" ou ".join(sorted(ALLOWED_DOC_HOSTS))} (documentação oficial do Google).'
            ),
        }

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={'User-Agent': 'BorderOmniAdsAgent/1.0'})
    except requests.RequestException as exc:
        logger.warning(f'docs_research_service: falha ao buscar {url}: {exc}')
        return {'error': 'Não foi possível acessar a documentação agora. Tente novamente ou responda com o conhecimento da skill.'}

    if resp.status_code != 200:
        return {'error': f'A página retornou status {resp.status_code} — pode não existir mais nessa URL.'}

    parser = _TextExtractor()
    try:
        parser.feed(resp.text)
    except Exception:
        logger.exception('docs_research_service: falha ao interpretar HTML')
        return {'error': 'Não foi possível interpretar o conteúdo da página.'}

    text = re.sub(r'\s+', ' ', ' '.join(parser.chunks)).strip()
    if not text:
        return {'error': 'A página não retornou conteúdo textual legível.'}

    return {'url': url, 'content': text[:MAX_CONTENT_CHARS]}
