# Configuração WhatsApp — Border Omni

## Canal registrado

| Campo | Valor |
|---|---|
| App ID | `1260435322688998` |
| Phone Number ID | `1040197165841892` |
| Business Account ID | `2133277890774145` |
| Webhook Token | `border_omni_wh_secret` |
| Organização | Border Collie Sul |
| Status | pending (verificação pendente) |

---

## URL do Webhook

Para receber mensagens do WhatsApp, o Meta precisa de uma URL pública HTTPS apontando para:

```
https://SEU_DOMINIO/api/webhooks/whatsapp/
```

Em desenvolvimento, use um túnel HTTPS como [ngrok](https://ngrok.com):

```bash
ngrok http 9022
# Copia a URL https://xxxx.ngrok.io
# Configura como: https://xxxx.ngrok.io/api/webhooks/whatsapp/
```

---

## Configuração no Meta for Developers

1. Acesse: https://developers.facebook.com/apps/1260435322688998
2. Vá em **WhatsApp → Configuração**
3. Em **Webhook**, clique **Editar**:
   - **URL de Callback**: `https://SEU_DOMINIO/api/webhooks/whatsapp/`
   - **Token de Verificação**: `border_omni_wh_secret`
4. Assine os eventos: **messages**
5. Clique **Verificar e Salvar**

---

## Verificação do Webhook (GET)

O Meta faz uma requisição GET para verificar o webhook:

```
GET /api/webhooks/whatsapp/?hub.mode=subscribe&hub.verify_token=border_omni_wh_secret&hub.challenge=12345
```

O backend retorna o `hub.challenge` se o token bater com algum `ChannelProvider`.

---

## Formato da mensagem inbound (simulado)

O simulador de webhook pode ser acessado em `http://localhost:9021/simulator` ou via curl:

```bash
curl -X POST http://localhost:9022/api/webhooks/whatsapp/ \
  -H "Content-Type: application/json" \
  -H "X-ORG-KEY: efc0e41b-7bec-4cbc-9f29-3c4b08e8a168" \
  -d '{
    "from_phone": "+5551999888777",
    "text": "oi quero um filhote",
    "provider": "WHATSAPP"
  }'
```

> A **API Key** da organização aparece na saída do `./start.sh start` ou no comando:
> ```bash
> cd backend && source ../venv/bin/activate && python manage.py shell -c "from apps.core.models import Organization; print(Organization.objects.first().api_key)"
> ```

---

## Mensagem real do Meta (formato oficial)

Para integração real com a WhatsApp Business API, o formato recebido é diferente. O webhook precisará ser adaptado para parsear o payload oficial:

```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "BUSINESS_ACCOUNT_ID",
    "changes": [{
      "value": {
        "messaging_product": "whatsapp",
        "messages": [{
          "from": "5551999888777",
          "id": "wamid.xxx",
          "text": { "body": "oi quero um filhote" },
          "type": "text",
          "timestamp": "1234567890"
        }]
      },
      "field": "messages"
    }]
  }]
}
```

**TODO:** Adaptar `WhatsAppWebhookView.post()` para processar o payload oficial do Meta além do formato simplificado atual.

---

## Envio de mensagens (API oficial)

Para enviar mensagens de volta ao usuário via API oficial:

```python
import requests

def send_whatsapp_message(phone_number_id, access_token, to, text):
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    return requests.post(url, json=payload, headers=headers)
```

**TODO:** Integrar este envio no `WhatsAppWebhookView` e no `send_message` endpoint da API.
