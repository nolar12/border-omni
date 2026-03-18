import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '../services/auth';

interface Props {
  onMenuClick: () => void;
}

// Mock notifications — substituir por dados reais quando disponível
const MOCK_NOTIFICATIONS = [
  { id: 1, text: 'Novo lead Tier A: +5551999000123', time: '2min', unread: true },
  { id: 2, text: 'Lead João Silva assumido por Marcelo', time: '15min', unread: true },
  { id: 3, text: 'Qualificação concluída: 3 novos leads', time: '1h', unread: false },
];

export default function Topbar({ onMenuClick }: Props) {
  const [showNotif, setShowNotif] = useState(false);
  const [showUser, setShowUser] = useState(false);
  const user = authService.getCurrentUser();
  const navigate = useNavigate();
  const unreadCount = MOCK_NOTIFICATIONS.filter(n => n.unread).length;

  const initials = `${user?.first_name?.[0] ?? ''}${user?.last_name?.[0] ?? ''}`.toUpperCase() || 'U';

  function closeAll() {
    setShowNotif(false);
    setShowUser(false);
  }

  return (
    <>
      {/* Backdrop for dropdowns */}
      {(showNotif || showUser) && (
        <div className="fixed inset-0 z-30" onClick={closeAll} />
      )}

      <header className="sticky top-0 z-40 bg-white border-b border-gray-200 flex items-center gap-3 px-4 h-16 flex-shrink-0">
        {/* Hamburger (mobile) */}
        <button
          onClick={onMenuClick}
          className="md:hidden flex items-center justify-center w-10 h-10 rounded-xl text-gray-500 hover:bg-gray-100 transition-colors"
          aria-label="Abrir menu"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <line x1="3" y1="6" x2="21" y2="6"/>
            <line x1="3" y1="12" x2="21" y2="12"/>
            <line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>

        {/* Logo (mobile only — desktop shows in sidebar) */}
        <div className="md:hidden flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">B</span>
          </div>
          <span className="font-bold text-gray-800 text-base">Border Omni</span>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Right actions */}
        <div className="flex items-center gap-1">

          {/* Notifications bell */}
          <div className="relative">
            <button
              onClick={() => { setShowNotif(v => !v); setShowUser(false); }}
              className="relative flex items-center justify-center w-10 h-10 rounded-xl text-gray-500 hover:bg-gray-100 transition-colors"
              aria-label="Notificações"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
              {unreadCount > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
              )}
            </button>

            {/* Notifications dropdown */}
            {showNotif && (
              <div className="absolute right-0 top-full mt-1 w-80 bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden z-50">
                <div className="flex items-center justify-between px-4 py-3 border-b">
                  <span className="font-semibold text-base text-gray-800">Notificações</span>
                  {unreadCount > 0 && (
                    <span className="text-sm text-blue-600 font-medium">{unreadCount} novas</span>
                  )}
                </div>
                <div className="max-h-72 overflow-y-auto">
                  {MOCK_NOTIFICATIONS.map(n => (
                    <div key={n.id} className={`flex gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer border-b border-gray-50 last:border-0 ${n.unread ? 'bg-blue-50/50' : ''}`}>
                      <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${n.unread ? 'bg-blue-500' : 'bg-gray-200'}`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-gray-700 leading-snug">{n.text}</p>
                        <p className="text-sm text-gray-400 mt-0.5">{n.time} atrás</p>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="px-4 py-2 border-t">
                  <button className="text-sm text-blue-600 hover:underline w-full text-center">
                    Ver todas
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Preferences / Settings shortcut */}
          <button
            onClick={() => { navigate('/configuracoes'); closeAll(); }}
            className="flex items-center justify-center w-10 h-10 rounded-xl text-gray-500 hover:bg-gray-100 transition-colors"
            aria-label="Configurações"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
          </button>

          {/* User avatar + dropdown */}
          <div className="relative ml-1">
            <button
              onClick={() => { setShowUser(v => !v); setShowNotif(false); }}
              className="flex items-center gap-2 pl-1 pr-2 py-1 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                <span className="text-white text-sm font-bold">{initials}</span>
              </div>
              <div className="hidden sm:block text-left">
                <p className="text-sm font-semibold text-gray-800 leading-tight">
                  {user?.first_name} {user?.last_name}
                </p>
                <p className="text-xs text-gray-400 capitalize leading-tight">{user?.plan_name}</p>
              </div>
              <svg className="w-4 h-4 text-gray-400 hidden sm:block" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </button>

            {/* User dropdown */}
            {showUser && (
              <div className="absolute right-0 top-full mt-1 w-56 bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden z-50">
                <div className="px-4 py-3 border-b bg-gray-50">
                  <p className="text-base font-semibold text-gray-800">{user?.first_name} {user?.last_name}</p>
                  <p className="text-sm text-gray-400">{user?.email}</p>
                  <p className="text-sm text-gray-400">{user?.organization_name}</p>
                </div>
                <div className="py-1">
                  <button
                    onClick={() => { navigate('/configuracoes'); closeAll(); }}
                    className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <circle cx="12" cy="12" r="3"/>
                      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
                    </svg>
                    Configurações
                  </button>
                  <button
                    onClick={() => { navigate('/plans'); closeAll(); }}
                    className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <line x1="12" y1="1" x2="12" y2="23"/>
                      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                    </svg>
                    Plano: <span className="capitalize font-medium ml-0.5">{user?.plan_name}</span>
                  </button>
                </div>
                <div className="border-t py-1">
                  <button
                    onClick={() => authService.logout()}
                    className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-red-600 hover:bg-red-50"
                  >
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                      <polyline points="16 17 21 12 16 7"/>
                      <line x1="21" y1="12" x2="9" y2="12"/>
                    </svg>
                    Sair
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>
    </>
  );
}
