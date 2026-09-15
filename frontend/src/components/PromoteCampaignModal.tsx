import { useState, useEffect } from 'react';
import DateInput from './DateInput';
import { advertisingService, type AdCampaign } from '../services/advertising';
import { littersService } from '../services/litters';
import type { Litter } from '../types';

// Minimal type declaration for the Google Identity Services popup code client
// (google.accounts.oauth2.initCodeClient) — same "SDK popup → code → backend
// discover/finalize" architecture already used for Meta via window.FB.login().
declare global {
  interface Window {
    google?: {
      accounts: {
        oauth2: {
          initCodeClient(config: {
            client_id: string;
            scope: string;
            ux_mode: 'popup';
            callback: (response: { code?: string; error?: string }) => void;
          }): { requestCode(): void };
        };
      };
    };
  }
}

const GOOGLE_ADS_CLIENT_ID = import.meta.env.VITE_GOOGLE_ADS_CLIENT_ID as string | undefined;
let gisScriptLoading = false;

function loadGoogleIdentityServices(onLoad: () => void) {
  if (window.google?.accounts?.oauth2) { onLoad(); return; }
  if (gisScriptLoading) {
    const check = setInterval(() => {
      if (window.google?.accounts?.oauth2) { clearInterval(check); onLoad(); }
    }, 200);
    return;
  }
  gisScriptLoading = true;
  const script = document.createElement('script');
  script.src = 'https://accounts.google.com/gsi/client';
  script.async = true;
  script.defer = true;
  script.onload = onLoad;
  document.body.appendChild(script);
}

type GoogleAdsConnectStep =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'selecting'; refreshToken: string; customers: string[] }
  | { status: 'finalizing' }
  | { status: 'error'; message: string };

interface PromoteCampaignModalProps {
  /** Ninhada fixa (fluxo "Promover" a partir da tela de Ninhadas) — some o seletor. */
  litter?: Litter | null;
  onClose: () => void;
  onCreated?: (campaign: AdCampaign) => void;
}

export default function PromoteCampaignModal({ litter: fixedLitter, onClose, onCreated }: PromoteCampaignModalProps) {
  const [checkingAccount, setCheckingAccount] = useState(true);
  const [hasAccount, setHasAccount] = useState(false);
  const [connectStep, setConnectStep] = useState<GoogleAdsConnectStep>({ status: 'idle' });
  const [selectedCustomerIdx, setSelectedCustomerIdx] = useState(0);
  const [manualCustomerId, setManualCustomerId] = useState('');
  const [manualLoginCustomerId, setManualLoginCustomerId] = useState('');

  // Seletor de ninhada — só usado quando o modal é aberto sem uma ninhada fixa
  // (ex.: botão "Nova Campanha" na tela de Anúncios).
  const [availableLitters, setAvailableLitters] = useState<Litter[]>([]);
  const [selectedLitterId, setSelectedLitterId] = useState<number | null>(fixedLitter?.id ?? null);
  const selectedLitter = fixedLitter ?? availableLitters.find(l => l.id === selectedLitterId) ?? null;

  useEffect(() => {
    if (fixedLitter) return;
    littersService.list().then(setAvailableLitters);
  }, [fixedLitter]);

  useEffect(() => {
    advertisingService.listAccounts()
      .then(accounts => setHasAccount(accounts.length > 0))
      .finally(() => setCheckingAccount(false));
  }, []);

  function startGoogleAdsConnect() {
    if (!GOOGLE_ADS_CLIENT_ID) {
      setConnectStep({ status: 'error', message: 'VITE_GOOGLE_ADS_CLIENT_ID não configurado no .env do frontend.' });
      return;
    }
    setConnectStep({ status: 'loading' });
    loadGoogleIdentityServices(() => {
      const client = window.google!.accounts.oauth2.initCodeClient({
        client_id: GOOGLE_ADS_CLIENT_ID,
        scope: 'https://www.googleapis.com/auth/adwords',
        ux_mode: 'popup',
        callback: async (response) => {
          if (!response.code) {
            setConnectStep({ status: 'error', message: 'Autorização cancelada ou negada.' });
            return;
          }
          try {
            const discover = await advertisingService.googleAdsDiscover(response.code);
            if (discover.accessible_customers.length === 0) {
              setConnectStep({ status: 'error', message: 'Nenhuma conta Google Ads acessível encontrada para este login.' });
              return;
            }
            setSelectedCustomerIdx(0);
            setManualCustomerId(discover.accessible_customers[0] ?? '');
            setManualLoginCustomerId('');
            setConnectStep({ status: 'selecting', refreshToken: discover.refresh_token, customers: discover.accessible_customers });
          } catch (e) {
            const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Falha ao listar contas Google Ads.';
            setConnectStep({ status: 'error', message: msg });
          }
        },
      });
      client.requestCode();
    });
  }

  async function finalizeGoogleAdsConnect() {
    if (connectStep.status !== 'selecting') return;
    setConnectStep({ status: 'finalizing' });
    try {
      await advertisingService.googleAdsFinalize({
        refresh_token: connectStep.refreshToken,
        customer_id: manualCustomerId,
        login_customer_id: manualLoginCustomerId || undefined,
      });
      setHasAccount(true);
      setConnectStep({ status: 'idle' });
    } catch (e) {
      const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Falha ao conectar a conta.';
      setConnectStep({ status: 'error', message: msg });
    }
  }

  const [region, setRegion] = useState('');
  const [radiusKm, setRadiusKm] = useState(30);
  const [dailyBudget, setDailyBudget] = useState(20);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [landingUrl, setLandingUrl] = useState(fixedLitter ? `https://bordercolliesul.com.br/ninhada/${fixedLitter.id}` : '');
  const [audienceDescription, setAudienceDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [campaign, setCampaign] = useState<AdCampaign | null>(null);
  const [clientRequestId] = useState(() => crypto.randomUUID());

  function handleLitterChange(id: string) {
    const litterId = id ? Number(id) : null;
    setSelectedLitterId(litterId);
    setLandingUrl(litterId ? `https://bordercolliesul.com.br/ninhada/${litterId}` : '');
  }

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const created = await advertisingService.promoteLitter({
        litter_id: selectedLitterId ?? undefined,
        name: selectedLitter ? undefined : 'Campanha Google Ads — Canil',
        daily_budget: dailyBudget,
        region,
        radius_km: radiusKm,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        landing_url: landingUrl,
        audience_description: audienceDescription,
        client_request_id: clientRequestId,
      });
      setCampaign(created);
      onCreated?.(created);
      if (created.status === 'error') {
        setError(created.error_message || 'Não foi possível criar a campanha agora, tente novamente.');
      } else if (created.error_message) {
        // Campanha criada com sucesso, mas grupo de anúncios/palavras-chave/anúncio
        // tiveram um problema parcial — ainda assim é um recurso real no Google Ads.
        setError(created.error_message);
      }
    } catch (err) {
      const message = (err as { response?: { data?: { error?: string } } })?.response?.data?.error;
      setError(message || 'Não foi possível criar a campanha agora, tente novamente.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-slate-800 rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-slate-700">
          <h2 className="text-white text-lg font-bold">
            {fixedLitter ? `Promover: ${fixedLitter.name}` : 'Nova Campanha (Google Ads)'}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <div className="p-6 space-y-4 overflow-y-auto">
          {checkingAccount ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : !hasAccount ? (
            <div className="space-y-4">
              <p className="text-sm text-slate-300">
                Nenhuma conta Google Ads conectada ainda. Conecte uma conta para poder criar a campanha.
              </p>

              {connectStep.status === 'selecting' ? (
                <div className="space-y-3">
                  <p className="text-xs text-amber-400/90 bg-amber-500/10 border border-amber-700/40 rounded-lg p-2">
                    Atenção: se a lista abaixo mostrar apenas o ID da sua conta gerenciadora (MCC), corrija manualmente
                    para o Customer ID da conta de anúncios real (ex: "205-907-0343" → digite só os números).
                  </p>
                  <div>
                    <label className="text-xs text-slate-400">Contas detectadas automaticamente</label>
                    <select
                      value={selectedCustomerIdx}
                      onChange={e => {
                        setSelectedCustomerIdx(Number(e.target.value));
                        setManualCustomerId(connectStep.customers[Number(e.target.value)] ?? '');
                      }}
                      className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-white text-sm"
                    >
                      {connectStep.customers.map((c, i) => (
                        <option key={c} value={i}>{c}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-400">Customer ID da conta de anúncios (editável)</label>
                    <input
                      value={manualCustomerId}
                      onChange={e => setManualCustomerId(e.target.value.replace(/\D/g, ''))}
                      placeholder="Ex: 2059070343"
                      className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-white text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400">ID da conta gerenciadora / MCC (login_customer_id, opcional)</label>
                    <input
                      value={manualLoginCustomerId}
                      onChange={e => setManualLoginCustomerId(e.target.value.replace(/\D/g, ''))}
                      placeholder="Ex: 1717587348"
                      className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-white text-sm"
                    />
                  </div>
                  <button
                    onClick={finalizeGoogleAdsConnect}
                    disabled={!manualCustomerId}
                    className="w-full px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-sm font-semibold"
                  >
                    Conectar esta conta
                  </button>
                </div>
              ) : (
                <button
                  onClick={startGoogleAdsConnect}
                  disabled={connectStep.status === 'loading' || connectStep.status === 'finalizing'}
                  className="w-full px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-sm font-semibold"
                >
                  {connectStep.status === 'loading' || connectStep.status === 'finalizing' ? 'Conectando…' : 'Conectar Google Ads'}
                </button>
              )}

              {connectStep.status === 'error' && <p className="text-sm text-red-400">{connectStep.message}</p>}
            </div>
          ) : campaign ? (
            <div className="space-y-3">
              <p className="text-sm text-slate-300">
                Status da campanha:{' '}
                <span className="font-semibold text-white">{campaign.status}</span>
              </p>
              {campaign.external_campaign_id && !campaign.external_campaign_id.startsWith('dryrun-') && (
                <a
                  href={`https://ads.google.com/aw/campaigns?campaignId=${campaign.external_campaign_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold"
                >
                  Ver campanhas no Google Ads ↗
                </a>
              )}
              {error && <p className="text-sm text-red-400">{error}</p>}
              {campaign.ad_headlines?.length > 0 && (
                <div className="bg-slate-900/60 rounded-lg p-3 text-xs text-slate-300 space-y-2">
                  <div>
                    <p className="text-slate-500 uppercase tracking-wide text-[10px] mb-1">Headlines</p>
                    {campaign.ad_headlines.map((h, i) => <p key={i}>• {h}</p>)}
                  </div>
                  {campaign.ad_descriptions?.length > 0 && (
                    <div>
                      <p className="text-slate-500 uppercase tracking-wide text-[10px] mb-1">Descriptions</p>
                      {campaign.ad_descriptions.map((d, i) => <p key={i}>• {d}</p>)}
                    </div>
                  )}
                  {campaign.ad_keywords?.length > 0 && (
                    <div>
                      <p className="text-slate-500 uppercase tracking-wide text-[10px] mb-1">Palavras-chave</p>
                      <p>{campaign.ad_keywords.join(' · ')}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <>
              {!fixedLitter && (
                <div>
                  <label className="text-xs text-slate-400">Ninhada (opcional)</label>
                  <select
                    value={selectedLitterId ?? ''}
                    onChange={e => handleLitterChange(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-white text-sm"
                  >
                    <option value="">Nenhuma / campanha geral do canil</option>
                    {availableLitters.map(l => (
                      <option key={l.id} value={l.id}>{l.name}</option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="text-xs text-slate-400">Canal</label>
                <div className="mt-1 px-3 py-2 rounded-lg bg-slate-900/60 text-slate-300 text-sm">Google Ads (Pesquisa)</div>
              </div>
              <div>
                <label className="text-xs text-slate-400">
                  Região <span className="text-slate-500">(cidades separadas por vírgula — restringe de verdade onde o anúncio aparece)</span>
                </label>
                <input
                  value={region}
                  onChange={e => setRegion(e.target.value)}
                  placeholder="Ex: Camboriú, Balneário Camboriú, Itajaí"
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-white text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400">Raio (km)</label>
                  <input
                    type="number" min={1} value={radiusKm}
                    onChange={e => setRadiusKm(Number(e.target.value))}
                    className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-white text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400">Orçamento diário (R$)</label>
                  <input
                    type="number" min={1} step="0.01" value={dailyBudget}
                    onChange={e => setDailyBudget(Number(e.target.value))}
                    className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-white text-sm"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400">Data inicial</label>
                  <DateInput value={startDate} onChange={setStartDate} className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-white text-sm" />
                </div>
                <div>
                  <label className="text-xs text-slate-400">Data final</label>
                  <DateInput value={endDate} onChange={setEndDate} className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-white text-sm" />
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-400">Landing page</label>
                <input
                  value={landingUrl}
                  onChange={e => setLandingUrl(e.target.value)}
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-white text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400">
                  Público-alvo <span className="text-slate-500">(opcional — a IA usa isso para gerar as sugestões de anúncio)</span>
                </label>
                <textarea
                  value={audienceDescription}
                  onChange={e => setAudienceDescription(e.target.value)}
                  placeholder="Ex: famílias de alto poder aquisitivo, região nobre, que valorizam pedigree e criação responsável"
                  rows={3}
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-white text-sm resize-none"
                />
              </div>
              {error && <p className="text-sm text-red-400">{error}</p>}
            </>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-700">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-slate-300 hover:text-white text-sm font-medium">
            {campaign ? 'Fechar' : 'Cancelar'}
          </button>
          {hasAccount && !campaign && (
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-sm font-semibold transition-colors"
            >
              {submitting ? 'Criando…' : 'Criar campanha'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
