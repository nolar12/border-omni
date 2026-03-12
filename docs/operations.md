# Operações do Dia-a-Dia — Border Omni

## Iniciar o sistema

### Forma recomendada — Watchdog (tudo automático)

```bash
cd ~/Cathedral/NOLAR/WWW7/border_omni
nohup bash watchdog.sh &
```

O watchdog:
- Inicia o **backend** (porta 9022)
- Inicia o **ngrok** (túnel público para o webhook)
- A cada 20 segundos verifica se os dois estão no ar
- Se qualquer um cair, **reinicia automaticamente**
- Registra tudo em `/tmp/border_omni_watchdog.log`

### Forma manual (3 terminais)

```bash
# Terminal 1 — Backend
cd ~/Cathedral/NOLAR/WWW7/border_omni/backend
source ../venv/bin/activate
python manage.py runserver 0.0.0.0:9022

# Terminal 2 — Frontend
cd ~/Cathedral/NOLAR/WWW7/border_omni/frontend
npm run dev

# Terminal 3 — Ngrok
ngrok http 9022
```

---

## Parar o sistema

```bash
pkill -f watchdog.sh
pkill -f "runserver 0.0.0.0:9022"
pkill -f "ngrok http"
```

---

## Verificar status dos serviços

```bash
# Verifica processos
ps aux | grep -E "runserver|ngrok|watchdog" | grep -v grep

# Testa backend
curl -s -o /dev/null -w "Backend: %{http_code}\n" http://localhost:9022/api/leads/
# Espera: 401 (autenticação necessária) = backend no ar

# Testa ngrok
curl -s http://localhost:4040/api/tunnels | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('Ngrok:', d['tunnels'][0]['public_url'])"

# Testa webhook
curl -s "http://localhost:9022/api/webhooks/whatsapp/\
?hub.mode=subscribe&hub.verify_token=border_omni_wh_secret&hub.challenge=TEST"
# Espera: TEST
```

---

## Acompanhar logs em tempo real

```bash
# Log do backend (requisições, erros, mensagens enviadas)
tail -f /tmp/backend.log

# Log do watchdog (reinícios automáticos)
tail -f /tmp/border_omni_watchdog.log

# Log do ngrok (requisições que chegam do Meta)
curl -s "http://localhost:4040/api/requests/http?limit=10" | python3 -c "
import sys, json
for r in json.load(sys.stdin).get('requests', []):
    print(r.get('started_at','')[:19],
          r.get('request',{}).get('method',''),
          r.get('request',{}).get('uri',''),
          '→', r.get('response',{}).get('status_code',''))
"
```

---

## Acesso ao sistema

| Serviço | URL |
|---|---|
| Frontend | http://localhost:9021 |
| Backend API | http://localhost:9022/api/ |
| Admin Django | http://localhost:9022/admin |
| Painel ngrok | http://localhost:4040 |

**Login padrão:**
- E-mail: `marcello12souza@gmail.com`
- Senha: `Cello1212!`

---

## Resetar senha de usuário

```bash
cd backend && source ../venv/bin/activate
python manage.py shell -c "
from django.contrib.auth.models import User
u = User.objects.get(email='marcello12souza@gmail.com')
u.set_password('NovaSenha123!')
u.save()
print('Senha atualizada')
"
```

---

## Banco de dados

### Ver estado atual
```bash
cd backend && source ../venv/bin/activate
python manage.py shell -c "
from apps.leads.models import Lead
from apps.conversations.models import Conversation, Message
print('Leads:', Lead.objects.count())
print('Conversas:', Conversation.objects.count())
print('Mensagens:', Message.objects.count())
print()
for l in Lead.objects.all().order_by('-id')[:10]:
    print(f'  [{l.id}] {l.full_name or \"(sem nome)\"} | {l.phone} | {l.status} | tier={l.tier} | ai={l.is_ai_active}')
"
```

### Ver mensagens de um lead
```bash
python manage.py shell -c "
from apps.conversations.models import Message
from apps.leads.models import Lead
lead = Lead.objects.get(phone='5521972121012')
for m in Message.objects.filter(conversation__lead=lead).order_by('created_at'):
    print(f'[{m.direction}] {m.created_at.strftime(\"%H:%M\")} | {m.text[:80]}')
"
```

### Resetar conversa de um lead (mantém o lead)
```bash
python manage.py shell -c "
from apps.leads.models import Lead
lead = Lead.objects.get(phone='NUMERO_AQUI')
lead.conversation_state = 'initial'
lead.status = 'NEW'
lead.is_ai_active = True
lead.assigned_to = None
lead.save()
print('Resetado')
"
```

### Atualizar token WhatsApp
```bash
python manage.py shell -c "
from apps.channels.models import ChannelProvider
ch = ChannelProvider.objects.filter(provider='whatsapp').first()
ch.access_token = 'NOVO_TOKEN_AQUI'
ch.save()
print('Token atualizado para:', ch.name)
"
```

---

## Problemas comuns

### Backend não responde (502 no ngrok)
```bash
pkill -f "runserver 0.0.0.0:9022"
cd backend && source ../venv/bin/activate
python manage.py runserver 0.0.0.0:9022 > /tmp/backend.log 2>&1 &
```

### Ngrok URL mudou
O ngrok com conta gratuita fixa o domínio (`nonredeemable-superseriously-keyla.ngrok-free.dev`). Se a URL mudar:
1. Copie a nova URL do painel http://localhost:4040
2. Atualize no Meta Developer Console em **WhatsApp → Configuração → Webhook**
3. Clique em **Verificar e Salvar**

### Lead não recebe mensagem da IA
Verificar se `is_ai_active=True`:
```bash
python manage.py shell -c "
from apps.leads.models import Lead
l = Lead.objects.get(phone='NUMERO')
print('AI ativa:', l.is_ai_active, '| Estado:', l.conversation_state)
"
```

### Mensagem "Arquivo muito grande" ao enviar vídeo
O WhatsApp limita vídeos a 16MB. Comprima o vídeo antes de enviar.

### Frontend mostrando imagens como documentos (📄)
Isso acontece quando o WhatsApp envia a foto como `type: "document"`. O backend corrige pelo MIME type, mas mensagens antigas podem precisar de correção manual:
```bash
python manage.py shell -c "
from apps.conversations.models import Message
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
for msg in Message.objects.filter(text__contains='/media/'):
    lines = msg.text.split('\n')
    if len(lines) >= 2 and lines[0].startswith('📄'):
        ext = '.' + lines[1].rsplit('.', 1)[-1].lower()
        if ext in IMAGE_EXTS:
            msg.text = '🖼️' + msg.text[2:]
            msg.save()
            print('Corrigido:', msg.id)
"
```

---

## Arquivos de mídia recebidos

Localização: `backend/media/whatsapp/`

```bash
# Ver arquivos recebidos
ls -lh backend/media/whatsapp/ | tail -20

# Ver tamanho total
du -sh backend/media/whatsapp/
```

Os arquivos são servidos em: `http://localhost:9022/media/whatsapp/{arquivo}`

---

## Backup do banco

```bash
mysqldump -u root -pcello12 border_leads > backup_$(date +%Y%m%d_%H%M).sql
```

Restaurar:
```bash
mysql -u root -pcello12 border_leads < backup_20260311_1400.sql
```
