"""
Traduz o estado comercial de um Lead (usando os campos que já existem em
apps.leads — Lead.status, Lead.lead_classification, LeadProfile.is_reserved/
is_purchased) para o funil comercial que o agente de Google Ads raciocina em
cima: NEW, CONTACTED, QUALIFIED, UNQUALIFIED, NEGOTIATING, RESERVED, SOLD, LOST.

Não cria nenhum campo/estado novo no app de leads — é só uma leitura derivada,
por isso vive aqui (apps.advertising), não em apps.leads.
"""
from apps.advertising.models import AdEvent

FUNNEL_STAGES = ['NEW', 'CONTACTED', 'QUALIFIED', 'UNQUALIFIED', 'NEGOTIATING', 'RESERVED', 'SOLD', 'LOST']


def commercial_stage(lead) -> str:
    profile = getattr(lead, 'profile', None)
    if profile and profile.is_purchased:
        return 'SOLD'
    if profile and profile.is_reserved:
        return 'RESERVED'
    if lead.is_archived and not (profile and (profile.is_reserved or profile.is_purchased)):
        return 'LOST'
    if lead.status == 'HANDOFF':
        return 'NEGOTIATING'
    if lead.lead_classification == 'DANGER_LEAD':
        return 'UNQUALIFIED'
    if lead.status == 'QUALIFIED' or lead.lead_classification in ('HOT_LEAD', 'WARM_LEAD'):
        return 'QUALIFIED'
    if lead.lead_classification == 'COLD_LEAD':
        return 'UNQUALIFIED'
    if lead.status in ('QUALIFYING', 'CLOSED'):
        return 'CONTACTED'
    return 'NEW'


def funnel_summary(campaign) -> dict:
    """
    Conta leads atribuídos a esta campanha por estágio comercial, mais os eventos
    de topo de funil (visita à landing, clique no WhatsApp) que ainda não viraram
    lead. Só existe "amostra suficiente" quando o chamador (o agente) decidir —
    aqui só devolvemos os números reais, sem interpretação.
    """
    attributions = campaign.lead_attributions.select_related('lead', 'lead__profile').all()
    stage_counts = {stage: 0 for stage in FUNNEL_STAGES}
    for attribution in attributions:
        stage_counts[commercial_stage(attribution.lead)] += 1

    page_views = AdEvent.objects.filter(campaign=campaign, event_type='page_view').count()
    whatsapp_clicks = AdEvent.objects.filter(campaign=campaign, event_type='whatsapp_click').count()

    return {
        'page_views': page_views,
        'whatsapp_clicks': whatsapp_clicks,
        'total_leads': attributions.count(),
        'stages': stage_counts,
    }
