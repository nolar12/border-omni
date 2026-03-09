# API Reference — Border Omni

Base URL: `http://localhost:9022/api`

Autenticação: `Authorization: Bearer <access_token>`

---

## Auth

### POST `/auth/login`
Login e obtenção de tokens JWT.

**Request:**
```json
{ "email": "user@example.com", "password": "senha" }
```
**Response:**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "user": {
    "id": 1, "email": "user@example.com",
    "first_name": "Marcelo", "last_name": "Souza",
    "organization_name": "Border Collie Sul",
    "plan_name": "pro"
  }
}
```

### POST `/auth/register`
Registra novo usuário e organização.

**Request:**
```json
{
  "email": "novo@email.com",
  "password": "senha123",
  "first_name": "Nome",
  "last_name": "Sobrenome",
  "organization_name": "Minha Empresa"
}
```

### POST `/auth/refresh`
Renova access token usando refresh token.
```json
{ "refresh": "eyJ..." }
```

### GET `/auth/me`
Retorna dados do usuário autenticado.

---

## Leads

### GET `/leads/`
Lista leads da organização com paginação.

**Query params:**
| Param | Tipo | Descrição |
|---|---|---|
| `tier` | A \| B \| C | Filtrar por tier |
| `status` | NEW \| QUALIFYING \| QUALIFIED \| HANDOFF \| CLOSED | Status |
| `is_ai_active` | true \| false | IA ativa ou humano |
| `search` | string | Busca em phone, full_name, instagram_handle |
| `page` | int | Página (default: 1, page_size: 30) |

**Response:** `{ count, next, previous, results: [LeadListItem] }`

### GET `/leads/{id}/`
Detalhe completo do lead incluindo notes e tags.

### GET `/leads/{id}/messages/`
Histórico de mensagens do lead.

```json
[
  { "id": 1, "direction": "IN", "text": "Oi", "created_at": "..." },
  { "id": 2, "direction": "OUT", "text": "Olá! ...", "created_at": "..." }
]
```

### POST `/leads/{id}/assume/`
Agente assume o atendimento (desativa IA).

**Response:** Lead atualizado com `is_ai_active: false`, `assigned_to: user`

### POST `/leads/{id}/release/`
Devolve o atendimento para a IA.

### POST `/leads/{id}/send_message/`
Envia mensagem manual (apenas quando `is_ai_active: false`).
```json
{ "text": "Olá, posso ajudar?" }
```

### POST `/leads/{id}/add_note/`
Adiciona nota interna ao lead.
```json
{ "text": "Lead demonstrou interesse imediato." }
```

### GET `/leads/stats/`
Estatísticas da organização.
```json
{
  "total": 150,
  "tier_a": 30,
  "tier_b": 75,
  "tier_c": 45,
  "handoff": 12,
  "qualifying": 8,
  "qualified": 90
}
```

---

## Webhook WhatsApp

### GET `/webhooks/whatsapp/`
Verificação do webhook pelo Meta. Parâmetros: `hub.verify_token`, `hub.challenge`.

### POST `/webhooks/whatsapp/`
Recebe mensagem inbound.

**Headers:** `X-ORG-KEY: <api_key_da_organizacao>`

**Request:**
```json
{
  "from_phone": "+5551999888777",
  "text": "Oi, quero saber sobre os filhotes",
  "provider": "WHATSAPP",
  "organization_key": "<api_key>"
}
```

**Response:**
```json
{
  "received": true,
  "replies": ["Olá! Bem-vindo ao Border Omni! ..."],
  "lead": {
    "id": 42,
    "tier": null,
    "score": 0,
    "status": "QUALIFYING",
    "is_ai_active": true,
    "conversation_state": "q1_location"
  }
}
```

---

## Canais

### GET `/channels/`
Lista canais da organização.

### POST `/channels/`
Cria novo canal.
```json
{
  "provider": "whatsapp",
  "app_id": "1260435322688998",
  "phone_number_id": "1040197165841892",
  "business_account_id": "2133277890774145",
  "access_token": "EAAR...",
  "webhook_verify_token": "meu_token_secreto",
  "is_active": true
}
```

### PATCH `/channels/{id}/`
Atualiza canal existente.

### DELETE `/channels/{id}/`
Remove canal.

---

## Respostas Rápidas

### GET `/quick-replies/`
Lista templates ativos da organização.

### POST `/quick-replies/`
Cria novo template.
```json
{
  "category": "GREETING",
  "shortcut": "/ola",
  "text": "Olá {lead_name}! Sou {user_name}."
}
```

**Categorias:** `GREETING`, `PRICING`, `AVAILABILITY`, `SCHEDULING`, `INFO`, `CLOSING`

**Variáveis disponíveis:** `{lead_name}`, `{user_name}`

---

## Planos e Assinatura

### GET `/plans/`
Lista todos os planos disponíveis.

### GET `/subscription/`
Retorna assinatura atual da organização.

### POST `/subscription/`
Atualiza plano.
```json
{ "plan": "pro" }
```

---

## Códigos de erro comuns

| Código | Significado |
|---|---|
| 400 | Dados inválidos |
| 401 | Token inválido ou expirado |
| 403 | Sem permissão |
| 404 | Recurso não encontrado |
| 429 | Limite do plano atingido |
