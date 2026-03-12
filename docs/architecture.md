# Arquitetura — Border Omni

## Visão Geral

Border Omni é um SaaS multi-tenant de qualificação de leads via WhatsApp. A IA conduz uma conversa estruturada com o lead (3–4 perguntas), calcula uma pontuação e classifica em Tier A/B/C. Quando necessário, o atendimento é transferido para um agente humano que pode enviar texto, imagens e documentos diretamente pelo painel.

---

## Fluxo principal — Mensagem de texto

```
WhatsApp User (cliente)
     │
     ▼ POST /api/webhooks/whatsapp/   (via ngrok em dev / domínio em prod)
┌──────────────────────────────────────┐
│         WhatsAppWebhookView          │
│  1. Detecta payload Meta vs simulador│
│  2. Identifica canal pelo phone_id   │
│  3. Identifica organização           │
│  4. Captura nome do contato (profile)│
│  5. Cria/busca Lead por telefone     │
│  6. Salva mensagem IN                │
│  7. Chama QualifierEngine            │
│  8. Salva respostas OUT              │
│  9. Envia respostas via Meta API     │
└──────────────────────────────────────┘
```

---

## Fluxo — Mídia recebida (imagem, vídeo, documento)

```
WhatsApp User envia foto/vídeo/doc
     │
     ▼ POST /api/webhooks/whatsapp/
┌──────────────────────────────────────┐
│  _handle_incoming_media()            │
│  1. Detecta tipo real (MIME/extensão)│
│  2. Obtém URL temporária do Meta API │
│  3. Baixa o arquivo                  │
│  4. Salva em /backend/media/whatsapp/│
│  5. Salva mensagem IN com URL local  │
└──────────────────────────────────────┘
     │
     ▼
Frontend exibe: miniatura / player / link
```

---

## Fluxo de Handoff Humano

```
Agente vê lead no painel → clica "Assumir"
     │
     ▼ POST /api/leads/{id}/assume/
┌───────────────────────────────────────┐
│  lead.is_ai_active = False            │
│  lead.assigned_to = agente logado     │
│  lead.status = HANDOFF                │
│  Mensagem "👋 Atendimento assumido"   │
│  enviada via WhatsApp API             │
└───────────────────────────────────────┘
     │
     ▼
Agente digita mensagens ou envia arquivos
POST /api/leads/{id}/send_message/   → texto enviado via Meta API
POST /api/leads/{id}/send_file/      → arquivo enviado via Meta API
     │
     ▼ POST /api/leads/{id}/release/  (opcional)
Devolve para IA
```

---

## Arquitetura de Camadas

```
┌──────────────────────────────────────────────────────┐
│                    FRONTEND (React + Vite)            │
│  localhost:9021                                       │
│                                                       │
│  Topbar ──── Sidebar ──── Content                    │
│              Dashboard                                │
│              LeadsPage (3 colunas)                    │
│                ├── Lista de leads (col 2)             │
│                └── Chat + Perfil + Notas (col 3)      │
│              Channels / Plans / Simulator             │
└──────────────────┬───────────────────────────────────┘
                   │ HTTP /api/*  e  /media/*
                   │ (proxy Vite → 9022)
┌──────────────────▼───────────────────────────────────┐
│                   BACKEND (Django 4.2)                │
│  localhost:9022                                       │
│                                                       │
│  /api/auth/          JWT Auth (login / refresh)       │
│  /api/leads/         CRUD + assume/release/send       │
│  /api/channels/      ChannelProvider CRUD             │
│  /api/quick-replies/ Respostas rápidas                │
│  /api/plans/         Planos SaaS                      │
│  /api/webhooks/      WhatsApp inbound (Meta + sim)    │
│  /media/             Arquivos recebidos (imagens etc) │
└──────────────────┬───────────────────────────────────┘
                   │ PyMySQL
┌──────────────────▼───────────────────────────────────┐
│                  MySQL (border_leads)                  │
│  organizations, leads, conversations, messages        │
│  channels_channelprovider, quick_replies, notes       │
│  plans, subscriptions, user_profiles                  │
└──────────────────────────────────────────────────────┘
```

---

## QualifierEngine — Máquina de Estados (atual)

```
initial
   │  (primeira mensagem → envia saudação + Q1)
   ▼
q1_budget     → orçamento: R$ 5.000 cabe? (1/2/3)
   │
   ▼
q2_timeline   → quando quer o filhote? (1/2/3/4)
   │
   ▼
q3_housing    → mora em casa ou apartamento?
   │
   ├── lead.full_name já existe? ──► complete
   │
   ▼
q4_name       → "Qual é o seu nome?" (só se sem nome)
   │
   ▼
complete      → score calculado, tier A/B/C atribuído
```

### Score (0–100)

| Critério | Pontos |
|---|---|
| Orçamento confirmado (YES) | 40 |
| Quer agora (NOW) | 35 |
| Mora em casa | 25 |
| Orçamento talvez (MAYBE) | 20 |
| Em até 30 dias | 25 |
| Apartamento | 8 |

### Tiers

| Score | Tier | Significado |
|---|---|---|
| ≥ 65 | **A** | Lead quente — prioridade máxima |
| 35–64 | **B** | Lead morno — tem interesse mas com restrições |
| < 35 | **C** | Lead frio — orçamento não confirmado / sem prazo |

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

## Segurança

- JWT (access 24h, refresh 7d com rotação automática)
- Todos os endpoints requerem autenticação exceto `/api/auth/login`, `/api/auth/register` e `/api/webhooks/whatsapp/`
- O webhook WhatsApp é validado por `webhook_verify_token` da `ChannelProvider`
- Tokens de acesso (`access_token`, `app_secret`) são `write_only` no serializer — nunca expostos na API
- Isolamento multi-tenant via FK de organização em todas as queries
