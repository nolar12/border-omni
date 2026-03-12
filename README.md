# Border Omni

SaaS de qualificação de leads via WhatsApp com IA conversacional, atendimento humano e arquitetura omnichannel.

---

## 🚀 Iniciar o sistema (desenvolvimento local)

### Opção 1 — Watchdog (recomendado)
O watchdog inicia o backend e o ngrok automaticamente e os reinicia se caírem.

```bash
# Na raiz do projeto:
nohup bash watchdog.sh &

# Acompanhar o log:
tail -f /tmp/border_omni_watchdog.log
```

### Opção 2 — Manual
```bash
# Terminal 1 — Backend
cd backend && source ../venv/bin/activate
python manage.py runserver 0.0.0.0:9022

# Terminal 2 — Frontend
cd frontend && npm run dev

# Terminal 3 — Ngrok (expor webhook)
ngrok http 9022
```

### Parar o watchdog
```bash
pkill -f watchdog.sh
pkill -f "runserver 0.0.0.0:9022"
```

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
| Senha | `Cello1212!` |
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

## Webhook WhatsApp — Configuração com ngrok (desenvolvimento local)

Use ngrok para expor o backend local na internet e configurar o webhook na Meta **antes de publicar no servidor definitivo**.

### 1. Instalar e autenticar o ngrok

> **ngrok já está instalado** em `~/.local/bin/ngrok` e autenticado nesta máquina. Pule para o passo 2.

Em uma nova máquina:

```bash
# Baixar e instalar
curl -sLo /tmp/ngrok.tgz https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xzf /tmp/ngrok.tgz -C ~/.local/bin/

# Autenticar (token em https://dashboard.ngrok.com → Your Authtoken)
~/.local/bin/ngrok config add-authtoken SEU_AUTHTOKEN_AQUI
```

### 2. Garantir que o backend está rodando

```bash
./start.sh start
# ou apenas o backend:
cd backend && python manage.py runserver 0.0.0.0:9022
```

### 3. Criar o túnel HTTPS

```bash
ngrok http 9022
```

O ngrok vai exibir algo como:

```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:9022
```

Copie a URL `https://...ngrok-free.app` — ela será usada na Meta.

### 4. Configurar o Webhook na Meta (developers.facebook.com)

1. Acesse [developers.facebook.com](https://developers.facebook.com/apps/) → seu App
2. Vá em **WhatsApp → Configuração**
3. Na seção **Webhooks**, clique em **Editar**
4. Preencha:

| Campo | Valor |
|---|---|
| **URL de callback** | `https://nonredeemable-superseriously-keyla.ngrok-free.dev/api/webhooks/whatsapp/` |
| **Token de verificação** | `border_omni_wh_secret` |

5. Clique em **Verificar e salvar** — a Meta vai fazer um `GET` no endpoint e responde automaticamente com o `hub.challenge`
6. Ative as assinaturas: `messages`, `message_deliveries`, `message_reads`

### 5. Verificar se o webhook está respondendo

```bash
curl "https://nonredeemable-superseriously-keyla.ngrok-free.dev/api/webhooks/whatsapp/?hub.mode=subscribe&hub.verify_token=border_omni_wh_secret&hub.challenge=12345"
# Resposta esperada: 12345  ✅
```

### 6. Reabrir o túnel (se o ngrok cair)

```bash
~/.local/bin/ngrok http 9022
# A nova URL gerada deve ser atualizada no painel da Meta
```

### 7. Trocar para URL definitiva (após deploy AWS)

Quando o backend estiver no ar em produção, volte em **WhatsApp → Configuração → Webhooks** na Meta e troque a URL do ngrok pela URL definitiva:

```
https://api.seudominio.com/api/webhooks/whatsapp/
```

> **Atenção:** O ngrok gratuito gera uma URL diferente a cada reinicialização. Se o ngrok cair, repita o passo 4 com a nova URL.

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
