# Backend — Border Omni

## Stack

- **Django 4.2** (LTS)
- **Django REST Framework** — API REST
- **SimpleJWT** — Autenticação JWT
- **PyMySQL** — Conector MySQL puro Python
- **django-filter** — Filtros na API
- **django-cors-headers** — CORS para o frontend

---

## Estrutura de pastas

```
backend/
├── config/
│   ├── __init__.py      # pymysql.install_as_MySQLdb()
│   ├── settings.py      # Configurações principais
│   ├── urls.py          # Rotas raiz
│   └── wsgi.py
├── apps/
│   ├── core/            # Organization, Plan, Subscription, UserProfile
│   ├── leads/           # Lead, LeadTag, LeadTagAssignment, Note
│   ├── conversations/   # Conversation, Message
│   ├── quick_replies/   # QuickReply
│   ├── channels/        # ChannelProvider
│   └── qualifier/       # QualifierEngine, parsers, states
└── api/
    ├── serializers/     # DRF Serializers
    ├── views/           # DRF Views e ViewSets
    └── urls.py          # Rotas da API
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
organization, phone, full_name, instagram_handle,
city, state, housing_type (HOUSE|APT|OTHER),
daily_time_minutes, experience_level, budget_ok, timeline, purpose,
has_kids, has_other_pets, score (0-100), tier (A|B|C),
status (NEW|QUALIFYING|QUALIFIED|HANDOFF|CLOSED),
source, channels_used, is_ai_active, assigned_to (FK→User),
conversation_state, tags (M2M→LeadTag)
# db_table: 'leads'
```

### leads.Note
```python
lead (FK), author (FK→User), text, created_at
# db_table: 'notes'
```

### conversations.Conversation
```python
lead (OneToOne), created_at, updated_at
# db_table: 'conversations'
```

### conversations.Message
```python
conversation (FK), direction (IN|OUT), text,
provider_message_id, created_at
# db_table: 'messages'
```

### channels.ChannelProvider
```python
organization, provider (whatsapp|instagram),
app_id, access_token, phone_number_id, business_account_id,
instagram_account_id, page_id, webhook_verify_token, webhook_url,
is_active, is_simulated, verification_status, last_verified_at
# db_table: 'channels_channelprovider'
```

### quick_replies.QuickReply
```python
organization, category (GREETING|PRICING|AVAILABILITY|SCHEDULING|INFO|CLOSING),
text, shortcut, is_active
# db_table: 'quick_replies'
```

---

## Configuração (settings.py)

```python
# Banco de dados — variáveis de ambiente com fallback
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

# JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
}
```

---

## Variáveis de ambiente

Crie um `.env` na raiz do backend para produção:

```env
SECRET_KEY=sua_chave_secreta_aqui
DEBUG=False
DB_NAME=border_leads
DB_USER=root
DB_PASSWORD=cello12
DB_HOST=localhost
DB_PORT=3306
```

---

## Seed

Popula o banco com dados iniciais (seguro executar múltiplas vezes):

```bash
source venv/bin/activate
cd backend
python manage.py seed
```

O seed cria:
- 3 planos: Free (R$0), Pro (R$197), Enterprise (R$597)
- Organização padrão
- Usuário admin (`marcello12souza@gmail.com` / `admin123`)
- Tags padrão: tier-a, tier-b, tier-c, casa, apartamento, urgente, experiente
- 6 quick replies de exemplo

---

## Migrações

```bash
# Criar migrações após alteração em models
python manage.py makemigrations

# Aplicar migrações
python manage.py migrate

# Para tabelas que já existem no banco (sem recriar)
python manage.py migrate --fake-initial
```

---

## Admin Django

Acesse `http://localhost:9022/admin` com as credenciais do superusuário.

Todos os models estão registrados no admin.

---

## Logs

Logs da aplicação em `border_omni.log` (no diretório `backend/`).

Configuração de logging em `settings.py` para o namespace `apps.*`.
