# Planos SaaS — Border Omni

## Planos disponíveis

| Plano | Preço/mês | Leads | Agentes | Canais | Handoff |
|---|---|---|---|---|---|
| **Free** | R$ 0 | 50 | 1 | 1 | — |
| **Pro** | R$ 197 | 500 | 5 | 3 | ✓ |
| **Enterprise** | R$ 597 | Ilimitado | Ilimitado | 10 | ✓ |

---

## Model de Assinatura

Cada `Organization` tem exatamente uma `Subscription` com status:

| Status | Descrição |
|---|---|
| `trial` | Período de avaliação (padrão ao criar conta) |
| `active` | Assinatura ativa e paga |
| `expired` | Período vencido sem renovação |
| `cancelled` | Cancelada pelo usuário |

---

## Upgrade de plano

Via API:
```bash
curl -X POST http://localhost:9022/api/subscription/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"plan": "pro"}'
```

Via painel: `http://localhost:9021/plans`

---

## Limites (TODO: implementar middleware)

Os limites de plano estão definidos nos models `Plan`, mas o enforcement (bloqueio quando o limite é atingido) ainda precisa ser implementado como middleware DRF:

```python
# backend/api/views/__init__.py — adicionar verificação antes de create
class LeadViewSet(viewsets.ReadOnlyModelViewSet):
    def create(self, request, *args, **kwargs):
        org = _get_org(request.user)
        plan = org.subscription.plan
        if Lead.objects.filter(organization=org).count() >= plan.max_leads:
            return Response({'detail': 'Limite de leads do plano atingido.'}, status=429)
        return super().create(request, *args, **kwargs)
```

---

## Seed dos planos

Os planos são criados automaticamente pelo comando de seed:

```bash
python manage.py seed
```

Para atualizar preços/limites diretamente:

```bash
python manage.py shell -c "
from apps.core.models import Plan
Plan.objects.filter(name='pro').update(price_monthly=197, max_leads=500)
"
```
