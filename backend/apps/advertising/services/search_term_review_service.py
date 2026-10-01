import logging
import re

from apps.advertising.models import AdAgentDecision
from apps.advertising.services.campaign_service import CampaignService

logger = logging.getLogger('apps')

# Qualquer pedaço que lembre a raça (inclui grafias erradas) — na dúvida NÃO nega.
_BREED_RE = re.compile(r'bord|boder|brder|coll|colie|coli\b|cole\b|coly', re.IGNORECASE)

MIN_IMPRESSIONS_WITHOUT_CLICK = 10
MAX_NEGATIVES_PER_RUN = 30


def find_irrelevant_terms(terms: list[dict], already_negated: set[str] | None = None) -> list[dict]:
    """Termos que casaram por Broad SEM citar a raça e já custaram clique ou volume —
    ruído puro ("cachorro", "filhotes mais lindos do mundo"). Termos com a raça no texto
    nunca entram aqui, mesmo que sejam ruins: esses exigem decisão humana."""
    already_negated = {t.lower() for t in (already_negated or set())}
    found: dict[str, dict] = {}
    for term in terms:
        text = (term.get('search_term') or '').strip().lower()
        if not text or text in already_negated or term.get('match_type') != 'BROAD':
            continue
        if _BREED_RE.search(text):
            continue
        entry = found.setdefault(text, {'search_term': text, 'clicks': 0, 'impressions': 0, 'cost': 0.0})
        entry['clicks'] += term.get('clicks', 0)
        entry['impressions'] += term.get('impressions', 0)
        entry['cost'] += term.get('cost', 0.0)
    return sorted(
        (e for e in found.values() if e['clicks'] >= 1 or e['impressions'] >= MIN_IMPRESSIONS_WITHOUT_CLICK),
        key=lambda e: -e['cost'],
    )


class SearchTermReviewService:
    def run(self, campaign, days_back: int = 3) -> list[dict]:
        service = CampaignService()
        already = set()
        for decision in AdAgentDecision.objects.filter(campaign=campaign, action='add_negative_keywords'):
            already.update(decision.after.get('negative_keywords_added', []))

        candidates = find_irrelevant_terms(service.get_search_terms(campaign, days_back), already)[:MAX_NEGATIVES_PER_RUN]
        if not candidates:
            return []

        wasted = sum(c['cost'] for c in candidates)
        service.add_negative_keywords(
            campaign.organization, campaign.id, [c['search_term'] for c in candidates], match_type='EXACT',
            reason=(
                f'Revisão diária de termos de busca: {len(candidates)} termo(s) casados por Broad sem citar a raça '
                f'(R$ {wasted:.2f} gastos) — ex.: {", ".join(c["search_term"] for c in candidates[:3])}.'
            ),
            hypothesis='Bloquear a busca exata sem a raça corta cliques de curiosidade sem afetar buscas de compra.',
            performed_by='agent',
        )
        return candidates
