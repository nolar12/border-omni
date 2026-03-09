STATE_INITIAL = 'initial'
STATE_Q1_LOCATION = 'q1_location'
STATE_Q2_HOUSING = 'q2_housing'
STATE_Q3_TIME = 'q3_time'
STATE_Q4_EXPERIENCE = 'q4_experience'
STATE_Q5_BUDGET = 'q5_budget'
STATE_Q6_TIMELINE = 'q6_timeline'
STATE_Q7_PURPOSE = 'q7_purpose'
STATE_COMPLETE = 'complete'

STATE_ORDER = [
    STATE_INITIAL,
    STATE_Q1_LOCATION,
    STATE_Q2_HOUSING,
    STATE_Q3_TIME,
    STATE_Q4_EXPERIENCE,
    STATE_Q5_BUDGET,
    STATE_Q6_TIMELINE,
    STATE_Q7_PURPOSE,
    STATE_COMPLETE,
]

MESSAGES = {
    STATE_INITIAL: (
        "Olá! 🐕 Bem-vindo ao Border Omni!\n"
        "Vou fazer algumas perguntas rápidas para entender melhor o que você precisa.\n\n"
        "Primeira pergunta: *Qual é a sua cidade e estado?* (ex: Porto Alegre/RS)"
    ),
    STATE_Q1_LOCATION: (
        "Qual é a sua cidade e estado? (ex: São Paulo/SP)"
    ),
    STATE_Q2_HOUSING: (
        "Você mora em *casa* ou *apartamento*?"
    ),
    STATE_Q3_TIME: (
        "Quantas horas por dia você teria disponível para cuidar de um Border Collie? "
        "(ex: 2 horas, 4 horas)"
    ),
    STATE_Q4_EXPERIENCE: (
        "Você já teve cachorro antes?\n"
        "1. Não, seria meu primeiro cão\n"
        "2. Sim, já tive cães\n"
        "3. Sim, já tive raça de alta energia"
    ),
    STATE_Q5_BUDGET: (
        "O investimento mensal para um Border Collie de qualidade (alimentação, veterinário, etc) "
        "fica entre R$ 800-1.500/mês. *Isso cabe no seu orçamento?*"
    ),
    STATE_Q6_TIMELINE: (
        "Para quando você está pensando em adquirir?\n"
        "1. Agora (imediato)\n"
        "2. Em até 30 dias\n"
        "3. Em 60 dias ou mais"
    ),
    STATE_Q7_PURPOSE: (
        "Qual seria a principal finalidade?\n"
        "1. Companheiro / pet de estimação\n"
        "2. Esporte / agility\n"
        "3. Trabalho / pastoreio"
    ),
    STATE_COMPLETE: (
        "✅ Perfeito! Tenho todas as informações que preciso.\n"
        "Em breve um de nossos especialistas entrará em contato com você. 🐾"
    ),
}

NEXT_STATE = {
    STATE_INITIAL: STATE_Q1_LOCATION,
    STATE_Q1_LOCATION: STATE_Q2_HOUSING,
    STATE_Q2_HOUSING: STATE_Q3_TIME,
    STATE_Q3_TIME: STATE_Q4_EXPERIENCE,
    STATE_Q4_EXPERIENCE: STATE_Q5_BUDGET,
    STATE_Q5_BUDGET: STATE_Q6_TIMELINE,
    STATE_Q6_TIMELINE: STATE_Q7_PURPOSE,
    STATE_Q7_PURPOSE: STATE_COMPLETE,
    STATE_COMPLETE: STATE_COMPLETE,
}
