STATE_INITIAL     = 'initial'
STATE_Q1_TIMELINE = 'q1_timeline'
STATE_Q2_HOUSING  = 'q2_housing'
STATE_Q3_BUDGET   = 'q3_budget'
STATE_Q4_PURPOSE  = 'q4_purpose'
STATE_COMPLETE    = 'complete'

STATE_ORDER = [
    STATE_INITIAL,
    STATE_Q1_TIMELINE,
    STATE_Q2_HOUSING,
    STATE_Q3_BUDGET,
    STATE_Q4_PURPOSE,
    STATE_COMPLETE,
]

MSG_MEDIA_CAPTION_VIDEO = ''
MSG_MEDIA_CAPTION_IMAGE = ''
# Alias para compatibilidade com o fallback legado (sempre vídeo)
MSG_MEDIA_CAPTION = MSG_MEDIA_CAPTION_VIDEO

MSG_INTRO = (
    "Fala!\n"
    "Aqui é o Marcello, do Border Collie Sul\n\n"
    "Vi que você veio pelo vídeo — já já eu te respondo com mais detalhes"
)

MESSAGES = {
    STATE_INITIAL: MSG_INTRO,
    STATE_Q1_TIMELINE: (
        "Para quando você está pensando em trazer seu Border Collie para casa?\n\n"
        "1. Agora — quero o mais rápido possível\n"
        "2. Em até 30 dias\n"
        "3. Em 2 a 3 meses\n"
        "4. Ainda estou pesquisando"
    ),
    STATE_Q2_HOUSING: (
        "Legal! Agora me conta uma coisa:\n\n"
        "Você mora em qual tipo de ambiente?\n\n"
        "1. Casa com pátio\n"
        "2. Casa sem pátio\n"
        "3. Apartamento"
    ),
    STATE_Q3_BUDGET: (
        "Perfeito!\n\n"
        "Só para alinhar expectativas:\n\n"
        "Nossos filhotes, com pedigree, microchip e todo acompanhamento inicial, "
        "têm valor a partir de R$ 5.000.\n\n"
        "Esse investimento está dentro do que você planeja para adquirir seu filhote?\n\n"
        "1. Sim, está dentro do planejamento\n"
        "2. Talvez, gostaria de entender melhor\n"
        "3. Ainda estou pesquisando valores"
    ),
    STATE_Q4_PURPOSE: (
        "Última curiosidade:\n\n"
        "Você procura seu Border Collie principalmente para:\n\n"
        "1. Companhia / família\n"
        "2. Esporte (agility, frisbee, atividades)\n"
        "3. Trabalho ou pastoreio\n"
        "4. Ainda estou pesquisando sobre a raça"
    ),
    STATE_COMPLETE: (
        "Perfeito! Obrigado pelas respostas.\n\n"
        "Estamos juntando as fotos e opções disponíveis da nova ninhada para te enviar.\n\n"
        "Entraremos em contato em breve!"
    ),
}

NEXT_STATE = {
    STATE_INITIAL:     STATE_Q1_TIMELINE,
    STATE_Q1_TIMELINE: STATE_Q2_HOUSING,
    STATE_Q2_HOUSING:  STATE_Q3_BUDGET,
    STATE_Q3_BUDGET:   STATE_Q4_PURPOSE,
    STATE_Q4_PURPOSE:  STATE_COMPLETE,
    STATE_COMPLETE:    STATE_COMPLETE,
}
