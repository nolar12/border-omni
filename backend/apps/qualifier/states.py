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

MSG_MEDIA_CAPTION = (
    "Esse vídeo é de uma ninhada anterior nossa 🐾\n\n"
    "Só para você conhecer melhor o padrão dos nossos filhotes.\n\n"
    "A ninhada atual ainda é bem novinha, mas já temos algumas reservas feitas.\n\n"
    "Vou te fazer 4 perguntinhas rápidas para entender melhor o que você procura."
)

MSG_INTRO = (
    "Olá! 🐕 Aqui é a Border Collie Sul.\n\n"
    "Nossos filhotes são filhos do Sky e da Leia, com excelente linhagem e criados em ambiente familiar.\n\n"
    "Eles são entregues com:\n\n"
    "✔ Pedigree\n"
    "✔ Microchip\n"
    "✔ Registro do canil\n"
    "✔ Vermifugação e primeira vacina\n\n"
    "Alguns filhotes desta ninhada já estão reservados.\n\n"
    "Depois das perguntinhas eu já te mostro quais ainda estão disponíveis. 🐾"
)

MESSAGES = {
    STATE_INITIAL: MSG_INTRO,
    STATE_Q1_TIMELINE: (
        "Para quando você está pensando em trazer seu Border Collie para casa? 📅\n\n"
        "1️⃣ Agora — quero o mais rápido possível\n"
        "2️⃣ Em até 30 dias\n"
        "3️⃣ Em 2 a 3 meses\n"
        "4️⃣ Ainda estou pesquisando"
    ),
    STATE_Q2_HOUSING: (
        "Legal! Agora me conta uma coisa:\n\n"
        "Você mora em qual tipo de ambiente? 🏠\n\n"
        "1️⃣ Casa com pátio\n"
        "2️⃣ Casa sem pátio\n"
        "3️⃣ Apartamento"
    ),
    STATE_Q3_BUDGET: (
        "Perfeito!\n\n"
        "Só para alinhar expectativas:\n\n"
        "Nossos filhotes, com pedigree, microchip e todo acompanhamento inicial, "
        "têm valor a partir de R$ 5.000.\n\n"
        "Esse investimento está dentro do que você planeja para adquirir seu filhote?\n\n"
        "1️⃣ Sim, está dentro do planejamento\n"
        "2️⃣ Talvez, gostaria de entender melhor\n"
        "3️⃣ Ainda estou pesquisando valores"
    ),
    STATE_Q4_PURPOSE: (
        "Última curiosidade 😊\n\n"
        "Você procura seu Border Collie principalmente para:\n\n"
        "1️⃣ Companhia / família\n"
        "2️⃣ Esporte (agility, frisbee, atividades)\n"
        "3️⃣ Trabalho ou pastoreio\n"
        "4️⃣ Ainda estou pesquisando sobre a raça"
    ),
    STATE_COMPLETE: (
        "Perfeito! Obrigado pelas respostas.\n\n"
        "Vou te mostrar agora quais filhotes ainda estão disponíveis desta ninhada "
        "e te enviar algumas fotos. 🐾\n\n"
        "Se quiser, também posso te explicar as diferenças entre eles para te ajudar a escolher."
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
