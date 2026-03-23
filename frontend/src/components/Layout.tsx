import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import BottomNav from './BottomNav';
import Footer from './Footer';

// Pages that use the full-height 3-column leads layout (no footer, no padding)
const FULLHEIGHT_ROUTES = ['/leads'];

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const isFullHeight = FULLHEIGHT_ROUTES.some(r => location.pathname.startsWith(r));

  // No mobile: quando um chat específico está aberto, esconde topbar e bottom nav
  // para aproveitar toda a tela. No desktop permanecem visíveis.
  const isMobileChat = /^\/leads\/\d+/.test(location.pathname);

  return (
    <div data-theme="border_omni" className="flex h-screen overflow-hidden bg-white">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main area pushed right on desktop */}
      <div className={`md:ml-[240px] flex flex-col flex-1 min-w-0 overflow-hidden ${isMobileChat ? 'md:pt-16' : 'pt-16'}`}>
        {/* Topbar: esconde no mobile quando o chat está aberto */}
        <div className={isMobileChat ? 'hidden md:block' : ''}>
          <Topbar onMenuClick={() => setSidebarOpen(true)} />
        </div>

        {isFullHeight ? (
          /* Full-height area for the 3-column leads/chat layout */
          <div className={`flex-1 overflow-hidden ${isMobileChat ? '' : 'pb-16'} md:pb-0`}>
            <Outlet />
          </div>
        ) : (
          /* Standard scrollable layout for other pages */
          <>
            <main className="flex-1 overflow-y-auto p-4 pb-20 md:pb-4 md:p-6 bg-gray-50">
              <Outlet />
            </main>
            <div className="hidden md:block">
              <Footer />
            </div>
          </>
        )}
      </div>

      {/* Mobile bottom nav: esconde quando o chat está aberto */}
      {!isMobileChat && <BottomNav />}
    </div>
  );
}
