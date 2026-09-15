"""
Monta o prompt do agente combinando as 4 camadas pedidas:
  1. skill (conhecimento permanente/metodologia — arquivo versionado, universal)
  2. briefing (contexto comercial da campanha específica — banco, por campanha)
  3. dados reais do Google Ads (via tools, não aqui)
  4. dados comerciais do nosso sistema (via tools, não aqui)

A skill nunca contém dado específico de uma campanha; o briefing nunca contém
metodologia genérica — a mistura dos dois é feita aqui, na hora de montar o prompt.
"""
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent / 'skills'


def load_skill(name: str = 'google_ads_performance_manager') -> str:
    path = SKILLS_DIR / f'{name}.md'
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return ''


def format_briefing(briefing) -> str:
    if not briefing:
        return 'Nenhum briefing cadastrado para esta campanha ainda — trate como uma campanha genérica de geração de leads.'

    lines = []
    if briefing.product_description:
        lines.append(f'Produto: {briefing.product_description}')
    if briefing.objective:
        lines.append(f'Objetivo: {briefing.objective}')
    if briefing.deadline:
        lines.append(f'Prazo: até {briefing.deadline.isoformat()}')
    if briefing.price_info:
        lines.append(f'Preço/valor: {briefing.price_info}')
    if briefing.primary_conversion:
        lines.append(f'Conversão principal: {briefing.primary_conversion}')
    if briefing.priority_regions:
        for group, cities in briefing.priority_regions.items():
            lines.append(f'Regiões prioritárias (grupo {group}): {", ".join(cities)}')
    if briefing.positive_intent_keywords:
        lines.append(f'Palavras-chave de intenção forte: {", ".join(briefing.positive_intent_keywords)}')
    if briefing.negative_keywords:
        lines.append(f'Negativas já definidas no briefing: {", ".join(briefing.negative_keywords)}')
    if briefing.do_not_negate_keywords:
        lines.append(f'NUNCA negativar automaticamente: {", ".join(briefing.do_not_negate_keywords)}')
    if briefing.notes:
        lines.append(f'Observações adicionais: {briefing.notes}')

    return '\n'.join(lines) if lines else 'Briefing cadastrado, porém sem campos preenchidos.'
