import { useState, useEffect, useCallback, useRef } from 'react';
import { advertisingService, type AdCampaign, type AdMetric, type AdChatMessage } from '../services/advertising';
import PromoteCampaignModal from '../components/PromoteCampaignModal';

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
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);

  useEffect(() => {
    advertisingService.getMetrics(campaignId)
      .then(setMetrics)
      .finally(() => setLoading(false));
  }, [campaignId]);

  async function handleSync() {
    setSyncing(true);
    setSyncError(null);
    try {
      const result = await advertisingService.syncMetrics(campaignId);
      setMetrics(result.metrics);
    } catch (err) {
      const message = (err as { response?: { data?: { error?: string } } })?.response?.data?.error;
      setSyncError(message || 'Não foi possível sincronizar agora.');
    } finally {
      setSyncing(false);
    }
  }

  const syncButton = (
    <button
      onClick={handleSync}
      disabled={syncing}
      className="text-[11px] text-blue-400 hover:text-blue-300 disabled:opacity-50 font-medium"
    >
      {syncing ? 'Sincronizando…' : 'Sincronizar agora'}
    </button>
  );

  if (loading) {
    return <p className="text-xs text-slate-500 px-4 pb-3">Carregando métricas…</p>;
  }

  if (!metrics || metrics.length === 0) {
    return (
      <div className="px-4 pb-3 space-y-1">
        <p className="text-xs text-slate-500">
          Ainda sem métricas sincronizadas (a sincronização automática roda a cada 6 horas enquanto a campanha estiver ativa).
        </p>
        {syncButton}
        {syncError && <p className="text-xs text-red-400">{syncError}</p>}
      </div>
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
    <div className="px-4 pb-4 space-y-2">
      <div className="flex items-center justify-between">
        {syncButton}
        {syncError && <p className="text-xs text-red-400">{syncError}</p>}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
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
      id: Date.now(), role: 'user', content: text, actions_taken: [], created_at: new Date().toISOString(),
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

  return (
    <div className="px-4 pb-4">
      <div className="bg-slate-900/60 rounded-lg p-3 flex flex-col gap-2 max-h-96">
        <div className="flex-1 overflow-y-auto space-y-2 min-h-[120px]">
          {messages === null ? (
            <p className="text-xs text-slate-500">Carregando conversa…</p>
          ) : messages.length === 0 ? (
            <p className="text-xs text-slate-500">
              Pergunte sobre o desempenho da campanha, ou peça para pausar/retomar/ajustar o orçamento.
            </p>
          ) : (
            messages.map(m => (
              <div key={m.id} className={`text-xs rounded-lg px-3 py-2 max-w-[85%] ${m.role === 'user' ? 'bg-blue-600 text-white ml-auto' : 'bg-slate-700 text-slate-100'}`}>
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
