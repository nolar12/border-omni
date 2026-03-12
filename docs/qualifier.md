# QualifierEngine — Border Omni

## Visão geral

O `QualifierEngine` é uma máquina de estados que conduz automaticamente a conversa com o lead pelo WhatsApp. Faz 4 perguntas, calcula dois scores independentes e classifica o lead em **Tier A/B/C** (escala 0–100) e **HOT/WARM/COLD** (escala 0–10).

**Arquivo principal:** `backend/apps/qualifier/engine.py`  
**Estados e mensagens:** `backend/apps/qualifier/states.py`  
**Parsers:** `backend/apps/qualifier/parsers.py`

---

## Fluxo completo

```
lead envia qualquer mensagem
        ↓
STATE_INITIAL
  → sorteia variante A/B/C/D (A/B test de mídia)
  → envia [mídia da variante] + [intro] + [Q1]
  → state = q1_timeline
        ↓
Q1 — Prazo de compra  (state: q1_timeline)
  → state = q2_housing
        ↓
Q2 — Tipo de moradia  (state: q2_housing)
  → state = q3_budget
        ↓
Q3 — Orçamento        (state: q3_budget)
  → state = q4_purpose
        ↓
Q4 — Finalidade       (state: q4_purpose)
  → _finalize() → calcula score + tier + lead_classification
  → state = complete
        ↓
Mensagem final enviada
```

---

## Mensagem de introdução (STATE_INITIAL)

Enviada em 3 partes separadas quando o lead manda qualquer mensagem pela primeira vez:

### Parte 1 — Mídia A/B (se URL configurada)
Vídeo ou foto sorteada entre as variantes A, B, C ou D (ver [docs/ab-test.md](ab-test.md)).

Legenda enviada com a mídia:
```
Esse vídeo é de uma ninhada anterior nossa 🐾

Só para você conhecer melhor o padrão dos nossos filhotes.

A ninhada atual ainda é bem novinha, mas já temos algumas reservas feitas.

Vou te fazer 4 perguntinhas rápidas para entender melhor o que você procura.
```

### Parte 2 — Intro
```
Olá! 🐕 Aqui é a Border Collie Sul.

Nossos filhotes são filhos do Sky e da Leia, com excelente linhagem e criados em ambiente familiar.

Eles são entregues com:

✔ Pedigree
✔ Microchip
✔ Registro do canil
✔ Vermifugação e primeira vacina

Alguns filhotes desta ninhada já estão reservados.

Depois das perguntinhas eu já te mostro quais ainda estão disponíveis. 🐾
```

### Parte 3 — Q1 (imediatamente após a intro)

---

## Pergunta 1 — Prazo de compra (state: `q1_timeline`)

```
Para quando você está pensando em trazer seu Border Collie para casa? 📅

1️⃣ Agora — quero o mais rápido possível
2️⃣ Em até 30 dias
3️⃣ Em 2 a 3 meses
4️⃣ Ainda estou pesquisando
```

**Parsing da resposta:**

| Resposta detectada | `timeline` |
|---|---|
| "1", "agora", "urgente", "rápido", "imediato" | `NOW` |
| "2", "30", "trinta" | `THIRTY_DAYS` |
| "3", "mês", "mes" | `SIXTY_PLUS` |
| "4", "pesquisando" ou qualquer outra | `RESEARCHING` |

---

## Pergunta 2 — Tipo de moradia (state: `q2_housing`)

```
Legal! Agora me conta uma coisa:

Você mora em qual tipo de ambiente? 🏠

1️⃣ Casa com pátio
2️⃣ Casa sem pátio
3️⃣ Apartamento
```

**Parsing da resposta:**

| Resposta detectada | `housing_type` |
|---|---|
| "3", "apart", "apto", "flat", "studio", "condomínio" | `APT` |
| "2", "sem pátio", "sem patio", "sem quintal" | `HOUSE_N` |
| "1", "pátio", "patio", "quintal", "casa", "sítio", "chácara", "rural" | `HOUSE_Y` |

> **Nota:** `HOUSE` (legado) ainda existe no banco para leads antigos e recebe o mesmo score de `HOUSE_N`.

---

## Pergunta 3 — Orçamento (state: `q3_budget`)

```
Perfeito!

Só para alinhar expectativas:

Nossos filhotes, com pedigree, microchip e todo acompanhamento inicial, têm valor a partir de R$ 5.000.

Esse investimento está dentro do que você planeja para adquirir seu filhote?

1️⃣ Sim, está dentro do planejamento
2️⃣ Talvez, gostaria de entender melhor
3️⃣ Ainda estou pesquisando valores
```

**Parsing da resposta:**

| Resposta detectada | `budget_ok` |
|---|---|
| "1", "sim", "dentro", "ok", "consigo", "pode" | `YES` |
| "2", "talvez", "entender", "melhor" | `MAYBE` |
| "3", "pesquisando" ou qualquer outra | `NO` |

---

## Pergunta 4 — Finalidade (state: `q4_purpose`)

```
Última curiosidade 😊

Você procura seu Border Collie principalmente para:

1️⃣ Companhia / família
2️⃣ Esporte (agility, frisbee, atividades)
3️⃣ Trabalho ou pastoreio
4️⃣ Ainda estou pesquisando sobre a raça
```

**Parsing da resposta:**

| Resposta detectada | `purpose` |
|---|---|
| "1", "companhia", "família", "familiar" | `COMPANION` |
| "2", "esporte", "agility", "frisbee", "atividade" | `SPORT` |
| "3", "trabalho", "pastoreio", "pastor" | `WORK` |
| "4", "pesquisando" ou qualquer outra | `None` |

> **Importante:** opção 4 / "pesquisando" salva `purpose=None`, o que resulta em 0 pts na classificação HOT/WARM/COLD.

---

## Mensagem final (state: `complete`)

```
Perfeito! Obrigado pelas respostas.

Vou te mostrar agora quais filhotes ainda estão disponíveis desta ninhada
e te enviar algumas fotos. 🐾

Se quiser, também posso te explicar as diferenças entre eles para te ajudar a escolher.
```

---

## Sistema 1 — Score e Tier (escala 0–100)

Mantido para compatibilidade e visualização geral.

```
Orçamento (40 pts — critério mais importante):
  YES   → 40 pts
  MAYBE → 20 pts
  NO    →  0 pts

Prazo (35 pts):
  NOW          → 35 pts
  THIRTY_DAYS  → 25 pts
  SIXTY_PLUS   → 10 pts
  RESEARCHING  →  0 pts

Moradia (25 pts):
  HOUSE_Y / HOUSE → 25 pts
  APT             →  8 pts
  HOUSE_N         →  8 pts  (casa sem pátio)
```

**Total máximo: 100 pts**

| Score | Tier | Ação recomendada |
|---|---|---|
| ≥ 65 | **A** | Contato imediato — orçamento e prazo definidos |
| 35–64 | **B** | Nutrir — interesse com restrições |
| < 35 | **C** | Baixa prioridade |

---

## Sistema 2 — Lead Classification (escala 0–10)

Sistema mais granular para priorização de follow-up.

```
Prazo:
  NOW          → +3
  THIRTY_DAYS  → +2
  SIXTY_PLUS   → +1
  RESEARCHING  → +0

Orçamento:
  YES   → +3
  MAYBE → +1
  NO    → +0

Moradia:
  HOUSE_Y          → +2  (casa com pátio)
  HOUSE_N / HOUSE  → +1  (casa sem pátio / legado)
  APT              → +0

Finalidade:
  COMPANION / SPORT / WORK → +2
  None (pesquisando)        → +0
```

**Total máximo: 10 pts**

| Score | Classificação | Comportamento |
|---|---|---|
| ≥ 7 | 🔥 `HOT_LEAD` | Notificação prioritária ao operador |
| 4–6 | 🟡 `WARM_LEAD` | Fila de follow-up normal |
| 0–3 | ❄️ `COLD_LEAD` | Manter automação, enviar mais informações |

---

## Tags automáticas geradas ao finalizar

| Condição | Tag |
|---|---|
| Tier A | `tier-a` |
| Tier B | `tier-b` |
| Tier C | `tier-c` |
| Mora em casa (qualquer tipo) | `casa` |
| Mora em apartamento | `apartamento` |
| Quer agora | `urgente` |
| Orçamento confirmado | `orcamento-ok` |
| Finalidade escolhida | `companhia` / `esporte` / `trabalho` |
| HOT_LEAD | `hot-lead` |
| WARM_LEAD | `warm-lead` |
| COLD_LEAD | `cold-lead` |

---

## Como ajustar as perguntas

Edite `backend/apps/qualifier/states.py` para alterar textos:

```python
MESSAGES = {
    STATE_Q1_TIMELINE: "Nova pergunta aqui...",
    STATE_Q2_HOUSING:  "...",
    STATE_Q3_BUDGET:   "...",
    STATE_Q4_PURPOSE:  "...",
    STATE_COMPLETE:    "...",
}
```

Edite `backend/apps/qualifier/engine.py` para:
- Alterar parsing das respostas → `_parse_and_update_lead()`
- Alterar score 0–100 → `_calculate_score()`
- Alterar tier A/B/C → `_determine_tier()`
- Alterar score 0–10 → `_calculate_classification_score()`
- Alterar HOT/WARM/COLD → `_determine_classification()`
- Alterar tags automáticas → `_generate_auto_tags()`

---

## Resetar conversa de um lead

```bash
cd backend && source ../venv/bin/activate
python3 manage.py shell -c "
from apps.leads.models import Lead
lead = Lead.objects.get(phone='5521972121012')
lead.conversation_state = 'initial'
lead.status = 'NEW'
lead.is_ai_active = True
lead.ab_variant = None
lead.lead_classification = None
lead.save()
print('Resetado:', lead.phone)
"
```

## Resetar TODOS os leads (apenas em desenvolvimento)

```bash
python3 manage.py shell -c "
from apps.leads.models import Lead
from apps.conversations.models import Conversation, Message
Message.objects.all().delete()
Conversation.objects.all().delete()
Lead.objects.all().delete()
print('Banco zerado')
"
```

> **CUIDADO:** Apaga permanentemente todos os leads, conversas e mensagens.

---

## Verificar classificação de um lead

```bash
python3 manage.py shell -c "
from apps.leads.models import Lead
l = Lead.objects.get(phone='5521XXXXXXXXX')
print(f'tier: {l.tier} | score: {l.score}/100')
print(f'classification: {l.lead_classification}')
print(f'housing: {l.housing_type} | timeline: {l.timeline}')
print(f'budget: {l.budget_ok} | purpose: {l.purpose}')
print(f'tags: {list(l.tags.values_list(\"name\", flat=True))}')
"
```
