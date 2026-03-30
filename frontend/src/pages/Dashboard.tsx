import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { leadsService } from '../services/leads';
import type { LeadStats, LeadListItem } from '../types';
import TierBadge from '../components/TierBadge';
import StatusBadge from '../components/StatusBadge';

export default function Dashboard() {
  const [stats, setStats] = useState<LeadStats | null>(null);
  const [recent, setRecent] = useState<LeadListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([leadsService.getStats(), leadsService.getLeads({ page: 1 })])
      .then(([s, leads]) => { setStats(s); setRecent(leads.results.slice(0, 8)); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-48">
      <span className="loading loading-spinner loading-lg text-primary" />
    </div>
  );

  const cards = [
    { label: 'Total Leads', value: stats?.total ?? 0, icon: '👥', color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'Tier A', value: stats?.tier_a ?? 0, icon: '🌟', color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'Tier B', value: stats?.tier_b ?? 0, icon: '🔶', color: 'text-amber-600', bg: 'bg-amber-50' },
    { label: 'Tier C', value: stats?.tier_c ?? 0, icon: '🔴', color: 'text-red-600', bg: 'bg-red-50' },
    { label: 'Qualificados', value: stats?.qualified ?? 0, icon: '✅', color: 'text-violet-600', bg: 'bg-violet-50' },
    { label: 'Handoff', value: stats?.handoff ?? 0, icon: '🤝', color: 'text-orange-600', bg: 'bg-orange-50' },
  ];

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {cards.map(c => (
          <div key={c.label} className={`${c.bg} rounded-2xl p-4 shadow-sm`}>
            <p className="text-2xl mb-1">{c.icon}</p>
            <p className={`text-3xl font-bold ${c.color}`}>{c.value}</p>
            <p className="text-sm text-gray-500 font-medium mt-1">{c.label}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
          <h2 className="font-semibold text-gray-800 text-base">Leads Recentes</h2>
          <button onClick={() => navigate('/leads')} className="text-sm text-blue-600 hover:underline">
            Ver todos →
          </button>
        </div>
        {recent.length === 0 ? (
          <div className="text-center py-10 text-gray-400">
            <p className="text-3xl mb-2">🐶</p>
            <p className="text-sm">Nenhum lead ainda.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-base">
              <thead><tr className="text-sm text-gray-400 uppercase bg-gray-50">
                <th className="text-left px-4 py-2.5 font-medium">Lead</th>
                <th className="text-left px-4 py-2.5 font-medium hidden sm:table-cell">Cidade</th>
                <th className="text-left px-4 py-2.5 font-medium">Tier</th>
                <th className="text-left px-4 py-2.5 font-medium hidden md:table-cell">Score</th>
                <th className="text-left px-4 py-2.5 font-medium">Status</th>
                <th className="text-left px-4 py-2.5 font-medium hidden sm:table-cell">Data</th>
              </tr></thead>
              <tbody>
                {recent.map(lead => (
                  <tr key={lead.id} className="border-t border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/leads/${lead.id}`)}>
                    <td className="px-4 py-3">
                      <p className="font-medium text-gray-800">{lead.full_name || '—'}</p>
                      <p className="text-sm text-gray-400">{lead.phone}</p>
                    </td>
                    <td className="px-4 py-3 text-gray-500 hidden sm:table-cell">
                      {lead.city ? `${lead.city}/${lead.state}` : '—'}
                    </td>
                    <td className="px-4 py-3"><TierBadge tier={lead.tier} /></td>
                    <td className="px-4 py-3 hidden md:table-cell font-mono font-bold text-gray-600">{lead.score}</td>
                    <td className="px-4 py-3"><StatusBadge status={lead.status} /></td>
                    <td className="px-4 py-3 text-gray-400 text-sm hidden sm:table-cell">
                      {new Date(lead.created_at).toLocaleDateString('pt-BR')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
