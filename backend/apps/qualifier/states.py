STATE_INITIAL = 'initial'
STATE_Q1_BUDGET = 'q1_budget'
STATE_Q2_TIMELINE = 'q2_timeline'
STATE_Q3_HOUSING = 'q3_housing'
STATE_COMPLETE = 'complete'

STATE_ORDER = [
    STATE_INITIAL,
    STATE_Q1_BUDGET,
    STATE_Q2_TIMELINE,
    STATE_Q3_HOUSING,
    STATE_COMPLETE,
]

MESSAGES = {
    STATE_INITIAL: (
        "Olá! 🐕 Aqui é a *Border Collie Sul*!\n\n"
        "Que alegria receber seu contato! Nossos filhotes são filhos do *Sky* e da *Leia* — "
        "ambos com *linhagem de campeões*, saúde certificada e temperamento excepcional. "
        "São criados em ambiente familiar, com seleção genética rigorosa e acompanhamento completo "
        "antes, durante e após a entrega. 🏆\n\n"
        "📌 Conheça mais:\n"
        "🌐 www.bordercolliesul.com.br\n"
        "📸 Instagram: @bordercolliesul\n\n"
        "Vou te fazer *3 perguntinhas rápidas* para entender melhor como posso te ajudar, tudo bem?\n\n"
        "Nossos filhotes têm valor a partir de *R$ 5.000* — um investimento em genética, "
        "saúde e procedência comprovadas.\n\n"
        "*Esse valor está dentro do seu planejamento?*\n\n"
        "1️⃣ Sim, consigo investir esse valor\n"
        "2️⃣ Preciso de mais informações antes\n"
        "3️⃣ Ainda não, mas quero me planejar"
    ),
    STATE_Q1_BUDGET: (
        "Nossos filhotes têm valor a partir de *R$ 5.000* — "
        "filhos do *Sky* e da *Leia*, com linhagem de campeões e saúde certificada.\n\n"
        "*Esse investimento está dentro do seu planejamento?*\n\n"
        "1️⃣ Sim, consigo investir esse valor\n"
        "2️⃣ Preciso de mais informações antes\n"
        "3️⃣ Ainda não, mas quero me planejar"
    ),
    STATE_Q2_TIMELINE: (
        "Ótimo! E para quando você está pensando em trazer seu Border Collie para casa? 📅\n\n"
        "1️⃣ Agora — quero o mais rápido possível\n"
        "2️⃣ Em até 30 dias\n"
        "3️⃣ Em 2 a 3 meses\n"
        "4️⃣ Ainda estou pesquisando, sem prazo definido"
    ),
    STATE_Q3_HOUSING: (
        "Última pergunta! 🏠 Você mora em *casa* ou *apartamento*?\n\n"
        "O Border Collie é uma raça de alta energia e precisa de espaço para se exercitar. "
        "Isso me ajuda a entender qual perfil de filhote combina melhor com você."
    ),
    STATE_COMPLETE: (
        "✅ *Perfeito, obrigado pelas informações!*\n\n"
        "Um dos nossos especialistas vai entrar em contato em breve para apresentar "
        "os filhotes disponíveis e tirar todas as suas dúvidas. 🐾\n\n"
        "_Border Collie Sul — criação responsável com procedência._"
    ),
}

NEXT_STATE = {
    STATE_INITIAL:   STATE_Q2_TIMELINE,
    STATE_Q1_BUDGET: STATE_Q2_TIMELINE,
    STATE_Q2_TIMELINE: STATE_Q3_HOUSING,
    STATE_Q3_HOUSING:  STATE_COMPLETE,
    STATE_COMPLETE:    STATE_COMPLETE,
}
