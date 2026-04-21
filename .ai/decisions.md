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
