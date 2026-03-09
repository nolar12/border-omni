import logging
from .states import (
    STATE_INITIAL, STATE_Q1_LOCATION, STATE_Q2_HOUSING, STATE_Q3_TIME,
    STATE_Q4_EXPERIENCE, STATE_Q5_BUDGET, STATE_Q6_TIMELINE, STATE_Q7_PURPOSE,
    STATE_COMPLETE, MESSAGES, NEXT_STATE,
)
from .parsers import (
    extract_uf, extract_city, parse_time_minutes, infer_housing_type,
    infer_experience, infer_budget, infer_timeline, infer_purpose,
)

logger = logging.getLogger(__name__)


class QualifierEngine:
    def __init__(self, lead):
        self.lead = lead

    def process_message(self, text: str) -> list[str]:
        state = self.lead.conversation_state or STATE_INITIAL
        replies = []

        if not self.lead.is_ai_active:
            return []

        # First message — send greeting and first question
        if state == STATE_INITIAL:
            self.lead.conversation_state = STATE_Q1_LOCATION
            self.lead.status = 'QUALIFYING'
            self.lead.save(update_fields=['conversation_state', 'status'])
            return [MESSAGES[STATE_INITIAL]]

        # Parse the current answer
        self._parse_and_update_lead(state, text)

        # Advance state
        next_state = NEXT_STATE.get(state, STATE_COMPLETE)
        self.lead.conversation_state = next_state

        if next_state == STATE_COMPLETE:
            self._finalize()
            replies.append(MESSAGES[STATE_COMPLETE])
        else:
            replies.append(MESSAGES[next_state])

        self.lead.save()
        return replies

    def _parse_and_update_lead(self, state: str, text: str):
        if state == STATE_Q1_LOCATION:
            city = extract_city(text)
            uf = extract_uf(text)
            if city:
                self.lead.city = city
            if uf:
                self.lead.state = uf

        elif state == STATE_Q2_HOUSING:
            ht = infer_housing_type(text)
            if ht:
                self.lead.housing_type = ht

        elif state == STATE_Q3_TIME:
            mins = parse_time_minutes(text)
            if mins is not None:
                self.lead.daily_time_minutes = mins

        elif state == STATE_Q4_EXPERIENCE:
            exp = infer_experience(text)
            if exp:
                self.lead.experience_level = exp
            # detect kids/pets from passing mentions
            lower = text.lower()
            if any(w in lower for w in ['filho', 'criança', 'kid', 'child', 'bebê']):
                self.lead.has_kids = True
            if any(w in lower for w in ['gato', 'cat', 'outro cachorro', 'outro cão']):
                self.lead.has_other_pets = True

        elif state == STATE_Q5_BUDGET:
            bud = infer_budget(text)
            if bud:
                self.lead.budget_ok = bud

        elif state == STATE_Q6_TIMELINE:
            tl = infer_timeline(text)
            if tl:
                self.lead.timeline = tl

        elif state == STATE_Q7_PURPOSE:
            pur = infer_purpose(text)
            if pur:
                self.lead.purpose = pur

    def _finalize(self):
        self.lead.score = self._calculate_score()
        self.lead.tier = self._determine_tier(self.lead.score)
        self.lead.status = 'QUALIFIED'
        self._generate_auto_tags()

    def _calculate_score(self) -> int:
        score = 0
        lead = self.lead

        # Housing (20 pts)
        if lead.housing_type == 'HOUSE':
            score += 20
        elif lead.housing_type == 'APT':
            score += 5

        # Time per day (25 pts)
        mins = lead.daily_time_minutes or 0
        if mins >= 240:
            score += 25
        elif mins >= 120:
            score += 15
        elif mins >= 60:
            score += 8

        # Experience (20 pts)
        exp_pts = {'HAD_HIGH_ENERGY': 20, 'HAD_DOGS': 12, 'FIRST_DOG': 5}
        score += exp_pts.get(lead.experience_level or '', 0)

        # Budget (20 pts)
        bud_pts = {'YES': 20, 'MAYBE': 10, 'NO': 0}
        score += bud_pts.get(lead.budget_ok or '', 0)

        # Timeline (15 pts)
        tl_pts = {'NOW': 15, 'THIRTY_DAYS': 10, 'SIXTY_PLUS': 3}
        score += tl_pts.get(lead.timeline or '', 0)

        # Penalty for kids (Border Collie + small kids = harder)
        if lead.has_kids:
            score -= 5

        return max(0, min(100, score))

    def _determine_tier(self, score: int) -> str:
        if score >= 70:
            return 'A'
        elif score >= 40:
            return 'B'
        return 'C'

    def _generate_auto_tags(self):
        from apps.leads.models import LeadTag
        lead = self.lead
        tag_names = []

        if lead.tier == 'A':
            tag_names.append('tier-a')
        elif lead.tier == 'B':
            tag_names.append('tier-b')
        elif lead.tier == 'C':
            tag_names.append('tier-c')

        if lead.housing_type == 'HOUSE':
            tag_names.append('casa')
        elif lead.housing_type == 'APT':
            tag_names.append('apartamento')

        if lead.timeline == 'NOW':
            tag_names.append('urgente')

        if lead.experience_level == 'HAD_HIGH_ENERGY':
            tag_names.append('experiente')

        for name in tag_names:
            tag, _ = LeadTag.objects.get_or_create(
                organization=lead.organization,
                name=name,
            )
            lead.tags.add(tag)
