import { useState, useEffect, useCallback, useRef } from 'react';
import { advertisingService, type AdCampaign, type AdDashboard, type AdFunnelBreakdownRow, type AdChatMessage, type AdvertisingAccount } from '../services/advertising';
import PromoteCampaignModal from '../components/PromoteCampaignModal';
import { requestGoogleAdsAuthCode } from '../lib/googleAdsOAuth';

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

const PERIOD_OPTIONS = [7, 14, 30, 90];

function money(value: number | null): string {
  return value !== null && value !== undefined ? `R$ ${value.toFixed(2)}` : '—';
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-slate-900/60 rounded-lg p-2.5">
      <p className="text-[10px] text-slate-500 uppercase">{label}</p>
      <p className="text-white text-sm font-semibold">{value}</p>
    </div>
  );
}

function BreakdownTable({ title, rows, emptyHint }: { title: string; rows: AdFunnelBreakdownRow[]; emptyHint: string }) {
  if (rows.length === 0) {
    return null;
  }
  return (
    <div className="bg-slate-900/60 rounded-lg p-3">
      <p className="text-[10px] text-slate-500 uppercase mb-2">{title}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-slate-300">
          <thead>
            <tr className="text-slate-500 text-left">
              <th className="pb-1 pr-3 font-normal">{emptyHint}</th>
              <th className="pb-1 pr-3 font-normal text-right">Leads</th>
              <th className="pb-1 pr-3 font-normal text-right">Qualificados</th>
              <th className="pb-1 pr-3 font-normal text-right">Reservas</th>
              <th className="pb-1 font-normal text-right">Vendas</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.group} className="border-t border-slate-800">
                <td className="py-1 pr-3">{row.group}</td>
                <td className="py-1 pr-3 text-right">{row.total_leads}</td>
                <td className="py-1 pr-3 text-right">{row.qualified_leads}</td>
                <td className="py-1 pr-3 text-right">{row.reservations}</td>
                <td className="py-1 text-right">{row.sales}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MetricsPanel({ campaignId }: { campaignId: number }) {
  const [dashboard, setDashboard] = useState<AdDashboard | null>(null);
  const [daysBack, setDaysBack] = useState(30);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);

  const loadDashboard = useCallback(() => {
    setLoading(true);
    advertisingService.getDashboard(campaignId, daysBack)
      .then(setDashboard)
      .finally(() => setLoading(false));
  }, [campaignId, daysBack]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  async function handleSync() {
    setSyncing(true);
    setSyncError(null);
    try {
      await advertisingService.syncMetrics(campaignId);
      loadDashboard();
    } catch (err) {
      const message = (err as { response?: { data?: { error?: string } } })?.response?.data?.error;
      setSyncError(message || 'Não foi possível sincronizar agora.');
    } finally {
      setSyncing(false);
    }
  }

  const header = (
    <div className="flex items-center justify-between gap-2 flex-wrap">
      <div className="flex items-center gap-1">
        {PERIOD_OPTIONS.map(days => (
          <button
            key={days}
            onClick={() => setDaysBack(days)}
            className={`text-[10px] px-2 py-0.5 rounded ${
              daysBack === days ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            {days}d
          </button>
        ))}
      </div>
      <button
        onClick={handleSync}
        disabled={syncing}
        className="text-[11px] text-blue-400 hover:text-blue-300 disabled:opacity-50 font-medium"
      >
        {syncing ? 'Sincronizando…' : 'Sincronizar agora'}
      </button>
    </div>
  );

  if (loading && !dashboard) {
    return <p className="text-xs text-slate-500 px-4 pb-3">Carregando métricas…</p>;
  }

  if (!dashboard) {
    return null;
  }

  const { snapshot, city_breakdown, keyword_breakdown } = dashboard;
  const noMetricsYet = snapshot.impressions === 0 && snapshot.clicks === 0 && snapshot.cost === 0;

  return (
    <div className="px-4 pb-4 space-y-3">
      {header}
      {syncError && <p className="text-xs text-red-400">{syncError}</p>}
      {noMetricsYet && (
        <p className="text-xs text-slate-500">
          Ainda sem métricas do Google Ads sincronizadas neste período (a sincronização automática roda a cada 6 horas
          enquanto a campanha estiver ativa) — os números de lead abaixo já vêm do CRM independentemente disso.
        </p>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        <StatTile label="Investimento" value={money(snapshot.cost)} />
        <StatTile label="Impressões" value={snapshot.impressions} />
        <StatTile label="Cliques" value={snapshot.clicks} />
        <StatTile label="Leads" value={snapshot.total_leads} />
        <StatTile label="Leads qualificados" value={snapshot.qualified_leads} />
        <StatTile label="Negociações" value={snapshot.negotiations} />
        <StatTile label="Reservas" value={snapshot.reservations} />
        <StatTile label="Vendas" value={snapshot.sales} />
        <StatTile label="CPL" value={money(snapshot.cost_per_lead)} />
        <StatTile label="CPL qualificado" value={money(snapshot.cost_per_qualified_lead)} />
        <StatTile label="CAC" value={money(snapshot.cac)} />
      </div>
      <BreakdownTable title="Por cidade (CRM)" rows={city_breakdown} emptyHint="Cidade" />
      <BreakdownTable title="Por palavra-chave (CRM)" rows={keyword_breakdown} emptyHint="Keyword" />
    </div>
  );
}

function ChatPanel({ campaign, onCampaignChanged }: { campaign: AdCampaign; onCampaignChanged: (c: AdCampaign) => void }) {
  const [messages, setMessages] = useState<AdChatMessage[] | null>(null);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  async function startRecording() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        setTranscribing(true);
        try {
          const { transcription } = await advertisingService.transcribeAudio(campaign.id, blob);
          setInput(prev => (prev ? `${prev} ${transcription}` : transcription));
        } catch {
          setError('Não foi possível transcrever o áudio.');
        } finally {
          setTranscribing(false);
        }
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setError('Não foi possível acessar o microfone (verifique a permissão do navegador).');
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  useEffect(() => {
    advertisingService.getChatHistory(campaign.id).then(setMessages);
  }, [campaign.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;
    setSending(true);
    setError(null);
    setInput('');
    setMessages(prev => [...(prev ?? []), {
      id: Date.now(), role: 'user', content: text, actions_taken: [], is_proactive: false, created_at: new Date().toISOString(),
    }]);
    try {
      const reply = await advertisingService.sendChatMessage(campaign.id, text);
      setMessages(prev => [...(prev ?? []), reply]);
      if (reply.actions_taken.length > 0) {
        // Alguma ação (pausar/retomar/orçamento) pode ter mudado a campanha — recarrega o card.
        advertisingService.listCampaigns().then(all => {
          const updated = all.find(c => c.id === campaign.id);
          if (updated) onCampaignChanged(updated);
        });
      }
    } catch (err) {
      const message = (err as { response?: { data?: { error?: string } } })?.response?.data?.error;
      setError(message || 'Não foi possível enviar a mensagem agora.');
    } finally {
      setSending(false);
    }
  }

  async function handleRunReviewNow() {
    setReviewing(true);
    setError(null);
    try {
      const result = await advertisingService.runProactiveReview(campaign.id);
      if ('status' in result && result.status === 'nothing_to_report') {
        setError('Revisão rodou, mas não achou nada novo para reportar agora.');
      } else {
        setMessages(prev => [...(prev ?? []), result as AdChatMessage]);
      }
    } catch (err) {
      const message = (err as { response?: { data?: { error?: string } } })?.response?.data?.error;
      setError(message || 'Não foi possível rodar a revisão agora.');
    } finally {
      setReviewing(false);
    }
  }

  return (
    <div className="px-4 pb-4">
      <div className="bg-slate-900/60 rounded-lg p-3 flex flex-col gap-2 max-h-96">
        <div className="flex items-center justify-between">
          <p className="text-[10px] text-slate-500">Revisão automática roda toda semana sozinha.</p>
          <button
            onClick={handleRunReviewNow}
            disabled={reviewing}
            className="text-[10px] text-violet-400 hover:text-violet-300 underline disabled:opacity-50"
          >
            {reviewing ? 'Revisando…' : 'Revisar agora'}
          </button>
        </div>
        <div className="flex-1 overflow-y-auto space-y-2 min-h-[120px]">
          {messages === null ? (
            <p className="text-xs text-slate-500">Carregando conversa…</p>
          ) : messages.length === 0 ? (
            <p className="text-xs text-slate-500">
              Pergunte sobre o desempenho da campanha, ou peça para pausar/retomar/ajustar o orçamento.
            </p>
          ) : (
            messages.map(m => (
              <div
                key={m.id}
                className={`text-xs rounded-lg px-3 py-2 max-w-[85%] ${
                  m.role === 'user'
                    ? 'bg-blue-600 text-white ml-auto'
                    : m.is_proactive
                      ? 'bg-violet-900/50 border border-violet-700/50 text-slate-100'
                      : 'bg-slate-700 text-slate-100'
                }`}
              >
                {m.is_proactive && (
                  <p className="mb-1 text-[10px] font-semibold text-violet-300 uppercase tracking-wide">🔄 Revisão automática</p>
                )}
                <p className="whitespace-pre-wrap">{m.content}</p>
                {m.actions_taken?.length > 0 && (
                  <p className="mt-1 text-[10px] text-slate-300/80 italic">
                    Ação: {m.actions_taken.map(a => a.tool).join(', ')}
                  </p>
                )}
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
        {error && <p className="text-xs text-red-400">{error}</p>}
        <div className="flex gap-2">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
            placeholder={transcribing ? 'Transcrevendo áudio…' : 'Ex: como está a performance? aumenta o orçamento pra R$30'}
            disabled={sending || transcribing}
            className="flex-1 px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-xs disabled:opacity-50"
          />
          <button
            onClick={recording ? stopRecording : startRecording}
            disabled={sending || transcribing}
            title={recording ? 'Parar gravação' : 'Gravar áudio'}
            className={`px-3 py-2 rounded-lg text-white text-xs font-semibold disabled:opacity-50 ${recording ? 'bg-red-600 hover:bg-red-500 animate-pulse' : 'bg-slate-700 hover:bg-slate-600'}`}
          >
            {recording ? '⏹' : '🎤'}
          </button>
          <button
            onClick={handleSend}
            disabled={sending || transcribing || !input.trim()}
            className="px-3 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-xs font-semibold"
          >
            {sending ? '…' : 'Enviar'}
          </button>
        </div>
      </div>
    </div>
  );
}

function CampaignRow({ campaign, onChanged }: { campaign: AdCampaign; onChanged: (c: AdCampaign) => void }) {
  const [expanded, setExpanded] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
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
          {campaign.external_campaign_id && !campaign.external_campaign_id.startsWith('dryrun-') && (
            <a
              href={`https://ads.google.com/aw/campaigns?campaignId=${campaign.external_campaign_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold"
            >
              Ver campanhas no Google Ads ↗
            </a>
          )}
          <button
            onClick={() => setExpanded(e => !e)}
            className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium"
          >
            {expanded ? 'Ocultar métricas' : 'Ver métricas'}
          </button>
          <button
            onClick={() => setChatOpen(o => !o)}
            className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold"
          >
            {chatOpen ? 'Ocultar chat' : 'Chat com IA'}
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
      {chatOpen && <ChatPanel campaign={campaign} onCampaignChanged={onChanged} />}
    </div>
  );
}

/**
 * Status da conexão Google Ads + reautorização — vive aqui (nível da página),
 * não dentro do modal "Nova Campanha", porque conectar é uma coisa de conta
 * (uma vez), não de campanha (toda vez). Reautorizar reusa o customer_id já
 * salvo — não precisa escolher a conta de novo, só pedir o consentimento com
 * o escopo atualizado (ex.: quando um novo escopo como datamanager é
 * adicionado depois que a conta já tinha sido conectada).
 */
function GoogleAdsConnectionStatus() {
  const [account, setAccount] = useState<AdvertisingAccount | null | undefined>(undefined); // undefined = carregando
  const [status, setStatus] = useState<'idle' | 'connecting' | 'error' | 'done'>('idle');
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    advertisingService.listAccounts().then(accounts => setAccount(accounts[0] ?? null));
  }, []);

  useEffect(() => { load(); }, [load]);

  function handleReauthorize() {
    if (!account) return;
    setStatus('connecting');
    setError(null);
    requestGoogleAdsAuthCode(
      async (code) => {
        try {
          const discover = await advertisingService.googleAdsDiscover(code);
          await advertisingService.googleAdsFinalize({
            refresh_token: discover.refresh_token,
            customer_id: account.customer_id,
            login_customer_id: account.login_customer_id || undefined,
          });
          setStatus('done');
          load();
        } catch (e) {
          const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Falha ao reautorizar a conta.';
          setStatus('error');
          setError(msg);
        }
      },
      (message) => { setStatus('error'); setError(message); },
    );
  }

  if (account === undefined || account === null) return null; // nada conectado ainda — o modal "Nova Campanha" cuida disso

  return (
    <div className="flex items-center gap-3 text-xs text-slate-400">
      <span className="text-emerald-400">✓ Google Ads conectado ({account.customer_id})</span>
      <button
        onClick={handleReauthorize}
        disabled={status === 'connecting'}
        title="Reconecte se o envio de conversões (leads qualificados/reservas/vendas) começar a falhar por permissão"
        className="text-slate-400 hover:text-amber-400 underline disabled:opacity-50"
      >
        {status === 'connecting' ? 'Conectando…' : status === 'done' ? 'Permissões atualizadas ✓' : 'Atualizar permissões'}
      </button>
      {error && <span className="text-red-400">{error}</span>}
    </div>
  );
}

export default function AdvertisingPage() {
  const [campaigns, setCampaigns] = useState<AdCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewCampaign, setShowNewCampaign] = useState(false);

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

  function handleCreated() {
    load();
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-white text-2xl font-bold">Anúncios (Google Ads)</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            Campanhas criadas a partir de "Promover" em cada ninhada, ou direto por aqui.
          </p>
          <div className="mt-2">
            <GoogleAdsConnectionStatus />
          </div>
        </div>
        <button
          onClick={() => setShowNewCampaign(true)}
          className="flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-sm font-semibold transition-colors"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Nova Campanha
        </button>
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

      {showNewCampaign && (
        <PromoteCampaignModal
          onClose={() => setShowNewCampaign(false)}
          onCreated={handleCreated}
        />
      )}
    </div>
  );
}
