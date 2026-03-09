# Border Omni

SaaS de qualificação de leads via WhatsApp com IA conversacional, atendimento humano e arquitetura omnichannel.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Django 4.2 + DRF + SimpleJWT + PyMySQL |
| Frontend | React 18 + Vite + Tailwind CSS v4 + DaisyUI v5 |
| Banco de dados | MySQL 8 (`border_leads`) |
| Mobile | Capacitor (Android / iOS) |

---

## Inicialização rápida

```bash
# Clone o repositório
git clone git@github.com:marcellosouza12/border-omni.git
cd border-omni

# Criar e ativar ambiente Python
python3 -m virtualenv venv
source venv/bin/activate

# Instalar dependências Python
pip install django==4.2.29 djangorestframework djangorestframework-simplejwt \
            django-cors-headers django-filter PyMySQL

# Instalar dependências Node
cd frontend && npm install && cd ..

# Aplicar migrações
cd backend && python manage.py migrate && cd ..

# Popular banco com dados iniciais
cd backend && python manage.py seed && cd ..

# Iniciar todos os serviços
./start.sh start
```

Acesse:
- **Frontend**: http://localhost:9021
- **Backend API**: http://localhost:9022/api/
- **Admin Django**: http://localhost:9022/admin

---

## Credenciais padrão

| Campo | Valor |
|---|---|
| Email | `marcello12souza@gmail.com` |
| Senha | `admin123` |
| DB Host | `localhost:3306` |
| DB Name | `border_leads` |
| DB User | `root` / `cello12` |

---

## Comandos do script

```bash
./start.sh start    # inicia frontend (9021) + backend (9022)
./start.sh stop     # encerra todos os serviços
./start.sh restart  # reinicia
./start.sh status   # mostra PIDs e estado
./start.sh logs     # últimas linhas dos logs
```

---

## Estrutura do projeto

```
border-omni/
├── backend/              # Django 4.2
│   ├── apps/
│   │   ├── core/         # Organization, Plan, Subscription, UserProfile
│   │   ├── leads/        # Lead, LeadTag, Note
│   │   ├── conversations/ # Conversation, Message
│   │   ├── quick_replies/ # QuickReply templates
│   │   ├── channels/     # ChannelProvider (WhatsApp/Instagram)
│   │   └── qualifier/    # QualifierEngine (IA conversacional)
│   ├── api/              # Serializers, Views, URLs (DRF)
│   ├── config/           # settings.py, urls.py
│   └── manage.py
├── frontend/             # React 18 + Vite
│   └── src/
│       ├── components/   # Layout, Sidebar, Topbar, Footer, etc.
│       ├── pages/        # Dashboard, LeadsPage, Channels, Plans, etc.
│       ├── services/     # API clients (auth, leads, channels, etc.)
│       └── types/        # TypeScript interfaces
├── docs/                 # Documentação detalhada
├── logs/                 # Logs de runtime
├── venv/                 # Ambiente Python
└── start.sh              # Script de inicialização
```

---

## Documentação

| Arquivo | Conteúdo |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Arquitetura geral, fluxos e diagramas |
| [docs/backend.md](docs/backend.md) | Models, configuração Django, seed |
| [docs/api-reference.md](docs/api-reference.md) | Todos os endpoints da API |
| [docs/frontend.md](docs/frontend.md) | Componentes, páginas e serviços |
| [docs/database.md](docs/database.md) | Schema MySQL, tabelas e relacionamentos |
| [docs/whatsapp.md](docs/whatsapp.md) | Configuração do webhook WhatsApp |
| [docs/saas-plans.md](docs/saas-plans.md) | Planos, limites e modelo de assinatura |
| [docs/mobile.md](docs/mobile.md) | Build Android/iOS com Capacitor |
