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

  return (
    <div data-theme="border_omni" className="flex h-screen overflow-hidden bg-white">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main area pushed right on desktop */}
      <div className="md:ml-[240px] flex flex-col flex-1 min-w-0 overflow-hidden">
        <Topbar onMenuClick={() => setSidebarOpen(true)} />

        {isFullHeight ? (
          /* Full-height area for the 3-column leads/chat layout */
          <div className="flex-1 overflow-hidden">
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

      {/* Mobile bottom nav (hidden on leads page — it has its own nav logic) */}
      {!isFullHeight && <BottomNav />}
    </div>
  );
}
