# Border Omni

SaaS de qualificação de leads via WhatsApp com IA conversacional, atendimento humano e arquitetura omnichannel.

---

## Iniciar o sistema (desenvolvimento local)

### Opção 1 — Watchdog (recomendado)

O watchdog inicia o backend e o ngrok automaticamente e os reinicia se caírem.

```bash
# Na raiz do projeto:
nohup bash watchdog.sh &

# Acompanhar o log:
tail -f /tmp/border_omni_watchdog.log
```

### Opção 2 — Script de inicialização

```bash
./start.sh start     # inicia frontend (9021) + backend (9022) + ngrok
./start.sh build     # compila o React para acesso externo via ngrok
./start.sh stop      # encerra todos os serviços
./start.sh restart   # reinicia
./start.sh status    # mostra PIDs e estado
./start.sh logs      # últimas linhas dos logs
```

### Opção 3 — Manual

```bash
# Terminal 1 — Backend
cd backend && source ../venv/bin/activate
python manage.py runserver 0.0.0.0:9022

# Terminal 2 — Frontend
cd frontend && npm run dev

# Terminal 3 — Ngrok (expor o app completo)
ngrok http 9021 --url=borderomni.ngrok.app
```

### Parar o watchdog

```bash
pkill -f watchdog.sh
pkill -f "runserver 0.0.0.0:9022"
```

---

## Acessar de fora (celular / fora do Wi-Fi)

O Ngrok expõe o **backend Django (porta 9022)** diretamente. O Django serve tanto a API/webhooks quanto o frontend React buildado — um único túnel para tudo.

### Como funciona

```
Celular → https://borderomni.ngrok.app → Ngrok → Django (9022)
                                                    ├── /api/...         → API REST
                                                    ├── /api/webhooks/   → Webhook WhatsApp
                                                    ├── /media/...       → Arquivos de mídia
                                                    └── /*               → App React (build)
```

### Passo a passo para acessar pelo celular

**1. Iniciar o sistema:**
```bash
./start.sh start
```

**2. Compilar o frontend** (necessário uma vez por sessão, ou após mudanças no código):
```bash
./start.sh build
```

**3. Acessar no celular:**
```
https://borderomni.ngrok.app
```

> O comando `./start.sh build` gera os arquivos estáticos em `frontend/dist/` que o Django passa a servir automaticamente. Para desenvolvimento local, continue usando `http://localhost:9021` (Vite com hot reload).

| URL | O que serve |
|---|---|
| `https://borderomni.ngrok.app` | App completo (React buildado) |
| `https://borderomni.ngrok.app/api/` | API REST |
| `https://borderomni.ngrok.app/media/` | Arquivos de mídia |
| `https://borderomni.ngrok.app/api/webhooks/whatsapp/` | Webhook WhatsApp (Meta) |

> O Ngrok precisa estar rodando para acesso externo funcionar. Use o watchdog para garantir que ele suba automaticamente.

---

## Acesso local

| URL | O que serve |
|---|---|
| `http://localhost:9021` | Frontend (React) |
| `http://localhost:9022/api/` | Backend API |
| `http://localhost:9022/admin` | Admin Django |

**Credenciais:**

| Campo | Valor |
|---|---|
| Email | `marcello12souza@gmail.com` |
| Senha | `Cello1212!` |
| DB Host | `localhost:3306` |
| DB Name | `border_leads` |
| DB User | `root` / `cello12` |

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Django 4.2 + DRF + SimpleJWT + PyMySQL |
| Frontend | React 18 + Vite + Tailwind CSS v4 + DaisyUI v5 |
| Banco de dados | MySQL 8 (`border_leads`) |
| Túnel externo | Ngrok (domínio fixo: `borderomni.ngrok.app`) |
| Mobile | Capacitor (Android / iOS) |

---

## Inicialização do zero

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

---

## Funcionalidades

### Leads

- Cadastro e gestão de leads com múltiplas tags
- Histórico de conversas por lead
- Indicador de canal ativo (WhatsApp, Instagram, Facebook)
- Notas internas por lead
- Filtros, busca e paginação

### Conversas

- Atendimento em tempo real via WhatsApp Business API
- Suporte a mensagens de texto, imagens, vídeos, documentos e áudio
- Atendimento humano com troca entre IA e operador
- Visualização por conversa (inbox style)

### Campanhas

Envio em massa de templates para leads selecionados individualmente ou em bloco.

- Seleção de leads por canal (WhatsApp, Instagram, Facebook)
- Envio de templates WhatsApp (HSM) para contatos WhatsApp
- Para Instagram e Facebook: envia o texto do template como mensagem direta (DM) — a API dessas plataformas não suporta templates estruturados
- Barra de progresso de envio em tempo real
- Indicador de canal por lead na tabela de seleção

### Templates de Mensagem

Criação, gestão e envio de templates para aprovação da Meta.

**Status do template:**

| Status | Descrição |
|---|---|
| `DRAFT` (Rascunho) | Salvo localmente, não enviado à Meta |
| `PENDING` | Enviado para aprovação, aguardando Meta |
| `APPROVED` | Aprovado — pronto para usar em campanhas |
| `REJECTED` | Reprovado pela Meta (motivo exibido na interface) |
| `PAUSED` | Pausado pela Meta |
| `DISABLED` | Desativado |

**Fluxo:**

1. Crie o template (texto, cabeçalho, rodapé, variáveis)
2. Salve como **Rascunho** ou **Envie para Aprovação** diretamente
3. Para rascunhos, clique em **Enviar para aprovação** quando quiser
4. A Meta notifica o status via webhook automaticamente — sem precisar recarregar a página

**Tipos de cabeçalho suportados:**

| Tipo | Descrição |
|---|---|
| `NONE` | Sem cabeçalho |
| `TEXT` | Texto fixo no cabeçalho |
| `IMAGE` | Imagem (JPEG/PNG, máx. 5 MB) |
| `VIDEO` | Vídeo (MP4, máx. 16 MB) |
| `DOCUMENT` | Documento PDF (máx. 16 MB) |

**Upload de mídia:** Ao criar um template com cabeçalho de imagem, vídeo ou documento, use o botão de upload para anexar o arquivo diretamente. O arquivo é salvo no servidor e a URL pública é preenchida automaticamente.

### Upload de Mídia

Endpoint genérico para upload de arquivos usados em templates:

- `POST /api/upload-media/` — aceita `multipart/form-data` com campo `file`
- Tipos aceitos: imagens (JPEG, PNG, GIF, WebP), vídeos (MP4, MOV, AVI), PDF
- Tamanho máximo: 16 MB
- Salvo em `backend/media/template_media/`
- URL pública retornada usa `MEDIA_BASE_URL` (configurável via `.env`)

### Webhook WhatsApp

Recebimento e processamento de eventos da Meta:

- `GET /api/webhooks/whatsapp/` — verificação do webhook pela Meta
- `POST /api/webhooks/whatsapp/` — recebimento de mensagens, status e atualizações de template

**Eventos processados:**

| Campo | Ação |
|---|---|
| `messages` | Cria/atualiza lead e conversa, dispara qualificador de IA |
| `message_deliveries` | Marca mensagem como entregue |
| `message_reads` | Marca mensagem como lida |
| `message_template_status_update` | Atualiza status do template (APPROVED, REJECTED, etc.) |

---

## Configuração do Ngrok

O domínio `borderomni.ngrok.app` está configurado como domínio fixo no Ngrok (plano pago).

### Webhook na Meta (developers.facebook.com)

1. Acesse [developers.facebook.com](https://developers.facebook.com/apps/) → seu App
2. Vá em **WhatsApp → Configuração**
3. Na seção **Webhooks**, clique em **Editar**
4. Preencha:

| Campo | Valor |
|---|---|
| **URL de callback** | `https://borderomni.ngrok.app/api/webhooks/whatsapp/` |
| **Token de verificação** | `border_omni_wh_secret` |

5. Clique em **Verificar e salvar**
6. Ative as assinaturas: `messages`, `message_deliveries`, `message_reads`, `message_template_quality_update`

### Verificar se o webhook está respondendo

```bash
curl "https://borderomni.ngrok.app/api/webhooks/whatsapp/?hub.mode=subscribe&hub.verify_token=border_omni_wh_secret&hub.challenge=12345"
# Resposta esperada: 12345  ✅
```

---

## Variáveis de ambiente (`.env` na raiz)

Crie um arquivo `.env` na raiz do projeto para sobrescrever qualquer configuração padrão:

```env
# URL pública base para links de mídia acessíveis externamente pela Meta
# Padrão em desenvolvimento: https://borderomni.ngrok.app
MEDIA_BASE_URL=https://borderomni.ngrok.app

# Banco de dados (se diferente do padrão)
DB_NAME=border_leads
DB_USER=root
DB_PASSWORD=cello12
DB_HOST=localhost
DB_PORT=3306

# Segurança (obrigatório em produção)
SECRET_KEY=django-insecure-border-omni-dev-key-change-in-production
DEBUG=True
```

---

## Estrutura do projeto

```
border-omni/
├── backend/              # Django 4.2
│   ├── apps/
│   │   ├── core/         # Organization, Plan, Subscription, UserProfile
│   │   ├── leads/        # Lead, LeadTag, Note
│   │   ├── conversations/ # Conversation, Message, MessageTemplate
│   │   ├── quick_replies/ # QuickReply
│   │   ├── channels/     # ChannelProvider (WhatsApp/Instagram/Facebook)
│   │   └── qualifier/    # QualifierEngine (IA conversacional)
│   ├── api/              # Serializers, Views, URLs (DRF)
│   │   ├── views/        # LeadViewSet, MessageTemplateViewSet, UploadMediaView, ...
│   │   ├── serializers/  # Serializers DRF
│   │   └── urls.py       # Roteamento da API
│   ├── config/           # settings.py, urls.py, wsgi.py
│   ├── media/            # Arquivos de upload (template_media/, ab_test/)
│   └── manage.py
├── frontend/             # React 18 + Vite
│   └── src/
│       ├── components/   # Layout, Sidebar, Topbar, Footer, etc.
│       ├── pages/        # Dashboard, LeadsPage, CampaignsPage, TemplatesPage, ...
│       ├── services/     # API clients (auth, leads, messageTemplates, mediaUpload, ...)
│       └── types/        # TypeScript interfaces
├── docs/                 # Documentação detalhada
├── logs/                 # Logs de runtime
├── venv/                 # Ambiente Python
├── start.sh              # Script de inicialização (frontend + backend + ngrok)
└── watchdog.sh           # Watchdog — reinicia backend e ngrok se caírem
```

---

## Endpoints da API

| Método | URL | Descrição |
|---|---|---|
| `POST` | `/api/token/` | Login (retorna JWT) |
| `POST` | `/api/token/refresh/` | Renovar token |
| `GET/POST` | `/api/leads/` | Listar / criar leads |
| `GET/PUT/PATCH/DELETE` | `/api/leads/{id}/` | Detalhe / atualizar / deletar lead |
| `POST` | `/api/leads/{id}/send_template/` | Enviar template para o lead |
| `GET/POST` | `/api/conversations/` | Listar / criar conversas |
| `GET/POST` | `/api/messages/` | Listar / criar mensagens |
| `GET/POST` | `/api/message-templates/` | Listar / criar templates |
| `GET/PUT/PATCH/DELETE` | `/api/message-templates/{id}/` | Detalhe / editar / deletar template |
| `POST` | `/api/message-templates/{id}/submit/` | Enviar rascunho para aprovação Meta |
| `POST` | `/api/upload-media/` | Upload de arquivo de mídia |
| `GET` | `/api/server-config/` | Configurações públicas (ex: MEDIA_BASE_URL) |
| `GET/POST` | `/api/webhooks/whatsapp/` | Webhook WhatsApp/Meta |
| `GET/POST` | `/api/quick-replies/` | Respostas rápidas |
| `GET/POST` | `/api/channels/` | Provedores de canal |
| `GET` | `/api/plans/` | Planos disponíveis |

---

## Documentação detalhada

| Arquivo | Conteúdo |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Arquitetura geral, fluxos e diagramas |
| [docs/backend.md](docs/backend.md) | Models, configuração Django, seed |
| [docs/api-reference.md](docs/api-reference.md) | Todos os endpoints da API |
| [docs/frontend.md](docs/frontend.md) | Componentes, páginas e serviços |
| [docs/database.md](docs/database.md) | Schema MySQL, tabelas e relacionamentos |
| [docs/whatsapp.md](docs/whatsapp.md) | Configuração do webhook WhatsApp |
| [docs/whatsapp-templates.md](docs/whatsapp-templates.md) | Templates de mensagem — criação, aprovação, vídeo/mídia, vinculação |
| [docs/saas-plans.md](docs/saas-plans.md) | Planos, limites e modelo de assinatura |
| [docs/mobile.md](docs/mobile.md) | Build Android/iOS com Capacitor |
