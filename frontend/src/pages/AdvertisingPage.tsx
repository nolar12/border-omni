import { useState, useEffect, useCallback } from 'react';
import { advertisingService, type AdCampaign, type AdMetric } from '../services/advertising';

const STATUS_LABELS: Record<string, string> = {
  draft: 'Rascunho',
  pending: 'Publicando',
  active: 'Ativa',
  paused: 'Pausada',
  error: 'Erro',
  ended: 'Encerrada',
};

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-slate-600 text-slate-200',
  pending: 'bg-amber-600 text-white',
  active: 'bg-emerald-600 text-white',
  paused: 'bg-slate-500 text-white',
  error: 'bg-red-600 text-white',
  ended: 'bg-slate-700 text-slate-300',
};

function MetricsPanel({ campaignId }: { campaignId: number }) {
  const [metrics, setMetrics] = useState<AdMetric[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    advertisingService.getMetrics(campaignId)
      .then(setMetrics)
      .finally(() => setLoading(false));
  }, [campaignId]);

  if (loading) {
    return <p className="text-xs text-slate-500 px-4 pb-3">Carregando métricas…</p>;
  }

  if (!metrics || metrics.length === 0) {
    return (
      <p className="text-xs text-slate-500 px-4 pb-3">
        Ainda sem métricas sincronizadas (a sincronização diária roda automaticamente enquanto a campanha estiver ativa).
      </p>
    );
  }

  const totals = metrics.reduce(
    (acc, m) => ({
      impressions: acc.impressions + m.impressions,
      clicks: acc.clicks + m.clicks,
      cost: acc.cost + Number(m.cost),
      conversions: acc.conversions + m.conversions,
    }),
    { impressions: 0, clicks: 0, cost: 0, conversions: 0 },
  );
  const cpl = totals.conversions > 0 ? totals.cost / totals.conversions : null;

  return (
    <div className="px-4 pb-4 grid grid-cols-2 sm:grid-cols-5 gap-3">
      <div className="bg-slate-900/60 rounded-lg p-2.5">
        <p className="text-[10px] text-slate-500 uppercase">Investimento</p>
        <p className="text-white text-sm font-semibold">R$ {totals.cost.toFixed(2)}</p>
      </div>
      <div className="bg-slate-900/60 rounded-lg p-2.5">
        <p className="text-[10px] text-slate-500 uppercase">Impressões</p>
        <p className="text-white text-sm font-semibold">{totals.impressions}</p>
      </div>
      <div className="bg-slate-900/60 rounded-lg p-2.5">
        <p className="text-[10px] text-slate-500 uppercase">Cliques</p>
        <p className="text-white text-sm font-semibold">{totals.clicks}</p>
      </div>
      <div className="bg-slate-900/60 rounded-lg p-2.5">
        <p className="text-[10px] text-slate-500 uppercase">Conversões</p>
        <p className="text-white text-sm font-semibold">{totals.conversions}</p>
      </div>
      <div className="bg-slate-900/60 rounded-lg p-2.5">
        <p className="text-[10px] text-slate-500 uppercase">CPL</p>
        <p className="text-white text-sm font-semibold">{cpl !== null ? `R$ ${cpl.toFixed(2)}` : '—'}</p>
      </div>
    </div>
  );
}

function CampaignRow({ campaign, onChanged }: { campaign: AdCampaign; onChanged: (c: AdCampaign) => void }) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);

  async function togglePause() {
    setBusy(true);
    try {
      const updated = campaign.status === 'paused'
        ? await advertisingService.resumeCampaign(campaign.id)
        : await advertisingService.pauseCampaign(campaign.id);
      onChanged(updated);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <div className="p-4 flex items-center justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-white font-semibold text-sm truncate">{campaign.name}</h3>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${STATUS_COLORS[campaign.status] ?? 'bg-slate-600 text-white'}`}>
              {STATUS_LABELS[campaign.status] ?? campaign.status}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {campaign.litter_name && <>Ninhada: {campaign.litter_name} · </>}
            R$ {campaign.daily_budget}/dia
            {campaign.region && <> · {campaign.region}</>}
          </p>
          {campaign.error_message && (
            <p className="text-xs text-red-400 mt-1">{campaign.error_message}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setExpanded(e => !e)}
            className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium"
          >
            {expanded ? 'Ocultar métricas' : 'Ver métricas'}
          </button>
          {(campaign.status === 'active' || campaign.status === 'paused') && (
            <button
              onClick={togglePause}
              disabled={busy}
              className="px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-xs font-semibold"
            >
              {campaign.status === 'paused' ? 'Retomar' : 'Pausar'}
            </button>
          )}
        </div>
      </div>
      {expanded && <MetricsPanel campaignId={campaign.id} />}
    </div>
  );
}

export default function AdvertisingPage() {
  const [campaigns, setCampaigns] = useState<AdCampaign[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setCampaigns(await advertisingService.listCampaigns());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function handleChanged(updated: AdCampaign) {
    setCampaigns(prev => prev.map(c => c.id === updated.id ? updated : c));
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-white text-2xl font-bold">Anúncios (Google Ads)</h1>
        <p className="text-slate-400 text-sm mt-0.5">
          Campanhas criadas a partir de "Promover" em cada ninhada.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : campaigns.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <p>Nenhuma campanha criada ainda.</p>
          <p className="text-sm mt-1">Vá em Ninhadas → Promover para criar a primeira.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {campaigns.map(c => (
            <CampaignRow key={c.id} campaign={c} onChanged={handleChanged} />
          ))}
        </div>
      )}
    </div>
  );
}
