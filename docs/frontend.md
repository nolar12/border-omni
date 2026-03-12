# Frontend — Border Omni

## Stack

- **React 18** + **TypeScript**
- **Vite 7** — build tool
- **Tailwind CSS v4** — utilitários CSS
- **DaisyUI v5** — componentes UI
- **React Router DOM v6** — roteamento
- **Axios** — cliente HTTP com interceptors JWT
- **Capacitor** — compilação nativa Android/iOS

---

## Estrutura de pastas

```
frontend/src/
├── types/
│   └── index.ts           # Todas as interfaces TypeScript
├── services/
│   ├── api.ts             # Axios base com JWT interceptor
│   ├── auth.ts            # Login, register, logout, getCurrentUser
│   ├── leads.ts           # CRUD leads + actions
│   ├── channels.ts        # CRUD canais
│   ├── quickReplies.ts    # Templates + resolveVariables
│   ├── plans.ts           # Planos e assinatura
│   └── simulator.ts       # Simulador de webhook
├── components/
│   ├── Layout.tsx              # Layout raiz com sidebar + topbar + footer
│   ├── Sidebar.tsx             # Menu lateral (desktop) + overlay (mobile)
│   ├── Topbar.tsx              # Logo, notificações, dropdown de usuário
│   ├── BottomNav.tsx           # Navegação inferior (mobile)
│   ├── Footer.tsx              # Footer mínimo copyright + versão
│   ├── PrivateRoute.tsx        # Proteção de rotas autenticadas
│   ├── AIStatusBadge.tsx       # Badge IA ativa / Nome do agente
│   ├── TierBadge.tsx           # Badge A/B/C colorido
│   ├── ClassificationBadge.tsx # Badge HOT🔥 / WARM🟡 / COLD❄️
│   ├── StatusBadge.tsx         # Badge status do lead
│   └── QuickReplyDrawer.tsx    # Bottom sheet de respostas rápidas
└── pages/
    ├── Login.tsx            # Tela de login
    ├── Dashboard.tsx        # Cards de stats + tabela de leads recentes
    ├── LeadsPage.tsx        # Layout 3 colunas omnichannel
    ├── ABTestPage.tsx       # Visualização de resultados do A/B test
    ├── Simulator.tsx        # Simulador de webhook WhatsApp
    ├── Channels.tsx         # CRUD de canais
    └── Plans.tsx            # Planos SaaS e assinatura atual
```

---

## Layout

### Desktop (md+)
```
┌──────────────────────────────────────────────────┐
│                    TOPBAR                         │
├────────────┬─────────────────────────────────────┤
│            │                                     │
│  SIDEBAR   │           CONTENT                   │
│  (240px)   │                                     │
│            │                                     │
├────────────┴─────────────────────────────────────┤
│                    FOOTER                         │
└──────────────────────────────────────────────────┘
```

### Mobile
```
┌──────────────────────────┐
│         TOPBAR           │  ← hamburger abre sidebar overlay
├──────────────────────────┤
│                          │
│         CONTENT          │
│                          │
├──────────────────────────┤
│       BOTTOM NAV         │  ← 5 tabs fixos
└──────────────────────────┘
```

---

## Página de Leads — Layout 3 Colunas

```
┌────────────┬──────────────────┬──────────────────────┐
│  SIDEBAR   │  LISTA DE LEADS  │  CHAT / DETALHE      │
│            │  ┌─────────────┐ │  ┌──────────────────┐│
│            │  │ busca       │ │  │ header + badges  ││
│            │  ├─────────────┤ │  ├──────────────────┤│
│            │  │ Lead A (A)  │ │  │ tabs: Chat/Perfil ││
│            │  │ Lead B (B)  │ │  │ /Notas           ││
│            │  │ Lead C (C)  │ │  ├──────────────────┤│
│            │  │ ...         │ │  │ mensagens        ││
│            │  └─────────────┘ │  ├──────────────────┤│
│            │                  │  │ input + enviar   ││
└────────────┴──────────────────┴──────────────────────┘
```

**Mobile:** lista ocupa toda a tela → tap num lead → chat ocupa toda a tela → botão voltar.

---

## Roteamento

```typescript
/login              → Login (pública)
/dashboard          → Dashboard
/leads              → LeadsPage (lista vazia selecionada)
/leads/:id          → LeadsPage (lead selecionado no chat)
/ab-test            → ABTestPage (métricas comparativas A/B/C/D)
/simulator          → Simulator
/channels           → Channels
/plans              → Plans
/campanhas          → ComingSoon
/automacoes         → ComingSoon
/relatorios         → ComingSoon
/equipe             → ComingSoon
/configuracoes      → ComingSoon
```

---

## Serviço de Auth (services/auth.ts)

```typescript
authService.login(email, password)    // → salva tokens no localStorage
authService.logout()                  // → limpa localStorage, redireciona /login
authService.getCurrentUser()          // → User | null (do localStorage)
authService.isAuthenticated()         // → boolean
authService.me()                      // → User (da API, atualiza localStorage)
```

---

## Interceptor JWT (services/api.ts)

- Adiciona `Authorization: Bearer <token>` automaticamente
- Em caso de 401, tenta refresh automático
- Se refresh falhar, faz logout e redireciona para `/login`

---

## Variáveis de ambiente

Crie `frontend/.env.local` para customizar:

```env
VITE_API_BASE_URL=http://localhost:9022
```

O proxy do Vite já aponta `/api` para `http://localhost:9022` via `vite.config.ts`.

---

## Scripts

```bash
npm run dev          # desenvolvimento (porta 9021 via start.sh)
npm run build        # build de produção em dist/
npm run preview      # preview do build
npm run lint         # ESLint
```

---

## Temas (DaisyUI)

O tema padrão é `light` do DaisyUI. O sidebar usa estilos customizados com fundo `#1e2a3a` (dark navy) independente do tema.

Para customizar o tema, edite `src/index.css`:
```css
[data-theme="border_omni"] {
  --color-primary: oklch(55.18% 0.215 263.13);
  /* ... */
}
```
