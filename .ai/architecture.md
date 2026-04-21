# Arquitetura — border_omni

## Estrutura de pastas
```
backend/
├── config/           # settings.py, urls.py
├── api/
│   ├── views/__init__.py    # MONOLÍTICO — todas as views
│   └── serializers/__init__.py
└── apps/
    ├── core/         # Organization, UserProfile, Plan, Subscription, AgentConfig, mídia, galeria
    ├── leads/        # Lead, LeadTag, Note (por lead)
    ├── conversations/ # Conversation, Message, MessageTemplate
    ├── channels/     # ChannelProvider (tokens Meta/WhatsApp)
    ├── quick_replies/ # QuickReplyCategory, QuickReply
    ├── qualifier/    # QualifierEngine, states.py, parsers.py, ai_classifier.py
    ├── rag/          # rag_service.py, embeddings, supabase vetorial
    ├── contracts/    # SaleContract, pdf_utils.py (WeasyPrint)
    ├── notes/        # GenericNote por organização
    └── kennel/       # Litter, Dog, DogMedia, DogHealthRecord, LitterHealthRecord

frontend/
└── src/
    ├── pages/        # Páginas do painel
    └── services/     # Cliente API por domínio
```

## Fluxo principal
- Autenticação JWT → filtra por Organization (multi-tenant)
- Leads chegam via WhatsApp → qualificados por QualifierEngine → classificados por IA
- Contrato de venda: draft → sent → buyer_filled → approved → signed

## Módulos de comunicação
- `api/views/__init__.py` → monolítico, importa models de todos os apps
- Frontend faz chamadas REST com JWT header
- Webhooks Meta/WhatsApp entram sem autenticação JWT

## Convenções
- Todo queryset filtra por `request.user.userprofile.organization`
- JWT com rotação habilitada
- SPA estático servido pelo Django em produção (`frontend/dist`)
- S3 para mídia, local para dev
