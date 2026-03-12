# Teste A/B de Mídia — Border Omni

## Objetivo

Identificar qual mídia (vídeo ou foto) enviada no início da conversa gera maior taxa de conversão de leads qualificados.

Cada novo lead recebe **aleatoriamente** uma das 4 variantes ao iniciar o fluxo. O sistema registra qual variante foi enviada e agrega métricas para comparação.

---

## Variantes

| Variante | Tipo | Variável de ambiente | Arquivo padrão |
|---|---|---|---|
| A | Vídeo (MP4) | `AB_MEDIA_URL_A` | `backend/media/ab_test/variant_a.mp4` |
| B | Imagem (PNG) | `AB_MEDIA_URL_B` | `backend/media/ab_test/variant_b.png` |
| C | Imagem (PNG) | `AB_MEDIA_URL_C` | `backend/media/ab_test/variant_c.png` |
| D | Imagem (PNG) | `AB_MEDIA_URL_D` | `backend/media/ab_test/variant_d.png` |

> Se a URL de uma variante não estiver configurada no `settings.py`, a mídia é omitida e apenas as mensagens de texto são enviadas (o lead ainda é contado para essa variante).

---

## Como configurar as URLs

No `backend/config/settings.py`, as variantes são montadas via variáveis de ambiente:

```python
AB_MEDIA_VARIANTS = {
    'A': {
        'type': 'video',
        'url':  os.getenv('AB_MEDIA_URL_A', ''),
        'caption': MSG_MEDIA_CAPTION,
    },
    'B': {
        'type': 'image',
        'url':  os.getenv('AB_MEDIA_URL_B', ''),
        'caption': MSG_MEDIA_CAPTION,
    },
    'C': {
        'type': 'image',
        'url':  os.getenv('AB_MEDIA_URL_C', ''),
        'caption': MSG_MEDIA_CAPTION,
    },
    'D': {
        'type': 'image',
        'url':  os.getenv('AB_MEDIA_URL_D', ''),
        'caption': MSG_MEDIA_CAPTION,
    },
}
```

### Para desenvolvimento local com ngrok

As URLs devem ser públicas (o WhatsApp Cloud API faz o download da mídia a partir da URL). Em desenvolvimento local, use o ngrok:

```bash
# Exemplo de URLs para o .env ou diretamente no settings:
AB_MEDIA_URL_A=https://SEU-NGROK.ngrok-free.dev/media/ab_test/variant_a.mp4
AB_MEDIA_URL_B=https://SEU-NGROK.ngrok-free.dev/media/ab_test/variant_b.png
AB_MEDIA_URL_C=https://SEU-NGROK.ngrok-free.dev/media/ab_test/variant_c.png
AB_MEDIA_URL_D=https://SEU-NGROK.ngrok-free.dev/media/ab_test/variant_d.png
```

### Para produção

Use URLs estáticas do servidor ou de um CDN/S3.

---

## Como o sorteio funciona

No `engine.py`, ao receber o primeiro estado (`STATE_INITIAL`):

```python
import random

variants = settings.AB_MEDIA_VARIANTS  # dict com 'A', 'B', 'C', 'D'
variant_key = random.choice(list(variants.keys()))
lead.ab_variant = variant_key
lead.save(update_fields=['ab_variant'])

variant = variants[variant_key]
if variant.get('url'):
    replies = [
        {'type': variant['type'], 'url': variant['url'], 'caption': variant['caption']},
        MSG_INTRO,
        MSG_Q1_TIMELINE,
    ]
```

O campo `lead.ab_variant` (char 1) armazena a letra sorteada ('A', 'B', 'C' ou 'D').

---

## Como o backend envia a mídia

A função `_send_whatsapp_media()` em `backend/api/views/__init__.py` é chamada quando o engine retorna um dict de mídia:

```python
def _send_whatsapp_media(phone_number_id, to, media_type, media_url, caption, token):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": media_type,  # "image" ou "video"
        media_type: {
            "link": media_url,
            "caption": caption,
        },
    }
    requests.post(
        f"https://graph.facebook.com/v22.0/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
    )
```

---

## Campo no banco

```python
# leads.Lead
ab_variant = models.CharField(max_length=1, null=True, blank=True)
# Valores possíveis: 'A', 'B', 'C', 'D', ou None (leads anteriores ao A/B test)
```

---

## API — Estatísticas agregadas

### `GET /api/leads/ab_stats/`

Retorna métricas por variante.

**Exemplo de resposta:**
```json
{
  "A": {
    "total": 12,
    "completed": 9,
    "qualified": 7,
    "tier_a": 3,
    "tier_b": 4,
    "tier_c": 2,
    "avg_score": 58.3
  },
  "B": { ... },
  "C": { ... },
  "D": { ... }
}
```

**Campos:**
| Campo | Descrição |
|---|---|
| `total` | Leads que receberam esta variante |
| `completed` | Completaram o fluxo de 4 perguntas |
| `qualified` | Status `QUALIFIED` ou `HANDOFF` |
| `tier_a/b/c` | Contagem por tier |
| `avg_score` | Score médio (0–100) dos leads que completaram |

**Taxas calculadas no frontend:**
| Taxa | Fórmula |
|---|---|
| Taxa de conclusão | `completed / total × 100` |
| Taxa de qualificação | `qualified / total × 100` |
| Taxa Tier A | `tier_a / total × 100` |

---

## Visualização no frontend

Acesse `/ab-test` no painel (link "Teste A/B" na sidebar).

A página exibe:
- Cards com métricas por variante
- Tabela comparativa com as 3 taxas principais
- Barras de progresso visuais
- Destaque da variante com melhor taxa de qualificação

**Arquivo:** `frontend/src/pages/ABTestPage.tsx`

---

## Boas práticas

- Mantenha as URLs de mídia **estáveis** durante o teste para não afetar os dados históricos.
- Aguarde ao menos **30–50 leads por variante** antes de tirar conclusões.
- Ao encerrar um teste, documente os resultados aqui.
- Para desativar uma variante sem remover o código, deixe a URL vazia no `settings.py`.

---

## Resultados (preencher conforme forem coletados)

| Data | Variante vencedora | Taxa qualificação | Observações |
|---|---|---|---|
| — | — | — | Teste em andamento |
