import { NavLink } from 'react-router-dom';
import { authService } from '../services/auth';

interface NavItem {
  to: string;
  label: string;
  soon?: boolean;
  icon: React.ReactNode;
}

const SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Principal',
    items: [
      {
        to: '/dashboard',
        label: 'Dashboard',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
            <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
          </svg>
        ),
      },
      {
        to: '/leads',
        label: 'Leads & Chats',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        ),
      },
      {
        to: '/simulator',
        label: 'Simulador',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <polygon points="5 3 19 12 5 21 5 3"/>
          </svg>
        ),
      },
    ],
  },
  {
    title: 'Comunicação',
    items: [
      {
        to: '/campanhas',
        label: 'Campanhas',
        soon: true,
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
          </svg>
        ),
      },
      {
        to: '/automacoes',
        label: 'Automações',
        soon: true,
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <circle cx="12" cy="12" r="3"/>
            <path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/>
          </svg>
        ),
      },
      {
        to: '/relatorios',
        label: 'Relatórios',
        soon: true,
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <line x1="18" y1="20" x2="18" y2="10"/>
            <line x1="12" y1="20" x2="12" y2="4"/>
            <line x1="6" y1="20" x2="6" y2="14"/>
          </svg>
        ),
      },
    ],
  },
  {
    title: 'Configurações',
    items: [
      {
        to: '/channels',
        label: 'Canais',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.99 12 19.79 19.79 0 0 1 1.98 3.38 2 2 0 0 1 3.95 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>
          </svg>
        ),
      },
      {
        to: '/equipe',
        label: 'Equipe',
        soon: true,
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        ),
      },
      {
        to: '/plans',
        label: 'Planos',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <line x1="12" y1="1" x2="12" y2="23"/>
            <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
          </svg>
        ),
      },
      {
        to: '/configuracoes',
        label: 'Configurações',
        soon: true,
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        ),
      },
    ],
  },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: Props) {
  const user = authService.getCurrentUser();

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div className="fixed inset-0 z-40 bg-black/40 md:hidden" onClick={onClose} />
      )}

      <aside
        className={`fixed top-0 left-0 h-full z-50 flex flex-col transition-transform duration-300
          md:translate-x-0 md:z-auto
          ${open ? 'translate-x-0' : '-translate-x-full'}`}
        style={{ width: 240, background: '#1e2a3a' }}
      >
        {/* Logo / Brand */}
        <div className="flex items-center gap-3 px-4 py-4 border-b border-white/10">
          <div className="w-8 h-8 rounded-xl bg-blue-500 flex items-center justify-center flex-shrink-0 shadow-lg">
            <span className="text-white font-bold text-sm">B</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-white font-bold text-sm leading-tight">Border Omni</p>
            <p className="text-slate-400 text-xs truncate">{user?.organization_name ?? 'SaaS'}</p>
          </div>
          <button className="text-slate-400 hover:text-white md:hidden flex-shrink-0" onClick={onClose}>
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {/* Navigation sections */}
        <nav className="flex-1 px-3 py-3 space-y-5 overflow-y-auto">
          {SECTIONS.map(section => (
            <div key={section.title}>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 px-2 mb-1.5">
                {section.title}
              </p>
              <div className="space-y-0.5">
                {section.items.map(item => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    onClick={onClose}
                    className={({ isActive }) =>
                      `sidebar-link ${isActive ? 'active' : ''} ${item.soon ? 'opacity-60' : ''}`
                    }
                  >
                    <span className="w-4 h-4 flex-shrink-0">{item.icon}</span>
                    <span className="flex-1">{item.label}</span>
                    {item.soon && (
                      <span className="text-[9px] font-semibold uppercase tracking-wide text-slate-500 bg-slate-700 px-1.5 py-0.5 rounded-full">
                        em breve
                      </span>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* User footer */}
        <div className="p-3 border-t border-white/10">
          <div className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg">
            <div className="w-7 h-7 rounded-full bg-blue-500 flex items-center justify-center flex-shrink-0">
              <span className="text-white text-xs font-bold">
                {user?.first_name?.[0]?.toUpperCase() ?? 'U'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-xs font-medium truncate">
                {user?.first_name} {user?.last_name}
              </p>
              <p className="text-slate-400 text-xs capitalize">{user?.plan_name}</p>
            </div>
            <button
              onClick={() => authService.logout()}
              title="Sair"
              className="text-slate-400 hover:text-red-400 transition-colors flex-shrink-0"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
