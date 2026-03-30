import { useEffect, useState } from 'react';
import api from '../services/api';

interface VariantStats {
  ab_variant: string;
  total: number;
  completed: number;
  qualified: number;
  tier_a: number;
  tier_b: number;
  tier_c: number;
  avg_score: number | null;
}

const VARIANT_META: Record<string, { label: string; type: string; theme: string; color: string }> = {
  A: { label: 'Variante A', type: 'Vídeo', theme: '—', color: 'bg-blue-500' },
  B: { label: 'Variante B', type: 'Foto', theme: 'Energia', color: 'bg-emerald-500' },
  C: { label: 'Variante C', type: 'Foto', theme: 'Inteligência', color: 'bg-violet-500' },
  D: { label: 'Variante D', type: 'Foto', theme: 'Lealdade', color: 'bg-amber-500' },
};

function pct(part: number, total: number) {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

function Bar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
        <div
          className={`h-2 rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${value}%` }}
        />
      </div>
      <span className="text-xs font-bold text-gray-700 w-8 text-right">{value}%</span>
    </div>
  );
}

function WinnerBadge() {
  return (
    <span className="ml-2 text-xs font-bold uppercase tracking-wide bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded-full">
      melhor
    </span>
  );
}

export default function ABTestPage() {
  const [rows, setRows] = useState<VariantStats[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<VariantStats[]>('/leads/ab_stats/')
      .then(r => setRows(r.data))
      .finally(() => setLoading(false));
  }, []);

  const totalLeads = rows.reduce((s, r) => s + r.total, 0);

  // Encontra a variante vencedora por taxa de qualificação
  const bestQualified = rows.reduce<string | null>((best, r) => {
    if (!best) return r.ab_variant;
    const bRow = rows.find(x => x.ab_variant === best)!;
    return pct(r.qualified, r.total) > pct(bRow.qualified, bRow.total) ? r.ab_variant : best;
  }, null);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <span className="loading loading-spinner loading-lg text-primary" />
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center text-gray-400">
        <p className="text-4xl mb-3">🧪</p>
        <p className="text-sm font-medium text-gray-600">Nenhum dado de A/B test ainda.</p>
        <p className="text-xs mt-1 max-w-xs">
          Configure as variáveis <code className="bg-gray-100 px-1 rounded">AB_MEDIA_URL_A/B/C/D</code> e aguarde os primeiros leads chegarem.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">

      {/* Header */}
      <div>
        <h1 className="text-lg font-bold text-gray-800">Teste A/B — Mídia de abertura</h1>
        <p className="text-sm text-gray-400 mt-0.5">
          {totalLeads} lead{totalLeads !== 1 ? 's' : ''} distribuídos entre as 4 variantes
        </p>
      </div>

      {/* Cards por variante */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {rows.map(row => {
          const meta = VARIANT_META[row.ab_variant] ?? {
            label: `Variante ${row.ab_variant}`, type: '—', theme: '—', color: 'bg-gray-400',
          };
          const completionRate = pct(row.completed, row.total);
          const qualifiedRate  = pct(row.qualified, row.total);
          const tierARate      = pct(row.tier_a, row.total);
          const isWinner       = row.ab_variant === bestQualified && rows.length > 1;

          return (
            <div key={row.ab_variant} className={`bg-white rounded-2xl border-2 shadow-sm p-5 ${isWinner ? 'border-yellow-400' : 'border-gray-100'}`}>
              {/* Variant header */}
              <div className="flex items-center gap-2 mb-4">
                <div className={`w-3 h-3 rounded-full flex-shrink-0 ${meta.color}`} />
                <span className="font-bold text-gray-800 text-sm">{meta.label}</span>
                <span className="text-xs text-gray-400">{meta.type}{meta.theme !== '—' ? ` · ${meta.theme}` : ''}</span>
                {isWinner && <WinnerBadge />}
                <span className="ml-auto text-xs font-semibold text-gray-500">{row.total} leads</span>
              </div>

              {/* Metrics */}
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>Conclusão do fluxo</span>
                    <span>{row.completed}/{row.total}</span>
                  </div>
                  <Bar value={completionRate} color={meta.color} />
                </div>

                <div>
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>Qualificados</span>
                    <span>{row.qualified}/{row.total}</span>
                  </div>
                  <Bar value={qualifiedRate} color={meta.color} />
                </div>

                <div>
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>Tier A</span>
                    <span>{row.tier_a}/{row.total}</span>
                  </div>
                  <Bar value={tierARate} color={meta.color} />
                </div>

                <div className="pt-1 border-t border-gray-50 flex items-center justify-between">
                  <span className="text-xs text-gray-400">Score médio</span>
                  <span className="text-sm font-bold text-gray-700">
                    {row.avg_score != null ? Math.round(row.avg_score) : '—'}<span className="text-xs font-normal text-gray-400">/100</span>
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Comparison table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100">
          <h2 className="font-semibold text-sm text-gray-800">Comparativo geral</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-400 uppercase bg-gray-50">
                <th className="text-left px-4 py-2 font-medium">Variante</th>
                <th className="text-left px-4 py-2 font-medium">Tipo</th>
                <th className="text-right px-4 py-2 font-medium">Leads</th>
                <th className="text-right px-4 py-2 font-medium">Conclusão</th>
                <th className="text-right px-4 py-2 font-medium">Qualificados</th>
                <th className="text-right px-4 py-2 font-medium">Tier A</th>
                <th className="text-right px-4 py-2 font-medium">Score médio</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => {
                const meta = VARIANT_META[row.ab_variant] ?? { label: `Var. ${row.ab_variant}`, type: '—', theme: '—', color: 'bg-gray-400' };
                const isWinner = row.ab_variant === bestQualified && rows.length > 1;
                return (
                  <tr key={row.ab_variant} className={`border-t border-gray-50 ${isWinner ? 'bg-yellow-50' : ''}`}>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className={`w-2.5 h-2.5 rounded-full ${meta.color}`} />
                        <span className="font-medium text-gray-800">{meta.label}</span>
                        {isWinner && <WinnerBadge />}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-gray-500">
                      {meta.type}{meta.theme !== '—' ? ` · ${meta.theme}` : ''}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono font-bold text-gray-700">{row.total}</td>
                    <td className="px-4 py-2.5 text-right font-semibold text-gray-700">{pct(row.completed, row.total)}%</td>
                    <td className="px-4 py-2.5 text-right font-semibold text-gray-700">{pct(row.qualified, row.total)}%</td>
                    <td className="px-4 py-2.5 text-right font-semibold text-gray-700">{pct(row.tier_a, row.total)}%</td>
                    <td className="px-4 py-2.5 text-right font-mono font-bold text-gray-700">
                      {row.avg_score != null ? Math.round(row.avg_score) : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-xs text-gray-400">
        "Conclusão" = lead respondeu as 4 perguntas. "Qualificados" = status QUALIFIED. Variante vencedora destacada pela maior taxa de qualificação.
      </p>
    </div>
  );
}
