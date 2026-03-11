import logging
from .states import (
    STATE_INITIAL, STATE_Q1_BUDGET, STATE_Q2_TIMELINE, STATE_Q3_HOUSING,
    STATE_COMPLETE, MESSAGES, NEXT_STATE,
)

logger = logging.getLogger(__name__)


class QualifierEngine:
    def __init__(self, lead):
        self.lead = lead

    def process_message(self, text: str) -> list[str]:
        state = self.lead.conversation_state or STATE_INITIAL

        if not self.lead.is_ai_active:
            return []

        # First message — send greeting with Q1 embedded
        if state == STATE_INITIAL:
            self.lead.conversation_state = STATE_Q1_BUDGET
            self.lead.status = 'QUALIFYING'
            self.lead.save(update_fields=['conversation_state', 'status'])
            return [MESSAGES[STATE_INITIAL]]

        self._parse_and_update_lead(state, text)

        next_state = NEXT_STATE.get(state, STATE_COMPLETE)
        self.lead.conversation_state = next_state

        if next_state == STATE_COMPLETE:
            self._finalize()
            self.lead.save()
            return [MESSAGES[STATE_COMPLETE]]

        self.lead.save()
        return [MESSAGES[next_state]]

    def _parse_and_update_lead(self, state: str, text: str):
        lower = text.lower().strip()

        if state == STATE_Q1_BUDGET:
            if any(c in lower for c in ['1', 'sim', 'consigo', 'dentro', 'ok', 'pode']):
                self.lead.budget_ok = 'YES'
            elif any(c in lower for c in ['3', 'não', 'nao', 'planej', 'ainda não']):
                self.lead.budget_ok = 'NO'
            else:
                self.lead.budget_ok = 'MAYBE'

        elif state == STATE_Q2_TIMELINE:
            if '1' in lower or 'agora' in lower or 'urgente' in lower or 'rápido' in lower:
                self.lead.timeline = 'NOW'
            elif '2' in lower or '30' in lower or 'trinta' in lower:
                self.lead.timeline = 'THIRTY_DAYS'
            elif '3' in lower or '2' in lower or 'mês' in lower or 'mes' in lower:
                self.lead.timeline = 'SIXTY_PLUS'
            else:
                self.lead.timeline = 'RESEARCHING'

        elif state == STATE_Q3_HOUSING:
            if any(w in lower for w in ['casa', 'house', 'sítio', 'sitio', 'chácara', 'chacara', 'rural']):
                self.lead.housing_type = 'HOUSE'
            elif any(w in lower for w in ['apart', 'apto', 'flat', 'studio', 'condomínio', 'condominio']):
                self.lead.housing_type = 'APT'

    def _finalize(self):
        self.lead.score = self._calculate_score()
        self.lead.tier = self._determine_tier(self.lead.score)
        self.lead.status = 'QUALIFIED'
        self._generate_auto_tags()

    def _calculate_score(self) -> int:
        score = 0
        lead = self.lead

        # Orçamento (40 pts — critério mais importante)
        bud_pts = {'YES': 40, 'MAYBE': 20, 'NO': 0}
        score += bud_pts.get(lead.budget_ok or '', 0)

        # Prazo (35 pts)
        tl_pts = {'NOW': 35, 'THIRTY_DAYS': 25, 'SIXTY_PLUS': 10, 'RESEARCHING': 0}
        score += tl_pts.get(lead.timeline or '', 0)

        # Moradia (25 pts)
        if lead.housing_type == 'HOUSE':
            score += 25
        elif lead.housing_type == 'APT':
            score += 8

        return max(0, min(100, score))

    def _determine_tier(self, score: int) -> str:
        if score >= 65:
            return 'A'
        elif score >= 35:
            return 'B'
        return 'C'

    def _generate_auto_tags(self):
        from apps.leads.models import LeadTag
        lead = self.lead
        tag_names = []

        tier_map = {'A': 'tier-a', 'B': 'tier-b', 'C': 'tier-c'}
        if lead.tier in tier_map:
            tag_names.append(tier_map[lead.tier])

        if lead.housing_type == 'HOUSE':
            tag_names.append('casa')
        elif lead.housing_type == 'APT':
            tag_names.append('apartamento')

        if lead.timeline == 'NOW':
            tag_names.append('urgente')

        if lead.budget_ok == 'YES':
            tag_names.append('orcamento-ok')

        for name in tag_names:
            tag, _ = LeadTag.objects.get_or_create(
                organization=lead.organization,
                name=name,
            )
            lead.tags.add(tag)
