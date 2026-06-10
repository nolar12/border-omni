# Arquitetura — border_omni

## Estrutura de pastas
```
backend/
├── config/
│   ├── settings.py   # Celery, Fernet key, Meta OAuth vars
│   ├── celery.py     # App Celery configurado
│   └── __init__.py   # Expõe celery_app para autodiscover
├── api/
│   ├── views/__init__.py    # MONOLÍTICO — todas as views
│   └── serializers/__init__.py
└── apps/
    ├── core/         # Organization, UserProfile (inclui dados de certificado do canil), Plan, Subscription, AgentConfig, mídia, galeria
    ├── leads/        # Lead (opted_in, lgpd_consent, ad_referral, ctwa_clid), LeadTag, Note
    │                 # LeadProfile (OneToOne: intencao_uso, potencial_compra, urgencia, tags_automaticas...)
    ├── conversations/ # Conversation, Message (+ transcription), MessageTemplate
    ├── channels/
    │   ├── models.py          # ChannelProvider, QualityRatingEvent, MetaConversionEvent
    │   ├── encrypted_fields.py # EncryptedTextField, EncryptedCharField (Fernet)
    │   ├── tasks.py           # sync_whatsapp_quality_ratings (Celery, 6h)
    │   ├── meta_conversions_service.py # MetaConversionsService — CAPI feedback loop
    │   ├── views_meta_oauth.py # MetaOAuthDiscoverView, MetaOAuthFinalizeView
    │   └── meta_client.py     # Helpers Graph API
    ├── quick_replies/ # QuickReplyCategory, QuickReply
    ├── qualifier/    # QualifierEngine, states.py, parsers.py, ai_classifier.py, transcriber.py
    ├── rag/          # rag_service.py, embeddings, supabase vetorial
    ├── contracts/    # SaleContract, pdf_utils.py (WeasyPrint)
    ├── notes/        # GenericNote por organização
    └── kennel/       # Litter, Dog, DogMedia, DogHealthRecord, LitterHealthRecord, templates PDF de registro

frontend/
└── src/
    ├── pages/
    │   ├── Channels.tsx      # quality badge, sync manual, histórico, banner RED, auto webhook_url
    │   ├── CampaignsPage.tsx # filtro opted_in
    │   └── LeadsPage.tsx     # badge janela 24h (existia), opted_in
    └── services/
        └── channels.ts       # syncQuality(), getQualityHistory()
```

## Fluxo principal
- Autenticação JWT → filtra por Organization (multi-tenant)
- Leads chegam via WhatsApp → qualificados por QualifierEngine → classificados por IA
- Contrato de venda: draft → sent → buyer_filled → approved → signed

## Módulos de comunicação
- `api/views/__init__.py` → monolítico, importa models de todos os apps
- Frontend faz chamadas REST com JWT header
- Webhooks Meta/WhatsApp entram sem autenticação JWT

## Segurança de canais
- `access_token` e `app_secret` cifrados em repouso com Fernet (`EncryptedTextField/EncryptedCharField`)
- Ativado por `FIELD_ENCRYPTION_KEY` no `.env`; sem a chave armazena em plain text (compatibilidade dev)
- Webhooks reais da Meta validados com `X-Hub-Signature-256` (HMAC-SHA256 com `META_APP_SECRET`)
- Simulador interno não valida assinatura (não envia header)

## Janela de 24h WhatsApp
- Backend (`send_message`) bloqueia texto livre se janela fechada → erro 400
- Frontend (`LeadsPage.tsx`): badge visual + banner de aviso na UI
- Templates podem ser enviados fora da janela sem restrição

## Quality Rating Monitoring
- `sync_whatsapp_quality_ratings` task Celery roda a cada 6h automaticamente
- Cria `QualityRatingEvent` a cada mudança; loga `ERROR` para RED, `WARNING` para YELLOW
- `POST /api/channels/{id}/sync_quality/` — sync manual imediato
- `GET /api/channels/{id}/quality_history/` — últimos 30 eventos
- UI: badge colorido, botão Sync, histórico colapsável, banner vermelho se RED

## Meta OAuth (Business Integration System User Token)
- Cada tenant autoriza via Facebook Login for Business com seu próprio Business Portfolio
- `MetaOAuthDiscoverView` troca code por SUAT e lista assets do cliente
- `MetaOAuthFinalizeView` salva ChannelProvider e registra webhooks via API
- App Meta central (FilhoteFacil) é apenas orquestrador — nunca hospeda WABAs de clientes

## Registro oficial de ninhada (PDF AcroForm)
- Novo fluxo no canil para preencher PDF oficial com dados da ninhada, pais e filhotes.
- Fluxo simplificado: usa template único fixo (`LITTER_REGISTRATION_TEMPLATE_PATH`) sem upload/lista de templates na tela.
- Modelos novos:
  - `LitterDocumentTemplate`: armazena arquivo PDF, `field_mapping`, `required_fields` e `field_inventory`.
  - `LitterRegistrationDocument`: histórico de emissões com `extra_data`, status e PDF gerado.
  - `Litter.registration_data`: rascunho persistente dos dados extras do formulário por ninhada.
- Serviço `apps.kennel.pdf_utils`:
  - extrai inventário de campos AcroForm (`extract_pdf_fields`);
  - aplica auto-mapeamento padrão CBKC (`build_cbkc_default_mapping`) para os campos conhecidos do formulário;
  - monta contexto (`build_litter_registration_context`);
  - resolve mapeamentos (`resolve_mapping`);
  - preenche PDF (`fill_pdf_template`) usando `pypdf`.
- Endpoints autenticados:
  - CRUD `litter-document-templates` (com action `inspect_fields`);
  - `POST /api/litters/{id}/generate_registration_pdf/` para gerar/download do registro.
  - `GET/POST /api/litters/{id}/registration_data/` para carregar/salvar rascunho antes da geração.
- Frontend (`LittersPage`):
  - uso direto de template oficial fixo configurado no backend;
  - captura de `extra_data` por ninhada/pais/filhotes;
  - geração/download do PDF final.

## Convenções
- Todo queryset filtra por `request.user.userprofile.organization`
- JWT com rotação habilitada
- SPA estático servido pelo Django em produção (`frontend/dist`)
- S3 para mídia, local para dev
