import re

UF_NAMES = {
    'acre': 'AC', 'alagoas': 'AL', 'amapá': 'AP', 'amazonas': 'AM',
    'bahia': 'BA', 'ceará': 'CE', 'distrito federal': 'DF', 'espírito santo': 'ES',
    'goiás': 'GO', 'maranhão': 'MA', 'mato grosso do sul': 'MS', 'mato grosso': 'MT',
    'minas gerais': 'MG', 'pará': 'PA', 'paraíba': 'PB', 'paraná': 'PR',
    'pernambuco': 'PE', 'piauí': 'PI', 'rio de janeiro': 'RJ', 'rio grande do norte': 'RN',
    'rio grande do sul': 'RS', 'rondônia': 'RO', 'roraima': 'RR', 'santa catarina': 'SC',
    'são paulo': 'SP', 'sergipe': 'SE', 'tocantins': 'TO',
}

VALID_UFS = set(UF_NAMES.values())


def extract_uf(text: str) -> str | None:
    text_lower = text.lower()
    match = re.search(r'\b([A-Z]{2})\b', text.upper())
    if match and match.group(1) in VALID_UFS:
        return match.group(1)
    for name, uf in UF_NAMES.items():
        if name in text_lower:
            return uf
    return None


def extract_city(text: str) -> str | None:
    separators = r'[/\-,]'
    parts = re.split(separators, text)
    if len(parts) >= 1:
        city = parts[0].strip().title()
        if len(city) > 2:
            return city
    return None


def parse_time_minutes(text: str) -> int | None:
    text = text.lower()
    hours_match = re.search(r'(\d+(?:[.,]\d+)?)\s*h', text)
    if hours_match:
        return int(float(hours_match.group(1).replace(',', '.')) * 60)
    mins_match = re.search(r'(\d+)\s*min', text)
    if mins_match:
        return int(mins_match.group(1))
    num_match = re.search(r'(\d+)', text)
    if num_match:
        n = int(num_match.group(1))
        if n <= 24:
            return n * 60
        return n
    return None


def infer_housing_type(text: str) -> str | None:
    text = text.lower()
    if any(w in text for w in ['casa', 'house', 'quintal', 'yard']):
        return 'HOUSE'
    if any(w in text for w in ['apto', 'apartamento', 'apt', 'flat', 'condo']):
        return 'APT'
    return None


def infer_experience(text: str) -> str | None:
    text = text.lower()
    if any(w in text for w in ['3', 'terceiro', 'alta energia', 'high energy', 'border', 'husky', 'malamute']):
        return 'HAD_HIGH_ENERGY'
    if any(w in text for w in ['2', 'segundo', 'sim', 'yes', 'já tive', 'já tinha', 'tive']):
        return 'HAD_DOGS'
    if any(w in text for w in ['1', 'primeiro', 'não', 'nunca', 'first']):
        return 'FIRST_DOG'
    return None


def infer_budget(text: str) -> str | None:
    text = text.lower()
    if any(w in text for w in ['sim', 'yes', 'claro', 'ok', 'tudo bem', 'pode ser', 'cabe', '1']):
        return 'YES'
    if any(w in text for w in ['não', 'no', 'impossível', 'caro', 'muito', '2']):
        return 'NO'
    if any(w in text for w in ['talvez', 'maybe', 'depende', 'possível', '3']):
        return 'MAYBE'
    return None


def infer_timeline(text: str) -> str | None:
    text = text.lower()
    if any(w in text for w in ['agora', 'now', 'imediato', 'já', 'hoje', '1']):
        return 'NOW'
    if any(w in text for w in ['30', 'trinta', 'mês', '2']):
        return 'THIRTY_DAYS'
    if any(w in text for w in ['60', 'sessenta', 'mais', 'depois', '3']):
        return 'SIXTY_PLUS'
    return None


def infer_purpose(text: str) -> str | None:
    text = text.lower()
    if any(w in text for w in ['companheiro', 'pet', 'estimação', 'família', 'family', '1']):
        return 'COMPANION'
    if any(w in text for w in ['esporte', 'sport', 'agility', 'competição', '2']):
        return 'SPORT'
    if any(w in text for w in ['trabalho', 'work', 'pastoreio', 'gado', 'fazenda', '3']):
        return 'WORK'
    return None
