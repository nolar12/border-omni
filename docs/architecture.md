# Arquitetura — Border Omni

## Visão Geral

Border Omni é um SaaS multi-tenant de qualificação de leads via WhatsApp. A IA conduz uma conversa estruturada com o lead, calcula uma pontuação e classifica em Tier A/B/C. Quando necessário, o atendimento é transferido para um humano.

---

## Fluxo principal

```
WhatsApp User
     │
     ▼ POST /api/webhooks/whatsapp/
┌──────────────────────────────────┐
│         WhatsAppWebhookView      │
│  1. Identifica organização       │
│  2. Cria/busca Lead por telefone │
│  3. Salva mensagem (IN)          │
│  4. Chama QualifierEngine        │
│  5. Salva respostas (OUT)        │
└──────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│         QualifierEngine          │
│  - State machine (7 perguntas)   │
│  - Parsers de linguagem natural  │
│  - Cálculo de score (0-100)      │
│  - Tier assignment (A/B/C)       │
│  - Auto-tags                     │
└──────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│         Lead atualizado          │
│  status: QUALIFIED               │
│  tier: A | B | C                 │
│  score: 0-100                    │
└──────────────────────────────────┘
```

---

## Fluxo de Handoff Humano

```
Agente vê lead QUALIFIED no painel
     │
     ▼ POST /api/leads/{id}/assume/
┌───────────────────────────────┐
│  lead.is_ai_active = False    │
│  lead.assigned_to = user      │
│  lead.status = HANDOFF        │
│  Mensagem automática enviada  │
└───────────────────────────────┘
     │
     ▼
Agente troca mensagens manualmente
POST /api/leads/{id}/send_message/
     │
     ▼ POST /api/leads/{id}/release/
Devolve para IA (opcional)
```

---

## Arquitetura de Camadas

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND (React)                  │
│  localhost:9021                                      │
│                                                      │
│  Topbar ──── Sidebar ──── Content                   │
│              Dashboard                               │
│              LeadsPage (3 colunas)                   │
│              Channels / Plans / Simulator            │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP /api/*
                      │ (proxy Vite → 9022)
┌─────────────────────▼───────────────────────────────┐
│                   BACKEND (Django)                   │
│  localhost:9022                                      │
│                                                      │
│  /api/auth/          JWT Auth                        │
│  /api/leads/         CRUD + actions                  │
│  /api/channels/      ChannelProvider CRUD            │
│  /api/quick-replies/ Templates                       │
│  /api/plans/         Planos SaaS                     │
│  /api/subscription/  Assinatura atual                │
│  /api/webhooks/      WhatsApp inbound                │
└─────────────────────┬───────────────────────────────┘
                      │ PyMySQL
┌─────────────────────▼───────────────────────────────┐
│                  MySQL (border_leads)                 │
│  organizations, leads, conversations, messages       │
│  channels_channelprovider, quick_replies, notes      │
│  plans, subscriptions, user_profiles                 │
└─────────────────────────────────────────────────────┘
```

---

## Multi-tenant

Cada `Organization` é um tenant isolado. Todos os models principais têm FK para `Organization`:

```
Organization (1) ──── (N) Lead
Organization (1) ──── (N) ChannelProvider
Organization (1) ──── (N) QuickReply
Organization (1) ──── (1) Subscription ──── (1) Plan
Organization (1) ──── (N) UserProfile ──── (1) User
```

O isolamento é feito nas views DRF filtrando sempre por `request.user.profile.organization`.

---

## QualifierEngine — Máquina de Estados

```
initial
   │
   ▼
q1_location   → cidade/estado
   │
   ▼
q2_housing    → casa / apartamento
   │
   ▼
q3_time       → horas/dia disponíveis
   │
   ▼
q4_experience → experiência com cães
   │
   ▼
q5_budget     → orçamento mensal
   │
   ▼
q6_timeline   → quando quer adquirir
   │
   ▼
q7_purpose    → finalidade (companheiro/esporte/trabalho)
   │
   ▼
complete      → score calculado, tier atribuído
```

### Score (0–100)

| Critério | Pontos |
|---|---|
| Casa com quintal | 20 |
| 4h+ por dia | 25 |
| Experiência com alta energia | 20 |
| Orçamento confirmado | 20 |
| Quer agora (NOW) | 15 |
| Tem filhos pequenos | -5 |

### Tiers

| Score | Tier |
|---|---|
| 70–100 | A (quente) |
| 40–69 | B (morno) |
| 0–39 | C (frio) |

---

## Segurança

- JWT (access 24h, refresh 7d com rotação)
- Todos os endpoints requerem autenticação exceto `/api/auth/login`, `/api/auth/register` e `/api/webhooks/whatsapp/`
- O webhook WhatsApp é validado por `webhook_verify_token` da `ChannelProvider`
- O isolamento multi-tenant é feito por FK de organização nas queries
