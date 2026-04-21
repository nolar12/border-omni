# Regras de Negócio — border_omni

- Multi-tenant: cada organização isolada por `org_id`
- Planos: free/pro/enterprise com limites (`max_leads`, `max_agents`, `max_channels`)
- Trial iniciado automaticamente no cadastro
- RAG disponível apenas em planos pro e enterprise
- Leads: qualificação por estados, classificação IA, campo "danger"
- A/B de mídia na primeira mensagem de lead
- Handoff: desativa IA ao assumir manualmente, envia mensagem de transição
- Contrato de venda: preço padrão 3.000, sinal ~30%, dados do filhote via Dog vinculado
- Canil: ninhadas (Litter) e cães (Dog) com mídias e saúde
- Listagem pública de ninhadas: `/api/public/litters/?org_id=` (obrigatório)
