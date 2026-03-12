# Envio e Recebimento de Mídia — Border Omni

## Visão Geral

O sistema suporta mídia bidirecional via WhatsApp:

| Direção | Quem envia | Como funciona |
|---|---|---|
| **Recebimento** (IN) | Cliente → Sistema | Webhook → download automático → exibição no chat |
| **Envio** (OUT) | Agente → Cliente | Upload via chat → Meta API → WhatsApp do cliente |

---

## Recebimento de Mídia (Cliente → Sistema)

### Fluxo técnico

```
1. Cliente envia imagem/vídeo/doc no WhatsApp
2. Meta envia webhook POST /api/webhooks/whatsapp/
3. Backend detecta msg_type = "image" | "video" | "document" | "audio"
4. Chama _handle_incoming_media()
5. GET https://graph.facebook.com/v22.0/{media_id} → URL temporária
6. Baixa o arquivo com Bearer token do canal
7. Salva em backend/media/whatsapp/{uuid8}_{filename}
8. Salva Message com text = "🖼️ legenda\n/media/whatsapp/arquivo.jpg"
9. Frontend renderiza: imagem/player/link conforme tipo
```

### Detecção de tipo real

O WhatsApp às vezes envia **fotos como `type: "document"`** quando o usuário encaminha como arquivo. O backend resolve isso verificando:

1. `mime_type` da mensagem (ex: `image/jpeg` → trata como imagem)
2. Extensão do `filename` (ex: `foto.jpg` → trata como imagem)

```python
# Lógica em _handle_incoming_media()
if msg_type == 'document' and mime_type.startswith('image/'):
    effective_type = 'image'  # Trata como imagem
```

### Ícones por tipo

| Tipo | Ícone | Como exibido no chat |
|---|---|---|
| image | 🖼️ | Miniatura clicável → abre em tamanho original |
| video | 🎥 | Player de vídeo embutido com controles |
| audio | 🎵 | Player de áudio |
| document/pdf | 📄 | Card clicável com nome e "Abrir ↗" |

### Formato salvo no banco (campo `text` da mensagem)

```
🖼️ legenda opcional
/media/whatsapp/21496e88_IMG_5513.jpg
```

O frontend detecta este padrão e renderiza adequadamente.

### Como o frontend exibe

```typescript
// MessageContent component (LeadsPage.tsx)
// Linha 1: ícone + legenda
// Linha 2: URL local (/media/...) ou externa (https://...)

const isMediaUrl = (s: string) =>
  s.startsWith('https://') || s.startsWith('http://') || s.startsWith('/media/');

const toAbsolute = (s: string) =>
  s.startsWith('/media/') ? `http://localhost:9022${s}` : s;
```

---

## Envio de Mídia (Agente → Cliente)

### Como usar no chat

1. Com a IA desligada (botão "Assumir" clicado), abra a conversa
2. Clique no ícone de **clipe 📎** na barra inferior
3. Selecione o arquivo no seu computador
4. Um preview aparece com nome e tamanho
5. Adicione uma **legenda** opcional
6. Clique no botão **Enviar** (azul)

### Limites de tamanho

| Tipo | Limite |
|---|---|
| Imagem (jpg, png, gif, webp) | **5 MB** |
| Vídeo (mp4, mov, 3gp) | **16 MB** |
| Áudio (mp3, ogg, aac) | **16 MB** |
| Documento (pdf, doc, xls...) | **100 MB** |

O frontend bloqueia o arquivo antes do envio se exceder o limite, mostrando mensagem de erro.

### Fluxo técnico (send_file)

```
1. Agente seleciona arquivo no chat
2. Frontend: POST /api/leads/{id}/send_file/ (multipart/form-data)
3. Backend:
   a. Detecta mime_type (imagem vs documento)
   b. POST https://graph.facebook.com/v22.0/{phone_number_id}/media
      com o arquivo → recebe media_id
   c. POST https://graph.facebook.com/v22.0/{phone_number_id}/messages
      com { type: "image"|"document", id: media_id }
   d. Salva Message OUT com texto "📎 nome_do_arquivo"
4. Cliente recebe o arquivo no WhatsApp
```

### Endpoint da API

```
POST /api/leads/{id}/send_file/
Content-Type: multipart/form-data

Campos:
  file     : arquivo (obrigatório)
  caption  : legenda (opcional)
```

### Erros comuns

| Erro | Causa | Solução |
|---|---|---|
| "Arquivo muito grande" | Excede limite do Meta | Comprimir o arquivo |
| 502 Bad Gateway | Erro na Meta API | Verificar token e phone_number_id |
| Arquivo não aparece no WhatsApp | mime_type incorreto | Meta às vezes rejeita mime_type incomum |

---

## Storage local

Os arquivos recebidos dos clientes são salvos em:

```
backend/media/whatsapp/
├── 21496e88_IMG_5513.jpg
├── 7eab4c01_fotos_batch2-64.jpg
├── 2f73dbb5_procuracao_marcello_tjrj.pdf
└── ...
```

**Nomeação:** `{8 chars uuid hex}_{filename original}`

**Servidos em:** `http://localhost:9022/media/whatsapp/{arquivo}`

### Em produção (AWS)

Para produção, considere usar **S3** em vez do disco local:

```python
# settings.py (produção)
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_STORAGE_BUCKET_NAME = 'border-omni-media'
AWS_S3_REGION_NAME = 'sa-east-1'
MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/'
```

---

## Tipos MIME suportados pelo WhatsApp

### Imagens
- `image/jpeg` → `.jpg`
- `image/png` → `.png`
- `image/gif` → `.gif`
- `image/webp` → `.webp`

### Vídeos
- `video/mp4` → `.mp4`
- `video/quicktime` → `.mov`
- `video/3gpp` → `.3gp`

### Áudio
- `audio/mpeg` → `.mp3`
- `audio/ogg` → `.ogg`
- `audio/aac` → `.aac`
- `audio/mp4` → `.m4a`

### Documentos
- `application/pdf` → `.pdf`
- `application/msword` → `.doc`
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document` → `.docx`
- `application/vnd.ms-excel` → `.xls`
- `text/plain` → `.txt`
