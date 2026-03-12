# Backend — Border Omni

## Stack

| Lib | Versão | Uso |
|---|---|---|
| Django | 4.2 LTS | Framework web |
| Django REST Framework | 3.x | API REST |
| SimpleJWT | latest | Autenticação JWT |
| PyMySQL | latest | Conector MySQL puro Python |
| django-filter | latest | Filtros na API |
| django-cors-headers | latest | CORS para o frontend |
| requests | latest | HTTP para Meta API |

---

## Estrutura de pastas

```
backend/
├── config/
│   ├── __init__.py      # pymysql.install_as_MySQLdb()
│   ├── settings.py      # Configurações principais
│   ├── urls.py          # Rotas raiz + /media/
│   └── wsgi.py
├── apps/
│   ├── core/            # Organization, Plan, Subscription, UserProfile
│   ├── leads/           # Lead, LeadTag, LeadTagAssignment, Note
│   ├── conversations/   # Conversation, Message
│   ├── quick_replies/   # QuickReply
│   ├── channels/        # ChannelProvider
│   └── qualifier/       # QualifierEngine, parsers, states
├── api/
│   ├── serializers/     # DRF Serializers
│   ├── views/           # DRF Views e ViewSets
│   └── urls.py          # Rotas da API
└── media/
    └── whatsapp/        # Mídias recebidas dos clientes (imagens, docs, vídeos)
```

---

## Models

### core.Organization
```python
id, name, api_key (UUID), is_active, created_at, updated_at
# db_table: 'organizations'
```

### core.UserProfile
```python
user (OneToOne→User), organization (FK), role, created_at
# db_table: 'user_profiles'
```

### core.Plan
```python
name (free|pro|enterprise), max_leads, max_agents, max_channels,
price_monthly, is_active
# db_table: 'plans'
```

### core.Subscription
```python
organization (OneToOne), plan (FK), status (active|trial|expired|cancelled),
trial_ends_at, current_period_end
# db_table: 'subscriptions'
```

### leads.Lead
```python
organization (FK), phone, full_name, instagram_handle,
city, state,

# Qualificação
housing_type (HOUSE_Y|HOUSE_N|HOUSE|APT|OTHER),
#   HOUSE_Y = Casa com pátio (novo)
#   HOUSE_N = Casa sem pátio (novo)
#   HOUSE   = Casa genérica (legado — mantido para compatibilidade)
#   APT     = Apartamento
budget_ok (YES|MAYBE|NO),
timeline (NOW|THIRTY_DAYS|SIXTY_PLUS|RESEARCHING),
purpose (COMPANION|SPORT|WORK|null),

# Scores e classificação
score (0-100),           # Sistema legado — ponderado (orçamento 40%, prazo 35%, moradia 25%)
tier (A|B|C),            # Baseado no score 0-100
lead_classification (HOT_LEAD|WARM_LEAD|COLD_LEAD|null),  # Novo — baseado em pontuação 0-10

# A/B Test
ab_variant (A|B|C|D|null),  # Variante de mídia sorteada no início do fluxo

status (NEW|QUALIFYING|QUALIFIED|HANDOFF|CLOSED),
source, channels_used, is_ai_active,
assigned_to (FK→User), conversation_state,
tags (M2M→LeadTag)
# db_table: 'leads'
```

### leads.Note
```python
lead (FK), author (FK→User), text, created_at
# db_table: 'notes'
```

### conversations.Conversation
```python
lead (OneToOne), organization (FK, nullable),
channel (whatsapp|instagram|facebook|messenger|other),
state (active|closed|pending),
last_message_at, created_at, updated_at
# db_table: 'conversations'
```

### conversations.Message
```python
conversation (FK), organization (FK),
direction (IN|OUT), text,
provider_message_id (media_id do Meta, nullable),
created_at
# db_table: 'messages'
# ATENÇÃO: organization_id é NOT NULL no MySQL (diferente do model Django)
```

### channels.ChannelProvider
```python
organization (FK), name, provider (whatsapp|instagram|facebook|messenger),
app_id, app_secret (write-only),
access_token (write-only), access_token_masked (read-only),
phone_number_id, business_account_id,
instagram_account_id, page_id,
webhook_verify_token, webhook_url,
is_active, is_simulated, verification_status, last_verified_at
# db_table: 'channels_channelprovider'
```

### quick_replies.QuickReply
```python
organization (FK), category (GREETING|PRICING|AVAILABILITY|...),
text, shortcut, is_active
# db_table: 'quick_replies'
```

---

## Endpoints da API

### Autenticação
| Método | URL | Descrição |
|---|---|---|
| POST | `/api/auth/login` | Login — retorna access + refresh token |
| POST | `/api/auth/refresh` | Renova access token |
| POST | `/api/auth/register` | Registra novo usuário |
| GET | `/api/auth/me` | Dados do usuário logado |

### Leads
| Método | URL | Descrição |
|---|---|---|
| GET | `/api/leads/` | Lista leads com filtros e paginação |
| GET | `/api/leads/{id}/` | Detalhe do lead |
| GET | `/api/leads/{id}/messages/` | Mensagens da conversa |
| POST | `/api/leads/{id}/assume/` | Agente assume o atendimento (desliga IA) |
| POST | `/api/leads/{id}/release/` | Devolve para IA |
| POST | `/api/leads/{id}/send_message/` | Envia texto via WhatsApp |
| POST | `/api/leads/{id}/send_file/` | Envia arquivo via WhatsApp (multipart/form-data) |
| POST | `/api/leads/{id}/add_note/` | Adiciona nota interna |
| DELETE | `/api/leads/{id}/delete/` | Remove lead, conversa e mensagens permanentemente |
| GET | `/api/leads/stats/` | Estatísticas (totais por tier/status) |
| GET | `/api/leads/ab_stats/` | Estatísticas de A/B test agrupadas por variante |

**Filtros disponíveis em `/api/leads/`:**
- `tier=A|B|C`
- `status=NEW|QUALIFYING|QUALIFIED|HANDOFF|CLOSED`
- `is_ai_active=true|false`
- `search=texto` (busca em phone, full_name, instagram_handle)

### Canais
| Método | URL | Descrição |
|---|---|---|
| GET | `/api/channels/` | Lista canais da organização |
| POST | `/api/channels/` | Cria canal |
| PATCH | `/api/channels/{id}/` | Atualiza canal |
| DELETE | `/api/channels/{id}/` | Remove canal |

### Outros
| Método | URL | Descrição |
|---|---|---|
| GET | `/api/quick-replies/` | Respostas rápidas |
| GET | `/api/plans/` | Planos disponíveis |
| GET/POST | `/api/webhooks/whatsapp/` | Webhook WhatsApp (público) |
| GET | `/media/whatsapp/{arquivo}` | Servir mídia recebida dos clientes |

---

## Configuração (settings.py)

```python
# Banco de dados
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', 'border_leads'),
        'USER': os.getenv('DB_USER', 'root'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'cello12'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '3306'),
    }
}

# JWT — tokens de 24h com refresh de 7 dias
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
}

# Mídia
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

---

## Atenção: discrepâncias modelo × banco

O banco MySQL `border_leads` foi criado antes do projeto e tem algumas diferenças dos models Django:

| Tabela | Campo | Situação |
|---|---|---|
| `messages` | `organization_id` | NOT NULL no MySQL, nullable no model — sempre passar `organization=org` |
| `conversations` | `channel`, `state` | Obrigatórios no MySQL — sempre usar `defaults=` no `get_or_create` |
| `channels_channelprovider` | `name`, `app_secret` | Adicionados via `ALTER TABLE` manualmente |

**Padrão correto para criar conversas:**
```python
conv, _ = Conversation.objects.get_or_create(
    lead=lead,
    defaults={'organization': org, 'channel': 'whatsapp', 'state': 'active'},
)
```

**Padrão correto para criar mensagens:**
```python
Message.objects.create(
    conversation=conv,
    organization=org,   # ← OBRIGATÓRIO
    direction='OUT',
    text=texto,
)
```

---

## Variáveis de ambiente (.env para produção)

```env
SECRET_KEY=sua_chave_secreta_longa_aqui
DEBUG=False
DB_NAME=border_leads
DB_USER=root
DB_PASSWORD=cello12
DB_HOST=localhost
DB_PORT=3306

# A/B Test — URLs públicas das mídias (WhatsApp faz download da URL)
AB_MEDIA_URL_A=https://SEU_DOMINIO/media/ab_test/variant_a.mp4
AB_MEDIA_URL_B=https://SEU_DOMINIO/media/ab_test/variant_b.png
AB_MEDIA_URL_C=https://SEU_DOMINIO/media/ab_test/variant_c.png
AB_MEDIA_URL_D=https://SEU_DOMINIO/media/ab_test/variant_d.png

# Legado — mantido para compatibilidade, não mais necessário com A/B test
# QUALIFICATION_MEDIA_URL=https://...
# QUALIFICATION_MEDIA_TYPE=video
```

---

## Seed

Popula o banco com dados iniciais (seguro executar múltiplas vezes):

```bash
cd backend && source ../venv/bin/activate
python manage.py seed
```

Cria:
- 3 planos: Free (R$0), Pro (R$197), Enterprise (R$597)
- Organização padrão "Border Collie Sul"
- Usuário admin: `marcello12souza@gmail.com` / `Cello1212!`
- Tags: tier-a, tier-b, tier-c, casa, apartamento, urgente, orcamento-ok, hot-lead, warm-lead, cold-lead, companhia, esporte, trabalho
- Quick replies de exemplo

---

## Migrações

```bash
# Criar migrações após alterar models
python manage.py makemigrations

# Aplicar migrações
python manage.py migrate

# Quando a tabela já existe no banco e não deve ser recriada
python manage.py migrate --fake apps_name 0001

# Verificar estado das migrações
python manage.py showmigrations
```

---

## Logs

```bash
# Log em tempo real
tail -f /tmp/backend.log

# Log do watchdog
tail -f /tmp/border_omni_watchdog.log
```
