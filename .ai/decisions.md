# Decisões Técnicas — border_omni

| Data | Decisão | Motivo |
|------|---------|--------|
| ~2024 | Django serve SPA em produção | Deploy único |
| ~2024 | Multi-tenant por Organization | Simplicidade, limites em código |
| ~2024 | WhatsApp via API Meta | Menor custo, controle direto |
| ~2024 | RAG com Supabase vetorial | pgvector gerenciado, SDK maduro |
| ~2024 | WeasyPrint para PDF | HTML/CSS para PDF sem dependência externa |
| ~2024 | Capacitor 8 no frontend | Web/mobile com mesmo codebase |
| ~2024 | api/views/__init__.py monolítico | Concentração histórica — dívida técnica conhecida |
| 2026-05 | Fernet para criptografia de tokens em repouso | Padrão AES-128-CBC+HMAC, já disponível via `cryptography`; chave rotacionável sem migração |
| 2026-05 | X-Hub-Signature-256 para validação de webhooks | Exigência Meta para produção; proteção contra payload forjado |
| 2026-05 | Cada tenant usa sua própria WABA (não hospedada) | Isolamento de reputação, compliance e offboarding limpo |
| 2026-05 | Celery + Redis + django-celery-beat | Sync periódico de quality_rating sem polling no request cycle |
| 2026-05 | QualityRatingEvent como log imutável | Auditoria de degradações sem depender de API externa |
| 2026-05 | opted_in + lgpd_consent no modelo Lead | Base legal para envio de campanhas; exigido pelo WhatsApp e LGPD |
| 2026-05 | HOT/WARM/COLD determinado por motor de pontuação (perfil AI) | Substituição do mapping direto de nivel_maturidade; pontuação objetiva baseada em 5 dimensões + tags |
| 2026-05 | LeadProfile como OneToOne separado do Lead | Evita engrossar tabela principal; campos de perfil AI são opcionais e de alta volatilidade |
| 2026-05 | MetaConversionsService isolado com dedup por (lead, event_name, status=sent) | CAPI não pode receber duplicatas; isolamento facilita testes e reuso |
| 2026-05 | Transcrição Whisper em thread daemon (fire-and-forget) | Não bloqueia webhook; falha silenciosa preserva fluxo principal |
| 2026-05 | ad_referral (JSONField raw) + ctwa_clid (CharField) no Lead | Rastreabilidade de origem de anúncio; ctwa_clid é a chave de atribuição da Meta |
| 2026-05 | AgentConfig armazena configuração CAPI por tenant | Configuração por org já estabelecida; evita novo model |
