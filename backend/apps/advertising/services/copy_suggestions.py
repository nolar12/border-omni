"""
Geração simples (baseada em template, sem IA) de sugestões de headline/description/
keyword para uma campanha Google Search a partir dos dados que o Border Omni já tem
sobre a ninhada e o canil. O usuário revisa/edita antes de publicar — não é geração
autônoma definitiva.
"""


def suggest_ad_copy(litter, user_profile=None) -> dict:
    breed = (user_profile.kennel_breed if user_profile and user_profile.kennel_breed else None)
    if not breed:
        first_puppy = litter.puppies.first() if hasattr(litter, 'puppies') else None
        breed = getattr(first_puppy, 'breed', None) or 'Border Collie'

    city = user_profile.kennel_city if user_profile else ''
    state = user_profile.kennel_state if user_profile else ''
    location = f'{city}/{state}' if city and state else (city or state or '')

    headlines = [
        f'Filhotes de {breed}' + (f' em {location}' if location else ''),
        f'Ninhada de {breed} Disponível',
        'Conheça Nossos Filhotes',
        'Filhotes de Criador Responsável',
    ]
    descriptions = [
        f'Filhotes de {breed} com pedigree e acompanhamento veterinário. Fale conosco pelo WhatsApp.',
        'Criação responsável, filhotes saudáveis e vacinados. Entre em contato e agende uma visita.',
    ]
    keywords = [
        f'filhote de {breed.lower()}',
        f'{breed.lower()} filhotes',
        f'comprar {breed.lower()}',
        f'canil {breed.lower()}' + (f' {location.lower()}' if location else ''),
    ]
    return {
        'ad_headlines': [h[:30] for h in headlines],
        'ad_descriptions': [d[:90] for d in descriptions],
        'ad_keywords': keywords,
    }
