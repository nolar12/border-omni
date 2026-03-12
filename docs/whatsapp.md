# WhatsApp Cloud API — Border Omni

## Canal configurado

| Campo | Valor |
|---|---|
| App ID | `1260435322688998` |
| Phone Number ID | `1040197165841892` |
| Business Account ID (WABA) | `2133277890774145` |
| Webhook Verify Token | `border_omni_wh_secret` |
| Organização | Border Collie Sul |
| System User | `borderomniapi` |
| Token type | System User Token (permanente) |

---

## Configuração no Meta for Developers

1. Acesse: https://developers.facebook.com/apps/1260435322688998
2. Vá em **WhatsApp → Configuração**
3. Em **Webhook**, clique **Editar**:
   - **URL de Callback**: `https://SEU_DOMINIO/api/webhooks/whatsapp/`
   - **Token de Verificação**: `border_omni_wh_secret`
4. Assine o evento: **messages**
5. Clique **Verificar e Salvar**

---

## Desenvolvimento local com ngrok

O ngrok cria um túnel HTTPS público apontando para `localhost:9022`.

### Iniciar (forma automática — recomendado)
```bash
cd ~/Cathedral/NOLAR/WWW7/border_omni
nohup bash watchdog.sh &
```
O watchdog inicia o backend **e** o ngrok automaticamente, e reinicia se qualquer um cair.

### Iniciar manualmente
```bash
ngrok http 9022
```

### URL atual (ngrok gratuito com domínio fixo)
```
https://nonredeemable-superseriously-keyla.ngrok-free.dev
```

### Webhook completo para configurar no Meta
```
https://nonredeemable-superseriously-keyla.ngrok-free.dev/api/webhooks/whatsapp/
```

### Testar se o webhook responde
```bash
curl "https://nonredeemable-superseriously-keyla.ngrok-free.dev/api/webhooks/whatsapp/\
?hub.mode=subscribe\
&hub.verify_token=border_omni_wh_secret\
&hub.challenge=1234567890"
# Deve retornar: 1234567890
```

---

## Subscription do App à WABA

Para o Meta enviar eventos de mensagens ao webhook, o App precisa estar inscrito na WABA:

```bash
curl -X POST \
  "https://graph.facebook.com/v22.0/2133277890774145/subscribed_apps" \
  -H "Authorization: Bearer SEU_TOKEN_AQUI"
```

Verificar inscrição atual:
```bash
curl "https://graph.facebook.com/v22.0/2133277890774145/subscribed_apps" \
  -H "Authorization: Bearer SEU_TOKEN_AQUI"
```

---

## Envio de mídia no fluxo automatizado (A/B Test)

O QualifierEngine envia mídia (vídeo ou imagem) como **primeiro passo** do fluxo, antes das mensagens de texto. O backend chama `_send_whatsapp_media()` em `api/views/__init__.py`.

```bash
# Enviar imagem via URL pública
curl -X POST "https://graph.facebook.com/v22.0/1040197165841892/messages" \
  -H "Authorization: Bearer SEU_TOKEN_AQUI" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "5521972121012",
    "type": "image",
    "image": {
      "link": "https://SEU_DOMINIO/media/ab_test/variant_b.png",
      "caption": "Legenda da imagem aqui"
    }
  }'

# Enviar vídeo via URL pública
curl -X POST "https://graph.facebook.com/v22.0/1040197165841892/messages" \
  -H "Authorization: Bearer SEU_TOKEN_AQUI" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "5521972121012",
    "type": "video",
    "video": {
      "link": "https://SEU_DOMINIO/media/ab_test/variant_a.mp4",
      "caption": "Legenda do vídeo aqui"
    }
  }'
```

> **Atenção:** A URL da mídia deve ser **pública e acessível pelo Meta**. Em desenvolvimento local, use o ngrok para expor o servidor.

---

## Envio de mensagem de texto via API

```bash
curl -X POST "https://graph.facebook.com/v22.0/1040197165841892/messages" \
  -H "Authorization: Bearer SEU_TOKEN_AQUI" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "5521972121012",
    "type": "text",
    "text": { "body": "Olá! Mensagem de teste." }
  }'
```

---

## Formatos de webhook recebidos

### Mensagem de texto
```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "changes": [{
      "value": {
        "metadata": { "phone_number_id": "1040197165841892" },
        "contacts": [{ "profile": { "name": "Nome do Cliente" } }],
        "messages": [{
          "from": "5521972121012",
          "type": "text",
          "text": { "body": "Oi quero um filhote" }
        }]
      }
    }]
  }]
}
```

### Imagem recebida
```json
{
  "messages": [{
    "type": "image",
    "image": {
      "id": "MEDIA_ID",
      "mime_type": "image/jpeg",
      "caption": "legenda opcional"
    }
  }]
}
```

### Documento recebido
```json
{
  "messages": [{
    "type": "document",
    "document": {
      "id": "MEDIA_ID",
      "mime_type": "application/pdf",
      "filename": "contrato.pdf"
    }
  }]
}
```

> **Atenção:** O WhatsApp às vezes envia imagens como `type: "document"` quando o usuário encaminha como arquivo. O backend detecta o tipo real pelo `mime_type` e pela extensão do `filename`.

---

## Tipos de mídia suportados

| Tipo | Extensões | Limite Meta |
|---|---|---|
| Imagem | jpg, jpeg, png, gif, webp | 5 MB |
| Vídeo | mp4, mov, 3gp | 16 MB |
| Áudio | mp3, ogg, aac, m4a, opus | 16 MB |
| Documento | pdf, doc, xls, ppt, txt | 100 MB |

---

## Como o backend processa mídia recebida

1. Webhook chega com `type: "image"` (ou document/video/audio)
2. Backend chama `GET https://graph.facebook.com/v22.0/{media_id}` → obtém URL temporária
3. Backend baixa o arquivo usando o access_token do canal
4. Arquivo salvo em `backend/media/whatsapp/{uuid}_{filename}`
5. Mensagem salva no banco com texto `🖼️ legenda\n/media/whatsapp/arquivo.jpg`
6. Frontend converte `/media/...` para `http://localhost:9022/media/...` e exibe

---

## Token de acesso

O token deve ser de um **System User** com permissões:
- `whatsapp_business_messaging`
- `whatsapp_business_management`

Tokens de usuário pessoal expiram em 1–60 dias. Tokens de System User são **permanentes**.

### Atualizar token no banco
```bash
cd backend && source ../venv/bin/activate
python manage.py shell -c "
from apps.channels.models import ChannelProvider
ch = ChannelProvider.objects.filter(provider='whatsapp').first()
ch.access_token = 'SEU_NOVO_TOKEN'
ch.save()
print('Token atualizado')
"
```

---

## Simulador interno (desenvolvimento)

Para testar sem depender do WhatsApp real:

```bash
# Via curl
curl -X POST http://localhost:9022/api/webhooks/whatsapp/ \
  -H "Content-Type: application/json" \
  -d '{
    "from_phone": "+5551999888777",
    "text": "oi quero um filhote",
    "provider": "WHATSAPP",
    "organization_key": "SUA_API_KEY"
  }'
```

Ou acesse `http://localhost:9021/simulator` no frontend.

---

## Limitações do Meta em modo de desenvolvimento

- Apenas números adicionados à lista de teste podem receber mensagens
- Para iniciar conversa: o negócio deve enviar o primeiro template, ou o cliente deve iniciar
- Números com status "pendente" não podem receber mensagens de texto livre
- A mensagem de "convite por SMS" aparece quando o número ainda não está registrado no WhatsApp Business
