import logging
import random
from django.conf import settings
from .states import (
    STATE_INITIAL, STATE_Q1_TIMELINE, STATE_Q2_HOUSING,
    STATE_Q3_BUDGET, STATE_Q4_PURPOSE, STATE_COMPLETE,
    MESSAGES, NEXT_STATE, MSG_MEDIA_CAPTION_VIDEO, MSG_MEDIA_CAPTION_IMAGE,
)
from .parsers import infer_timeline, infer_budget, infer_purpose

logger = logging.getLogger(__name__)


class QualifierEngine:
    def __init__(self, lead):
        self.lead = lead

    def process_message(self, text: str) -> list[str]:
        state = self.lead.conversation_state or STATE_INITIAL

        if not self.lead.is_ai_active:
            return []

        # Primeira mensagem: sorteia variante A/B, envia mídia + intro + Q1
        if state == STATE_INITIAL:
            variants = getattr(settings, 'AB_MEDIA_VARIANTS', {})
            if variants:
                variant_key = random.choice(list(variants.keys()))
                self.lead.ab_variant = variant_key
            self.lead.conversation_state = STATE_Q1_TIMELINE
            self.lead.status = 'QUALIFYING'
            self.lead.save(update_fields=['conversation_state', 'status', 'ab_variant'])

            replies: list = []
            if variants and self.lead.ab_variant:
                variant = variants[self.lead.ab_variant]
                if variant.get('url'):
                    default_caption = (
                        MSG_MEDIA_CAPTION_VIDEO if variant['type'] == 'video'
                        else MSG_MEDIA_CAPTION_IMAGE
                    )
                    replies.append({
                        'type': variant['type'],
                        'url': variant['url'],
                        'caption': variant.get('caption', default_caption),
                    })
            else:
                # fallback para configuração legada (sempre vídeo)
                media_url = getattr(settings, 'QUALIFICATION_MEDIA_URL', '')
                media_type = getattr(settings, 'QUALIFICATION_MEDIA_TYPE', 'video')
                if media_url:
                    replies.append({'type': media_type, 'url': media_url, 'caption': MSG_MEDIA_CAPTION_VIDEO})
            replies.append(MESSAGES[STATE_INITIAL])
            replies.append(MESSAGES[STATE_Q1_TIMELINE])
            return replies

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

        if state == STATE_Q1_TIMELINE:
            timeline = infer_timeline(lower)
            if timeline:
                self.lead.timeline = timeline
            elif '4' in lower or 'pesquisando' in lower:
                self.lead.timeline = 'RESEARCHING'
            elif '3' in lower or 'mês' in lower or 'mes' in lower:
                self.lead.timeline = 'SIXTY_PLUS'
            else:
                self.lead.timeline = 'RESEARCHING'

        elif state == STATE_Q2_HOUSING:
            if '3' in lower or any(w in lower for w in ['apart', 'apto', 'flat', 'studio', 'condomínio', 'condominio']):
                self.lead.housing_type = 'APT'
            elif '2' in lower or any(w in lower for w in ['sem pátio', 'sem patio', 'sem quintal']):
                self.lead.housing_type = 'HOUSE_N'
            elif '1' in lower or any(w in lower for w in ['pátio', 'patio', 'quintal', 'casa', 'sítio', 'sitio', 'chácara', 'chacara', 'rural']):
                self.lead.housing_type = 'HOUSE_Y'

        elif state == STATE_Q3_BUDGET:
            budget = infer_budget(lower)
            if budget:
                self.lead.budget_ok = budget
            elif '3' in lower or 'pesquisando' in lower:
                self.lead.budget_ok = 'NO'
            else:
                self.lead.budget_ok = 'MAYBE'

        elif state == STATE_Q4_PURPOSE:
            if '4' in lower or 'pesquisando' in lower:
                self.lead.purpose = None
            else:
                purpose = infer_purpose(lower)
                self.lead.purpose = purpose if purpose else None

    def _finalize(self):
        self.lead.score = self._calculate_score()
        self.lead.tier = self._determine_tier(self.lead.score)
        classification_score = self._calculate_classification_score()
        self.lead.lead_classification = self._determine_classification(classification_score)
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

    def _calculate_classification_score(self) -> int:
        lead = self.lead
        tl  = {'NOW': 3, 'THIRTY_DAYS': 2, 'SIXTY_PLUS': 1, 'RESEARCHING': 0}
        bud = {'YES': 3, 'MAYBE': 1, 'NO': 0}
        hs  = {'HOUSE_Y': 2, 'HOUSE_N': 1, 'HOUSE': 1, 'APT': 0}
        pur = {'COMPANION': 2, 'SPORT': 2, 'WORK': 2}
        return (
            tl.get(lead.timeline or '', 0)
            + bud.get(lead.budget_ok or '', 0)
            + hs.get(lead.housing_type or '', 0)
            + pur.get(lead.purpose or '', 0)
        )

    def _determine_classification(self, score: int) -> str:
        if score >= 7:
            return 'HOT_LEAD'
        if score >= 4:
            return 'WARM_LEAD'
        return 'COLD_LEAD'

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

        purpose_tag = {'COMPANION': 'companhia', 'SPORT': 'esporte', 'WORK': 'trabalho'}
        if lead.purpose in purpose_tag:
            tag_names.append(purpose_tag[lead.purpose])

        classification_tag = {'HOT_LEAD': 'hot-lead', 'WARM_LEAD': 'warm-lead', 'COLD_LEAD': 'cold-lead'}
        if lead.lead_classification in classification_tag:
            tag_names.append(classification_tag[lead.lead_classification])

        for name in tag_names:
            tag, _ = LeadTag.objects.get_or_create(
                organization=lead.organization,
                name=name,
            )
            lead.tags.add(tag)
