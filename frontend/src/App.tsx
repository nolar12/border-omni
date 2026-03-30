import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import { registerSW } from 'virtual:pwa-register';
import Layout from './components/Layout';
import PrivateRoute from './components/PrivateRoute';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import LeadsPage from './pages/LeadsPage';
import Simulator from './pages/Simulator';
import Channels from './pages/Channels';
import Plans from './pages/Plans';
import ABTestPage from './pages/ABTestPage';
import SettingsPage from './pages/SettingsPage';
import TemplatesPage from './pages/TemplatesPage';
import CampaignsPage from './pages/CampaignsPage';
import GalleryPage from './pages/GalleryPage';
import ContractsPage from './pages/ContractsPage';
import ContractPublicPage from './pages/ContractPublicPage';
import NotesPage from './pages/NotesPage';
import DogsPage from './pages/DogsPage';
import LittersPage from './pages/LittersPage';
import ShareTargetPage from './pages/ShareTargetPage';

export default function App() {
  useEffect(() => {
    registerSW({ immediate: true });
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        {/* Página pública do contrato — sem autenticação */}
        <Route path="/contrato/:token" element={<ContractPublicPage />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          {/* Leads usa rota com :id opcional para layout 3 colunas */}
          <Route path="leads" element={<LeadsPage />} />
          <Route path="leads/:id" element={<LeadsPage />} />
          <Route path="simulator" element={<Simulator />} />
          <Route path="ab-test" element={<ABTestPage />} />
          <Route path="channels" element={<Channels />} />
          <Route path="plans" element={<Plans />} />
          {/* Placeholder routes para features futuras */}
          <Route path="campanhas" element={<CampaignsPage />} />
          <Route path="automacoes" element={<ComingSoon title="Automações" />} />
          <Route path="relatorios" element={<ComingSoon title="Relatórios" />} />
          <Route path="equipe" element={<ComingSoon title="Equipe" />} />
          <Route path="configuracoes" element={<SettingsPage />} />
          <Route path="templates" element={<TemplatesPage />} />
          <Route path="galeria" element={<GalleryPage />} />
          <Route path="contratos" element={<ContractsPage />} />
          <Route path="notas" element={<NotesPage />} />
          <Route path="canil/caes" element={<DogsPage />} />
          <Route path="canil/ninhadas" element={<LittersPage />} />
        </Route>
        {/* Share Target — recebe fotos compartilhadas pelo SO */}
        <Route path="/share" element={<ShareTargetPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

function ComingSoon({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center">
      <div className="text-5xl mb-4">🚧</div>
      <h2 className="text-2xl font-bold text-gray-700">{title}</h2>
      <p className="text-gray-400 text-base mt-2">Em desenvolvimento. Em breve disponível.</p>
    </div>
  );
}
