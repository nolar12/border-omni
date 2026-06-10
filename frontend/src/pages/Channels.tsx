import { useEffect, useRef, useState } from 'react';
import { channelsService } from '../services/channels';
import type {
  ChannelProvider,
  QualityRatingEvent,
  MetaDiscoverResponse,
  MetaPageAsset,
  MetaWabaAsset,
} from '../types';

// Minimal type declaration for the Facebook JS SDK loaded at runtime
declare global {
  interface Window {
    FB: {
      init(opts: { appId: string; version: string; xfbml?: boolean; cookie?: boolean }): void;
      login(
        cb: (resp: { authResponse?: { code?: string; accessToken?: string } | null }) => void,
        opts: { config_id: string; response_type: string; override_default_response_type: boolean },
      ): void;
    };
    fbAsyncInit?: () => void;
  }
}

const META_APP_ID = import.meta.env.VITE_META_APP_ID as string | undefined;
const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? '';
const META_CONFIG_IDS: Record<string, string> = {
  whatsapp: import.meta.env.VITE_META_CONFIG_ID_WHATSAPP ?? '',
  facebook: import.meta.env.VITE_META_CONFIG_ID_FACEBOOK ?? '',
  messenger: import.meta.env.VITE_META_CONFIG_ID_FACEBOOK ?? '',
  instagram: import.meta.env.VITE_META_CONFIG_ID_INSTAGRAM ?? '',
};

type OAuthStep =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'selecting'; discover: MetaDiscoverResponse }
  | { status: 'finalizing' }
  | { status: 'done'; channelName: string }
  | { status: 'error'; message: string };

type ProviderKey = 'whatsapp' | 'instagram' | 'facebook' | 'messenger';

interface FieldDef {
  key: keyof ChannelProvider;
  label: string;
  placeholder: string;
  help?: string;
  link?: { url: string; label: string };
  secret?: boolean;
}

interface ProviderMeta {
  label: string;
  icon: string;
  color: string;
  description: string;
  docsUrl: string;
  fields: FieldDef[];
}

const PROVIDERS: Record<ProviderKey, ProviderMeta> = {
  whatsapp: {
    label: 'WhatsApp Business API',
    icon: '📱',
    color: 'bg-green-500',
    description: 'Conecte sua conta WhatsApp Business via Meta Cloud API para enviar e receber mensagens.',
    docsUrl: 'https://developers.facebook.com/docs/whatsapp/cloud-api/get-started',
    fields: [
      {
        key: 'app_id', label: 'App ID', placeholder: '1234567890',
        help: 'ID do seu aplicativo no Meta for Developers',
        link: { url: 'https://developers.facebook.com/apps/', label: 'Abrir Meta for Developers' },
      },
      {
        key: 'app_secret', label: 'App Secret', placeholder: '••••••••', secret: true,
        help: 'Configurações Básicas do seu App',
        link: { url: 'https://developers.facebook.com/apps/', label: 'App → Configurações Básicas' },
      },
      {
        key: 'access_token', label: 'Access Token', placeholder: 'EAAr...', secret: true,
        help: 'Token de acesso permanente (System User Token)',
        link: { url: 'https://business.facebook.com/settings/system-users', label: 'Meta Business Suite → Usuários do Sistema' },
      },
      {
        key: 'phone_number_id', label: 'Phone Number ID', placeholder: '1040197165841892',
        help: 'ID do número no painel WhatsApp do seu App',
        link: { url: 'https://developers.facebook.com/apps/', label: 'App → WhatsApp → Configuração' },
      },
      {
        key: 'business_account_id', label: 'Business Account ID (WABA)', placeholder: '2133277890774145',
        help: 'ID da conta WhatsApp Business (WABA)',
        link: { url: 'https://business.facebook.com/settings/whatsapp-business-accounts', label: 'Meta Business Suite → Contas WhatsApp' },
      },
      {
        key: 'webhook_verify_token', label: 'Webhook Verify Token', placeholder: 'meu_token_secreto',
        help: 'Token que você cria e configura na Meta para validar o webhook',
        link: { url: 'https://developers.facebook.com/docs/graph-api/webhooks/getting-started', label: 'Docs: Configurar Webhook' },
      },
      {
        key: 'webhook_url', label: 'Webhook URL', placeholder: 'https://seu-dominio.com/api/webhooks/whatsapp/',
        help: 'URL pública e acessível que receberá os eventos da Meta',
        link: { url: 'https://developers.facebook.com/apps/', label: 'App → WhatsApp → Configuração → Webhooks' },
      },
    ],
  },
  instagram: {
    label: 'Instagram Messaging',
    icon: '📸',
    color: 'bg-pink-500',
    description: 'Receba e responda mensagens diretas do Instagram via Meta API.',
    docsUrl: 'https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api',
    fields: [
      {
        key: 'app_id', label: 'App ID', placeholder: '1234567890',
        help: 'App com permissão instagram_manage_messages ativada',
        link: { url: 'https://developers.facebook.com/apps/', label: 'Meta for Developers → Seus Apps' },
      },
      {
        key: 'app_secret', label: 'App Secret', placeholder: '••••••••', secret: true,
        help: 'Segredo do aplicativo',
        link: { url: 'https://developers.facebook.com/apps/', label: 'App → Configurações Básicas' },
      },
      {
        key: 'access_token', label: 'Page Access Token', placeholder: 'EAAr...', secret: true,
        help: 'Token da Página do Facebook vinculada à conta Instagram',
        link: { url: 'https://business.facebook.com/settings/system-users', label: 'Meta Business Suite → Usuários do Sistema' },
      },
      {
        key: 'instagram_account_id', label: 'Instagram Account ID', placeholder: '17841400000000000',
        help: 'ID da conta profissional Instagram',
        link: { url: 'https://developers.facebook.com/docs/instagram-platform/reference/ig-user', label: 'Docs: Obter IG User ID' },
      },
      {
        key: 'webhook_verify_token', label: 'Webhook Verify Token', placeholder: 'meu_token_secreto',
        help: 'Token definido por você para validar o webhook',
        link: { url: 'https://developers.facebook.com/docs/graph-api/webhooks/getting-started', label: 'Docs: Webhooks' },
      },
      {
        key: 'webhook_url', label: 'Webhook URL', placeholder: 'https://seu-dominio.com/api/webhooks/instagram/',
        help: 'URL que receberá os eventos de mensagens do Instagram',
        link: { url: 'https://developers.facebook.com/apps/', label: 'App → Instagram → Webhooks' },
      },
    ],
  },
  facebook: {
    label: 'Facebook Page',
    icon: '👤',
    color: 'bg-blue-600',
    description: 'Gerencie conversas via Messenger e comentários da sua Página do Facebook.',
    docsUrl: 'https://developers.facebook.com/docs/messenger-platform/get-started',
    fields: [
      {
        key: 'app_id', label: 'App ID', placeholder: '1234567890',
        help: 'ID do aplicativo Meta com Messenger ativado',
        link: { url: 'https://developers.facebook.com/apps/', label: 'Meta for Developers → Seus Apps' },
      },
      {
        key: 'app_secret', label: 'App Secret', placeholder: '••••••••', secret: true,
        help: 'Segredo do aplicativo',
        link: { url: 'https://developers.facebook.com/apps/', label: 'App → Configurações Básicas' },
      },
      {
        key: 'access_token', label: 'Page Access Token', placeholder: 'EAAr...', secret: true,
        help: 'Token de acesso da Página do Facebook',
        link: { url: 'https://business.facebook.com/settings/system-users', label: 'Meta Business Suite → Usuários do Sistema' },
      },
      {
        key: 'page_id', label: 'Page ID', placeholder: '100000000000000',
        help: 'ID numérico da sua Página no Facebook',
        link: { url: 'https://www.facebook.com/help/1502952483237806', label: 'Como encontrar o Page ID' },
      },
      {
        key: 'webhook_verify_token', label: 'Webhook Verify Token', placeholder: 'meu_token_secreto',
        link: { url: 'https://developers.facebook.com/docs/graph-api/webhooks/getting-started', label: 'Docs: Webhooks' },
      },
      {
        key: 'webhook_url', label: 'Webhook URL', placeholder: 'https://seu-dominio.com/api/webhooks/facebook/',
        link: { url: 'https://developers.facebook.com/apps/', label: 'App → Messenger → Configuração de Webhooks' },
      },
    ],
  },
  messenger: {
    label: 'Messenger',
    icon: '💬',
    color: 'bg-indigo-500',
    description: 'Integração dedicada ao Messenger com suporte a chatbots e handoff humano.',
    docsUrl: 'https://developers.facebook.com/docs/messenger-platform',
    fields: [
      {
        key: 'app_id', label: 'App ID', placeholder: '1234567890',
        link: { url: 'https://developers.facebook.com/apps/', label: 'Meta for Developers → Seus Apps' },
      },
      {
        key: 'app_secret', label: 'App Secret', placeholder: '••••••••', secret: true,
        link: { url: 'https://developers.facebook.com/apps/', label: 'App → Configurações Básicas' },
      },
      {
        key: 'access_token', label: 'Page Access Token', placeholder: 'EAAr...', secret: true,
        link: { url: 'https://business.facebook.com/settings/system-users', label: 'Meta Business Suite → Usuários do Sistema' },
      },
      {
        key: 'page_id', label: 'Page ID', placeholder: '100000000000000',
        link: { url: 'https://www.facebook.com/help/1502952483237806', label: 'Como encontrar o Page ID' },
      },
      {
        key: 'webhook_verify_token', label: 'Webhook Verify Token', placeholder: 'meu_token_secreto',
        link: { url: 'https://developers.facebook.com/docs/graph-api/webhooks/getting-started', label: 'Docs: Webhooks' },
      },
      {
        key: 'webhook_url', label: 'Webhook URL', placeholder: 'https://seu-dominio.com/api/webhooks/messenger/',
        link: { url: 'https://developers.facebook.com/apps/', label: 'App → Messenger → Webhooks' },
      },
    ],
  },
};

const STATUS_BADGE: Record<string, { cls: string; label: string }> = {
  verified: { cls: 'bg-emerald-100 text-emerald-700', label: 'Verificado' },
  pending:  { cls: 'bg-amber-100 text-amber-700',   label: 'Pendente'  },
  failed:   { cls: 'bg-red-100 text-red-700',        label: 'Falhou'    },
};

type FormData = Partial<ChannelProvider> & { name?: string };

const WEBHOOK_PATHS: Record<ProviderKey, string> = {
  whatsapp: '/api/webhooks/whatsapp/',
  instagram: '/api/webhooks/meta/',
  facebook: '/api/webhooks/meta/',
  messenger: '/api/webhooks/meta/',
};

function generateVerifyToken(): string {
  const arr = new Uint8Array(18);
  crypto.getRandomValues(arr);
  return Array.from(arr, b => b.toString(16).padStart(2, '0')).join('');
}

const EMPTY_FORM = (provider: ProviderKey): FormData => ({
  name: '', provider, app_id: '', app_secret: '', access_token: '',
  phone_number_id: '', business_account_id: '', instagram_account_id: '',
  page_id: '',
  webhook_verify_token: generateVerifyToken(),
  webhook_url: `${API_URL}${WEBHOOK_PATHS[provider]}`,
  is_active: true, is_simulated: false,
});

export default function Channels() {
  const [channels, setChannels] = useState<ChannelProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeProvider, setActiveProvider] = useState<ProviderKey>('whatsapp');
  const [editing, setEditing] = useState<ChannelProvider | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormData>(EMPTY_FORM('whatsapp'));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});

  // Quality rating sync
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [qualityHistory, setQualityHistory] = useState<Record<number, QualityRatingEvent[]>>({});
  const [showHistoryId, setShowHistoryId] = useState<number | null>(null);

  // Meta OAuth state machine
  const [oauthStep, setOauthStep] = useState<OAuthStep>({ status: 'idle' });
  const [showOAuthModal, setShowOAuthModal] = useState(false);
  const [oauthProvider, setOauthProvider] = useState<ProviderKey>('whatsapp');
  // Selection state
  const [selectedWabaIdx, setSelectedWabaIdx] = useState(0);
  const [selectedPhoneIdx, setSelectedPhoneIdx] = useState(0);
  const [selectedPageIdx, setSelectedPageIdx] = useState(0);
  const [channelName, setChannelName] = useState('');
  const fbSdkLoaded = useRef(false);

  function load() {
    channelsService.getAll().then(setChannels).finally(() => setLoading(false));
  }
  useEffect(() => { load(); }, []);

  async function handleSyncQuality(id: number) {
    setSyncingId(id);
    try {
      await channelsService.syncQuality(id);
      load();
    } finally {
      setSyncingId(null);
    }
  }

  async function toggleQualityHistory(id: number) {
    if (showHistoryId === id) {
      setShowHistoryId(null);
      return;
    }
    setShowHistoryId(id);
    if (!qualityHistory[id]) {
      const events = await channelsService.getQualityHistory(id);
      setQualityHistory(prev => ({ ...prev, [id]: events }));
    }
  }

  // Load Facebook JS SDK once
  useEffect(() => {
    if (!META_APP_ID || fbSdkLoaded.current) return;
    fbSdkLoaded.current = true;
    window.fbAsyncInit = () => {
      window.FB.init({ appId: META_APP_ID, version: 'v22.0', cookie: true, xfbml: false });
    };
    const script = document.createElement('script');
    script.src = 'https://connect.facebook.net/en_US/sdk.js';
    script.async = true;
    script.defer = true;
    document.body.appendChild(script);
  }, []);

  function openCreate(provider: ProviderKey) {
    setEditing(null);
    setForm(EMPTY_FORM(provider));
    setError('');
    setSuccess('');
    setShowSecrets({});
    setShowForm(true);
  }

  function openEdit(ch: ChannelProvider) {
    setEditing(ch);
    setForm({ ...ch, access_token: '', app_secret: '' });
    setError('');
    setSuccess('');
    setShowSecrets({});
    setShowForm(true);
    setActiveProvider(ch.provider as ProviderKey);
  }

  async function handleSave() {
    setSaving(true); setError(''); setSuccess('');
    try {
      const payload = { ...form };
      if (!payload.access_token) delete payload.access_token;
      if (!payload.app_secret) delete payload.app_secret;
      editing
        ? await channelsService.update(editing.id, payload)
        : await channelsService.create(payload);
      setSuccess('Canal salvo com sucesso!');
      setShowForm(false);
      load();
    } catch (err: unknown) {
      const e = err as { response?: { data?: Record<string, string[]> } };
      setError(e?.response?.data
        ? Object.entries(e.response.data).map(([k, v]) => `${k}: ${v.join(', ')}`).join(' | ')
        : 'Erro ao salvar.');
    } finally { setSaving(false); }
  }

  async function handleDelete(id: number) {
    if (!confirm('Excluir este canal? Esta ação não pode ser desfeita.')) return;
    await channelsService.delete(id);
    load();
  }

  function toggleSecret(key: string) {
    setShowSecrets(s => ({ ...s, [key]: !s[key] }));
  }

  // ── Meta OAuth helpers ─────────────────────────────────────────────────────

  function openOAuth(provider: ProviderKey) {
    setOauthProvider(provider);
    setOauthStep({ status: 'idle' });
    setSelectedWabaIdx(0);
    setSelectedPhoneIdx(0);
    setSelectedPageIdx(0);
    setChannelName('');
    setShowOAuthModal(true);
  }

  function startOAuth() {
    if (!window.FB) {
      setOauthStep({ status: 'error', message: 'Facebook SDK ainda não carregado. Aguarde e tente novamente.' });
      return;
    }
    const configId = META_CONFIG_IDS[oauthProvider];
    if (!configId) {
      setOauthStep({ status: 'error', message: `META_CONFIG_ID para ${oauthProvider} não configurado. Adicione VITE_META_CONFIG_ID_${oauthProvider.toUpperCase()} ao .env.` });
      return;
    }
    setOauthStep({ status: 'loading' });
    window.FB.login(
      async (response) => {
        const code = response.authResponse?.code;
        if (!code) {
          setOauthStep({ status: 'error', message: 'Autorização cancelada ou negada pelo usuário.' });
          return;
        }
        try {
          const discover = await channelsService.metaDiscover(code, oauthProvider);
          setOauthStep({ status: 'selecting', discover });
        } catch (e: unknown) {
          const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Falha ao listar contas Meta.';
          setOauthStep({ status: 'error', message: msg });
        }
      },
      { config_id: configId, response_type: 'code', override_default_response_type: true },
    );
  }

  async function finalizeOAuth() {
    if (oauthStep.status !== 'selecting') return;
    const { discover } = oauthStep;
    setOauthStep({ status: 'finalizing' });
    try {
      if (oauthProvider === 'whatsapp') {
        const wabas = discover.assets as MetaWabaAsset[];
        const waba = wabas[selectedWabaIdx];
        const phone = waba?.phone_numbers[selectedPhoneIdx];
        if (!waba || !phone) throw new Error('Selecione uma conta e um número válidos.');
        await channelsService.metaFinalize({
          provider: 'whatsapp',
          name: channelName || waba.waba_name,
          access_token: discover.access_token,
          waba_id: waba.waba_id,
          phone_number_id: phone.id,
        });
        setOauthStep({ status: 'done', channelName: channelName || waba.waba_name || phone.display_phone_number });
      } else {
        const pages = discover.assets as MetaPageAsset[];
        const page = pages[selectedPageIdx];
        if (!page) throw new Error('Selecione uma página válida.');
        const igAccount = page.instagram_business_account;
        await channelsService.metaFinalize({
          provider: oauthProvider as 'facebook' | 'messenger' | 'instagram',
          name: channelName || page.name,
          access_token: discover.access_token,
          page_id: page.id,
          page_name: page.name,
          page_token: page.access_token,
          instagram_account_id: igAccount?.id,
          instagram_username: igAccount?.username,
        });
        setOauthStep({ status: 'done', channelName: channelName || page.name });
      }
      load();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error
        ?? (e as Error)?.message
        ?? 'Falha ao salvar canal.';
      setOauthStep({ status: 'error', message: msg });
    }
  }

  function closeOAuthModal() {
    if (oauthStep.status === 'done') load();
    setShowOAuthModal(false);
    setOauthStep({ status: 'idle' });
  }

  const providerChannels = (p: ProviderKey) => channels.filter(c => c.provider === p);
  const meta = PROVIDERS[activeProvider];
  const redChannels = channels.filter(c => c.provider === 'whatsapp' && c.quality_rating === 'RED');

  return (
    <div className="max-w-4xl space-y-6">

      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-gray-800">Integrações & Canais</h1>
        <p className="text-sm text-gray-500 mt-0.5">Configure suas contas da Meta para receber e enviar mensagens.</p>
      </div>

      {/* Banner de alerta — canais com qualidade RED */}
      {redChannels.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-2xl px-4 py-3 flex items-start gap-3">
          <svg className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <div className="flex-1">
            <p className="text-sm font-semibold text-red-700">
              {redChannels.length === 1
                ? `Canal "${redChannels[0].name || redChannels[0].phone_number_id}" com qualidade BAIXA`
                : `${redChannels.length} canais com qualidade BAIXA`}
            </p>
            <p className="text-xs text-red-600 mt-0.5">
              Risco de banimento do número. Revise os templates enviados, certifique-se de que os leads têm opt-in e evite mensagens não solicitadas.
            </p>
          </div>
        </div>
      )}

      {/* Provider tabs */}
      <div className="flex gap-2 flex-wrap">
        {(Object.keys(PROVIDERS) as ProviderKey[]).map(p => {
          const pm = PROVIDERS[p];
          const count = providerChannels(p).length;
          return (
            <button
              key={p}
              onClick={() => setActiveProvider(p)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all
                ${activeProvider === p
                  ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                  : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300 hover:text-blue-600'}`}
            >
              <span>{pm.icon}</span>
              <span>{pm.label.split(' ')[0]}</span>
              {count > 0 && (
                <span className={`text-xs px-1.5 py-0.5 rounded-full font-semibold
                  ${activeProvider === p ? 'bg-white/20 text-white' : 'bg-blue-100 text-blue-600'}`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Provider info banner */}
      <div className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
        <div className="flex items-start gap-4">
          <div className={`w-12 h-12 rounded-xl ${meta.color} flex items-center justify-center text-2xl flex-shrink-0`}>
            {meta.icon}
          </div>
          <div className="flex-1">
            <h2 className="font-semibold text-gray-800">{meta.label}</h2>
            <p className="text-sm text-gray-500 mt-0.5">{meta.description}</p>
          </div>
          <div className="flex gap-2 flex-shrink-0">
            {META_APP_ID && META_CONFIG_IDS[activeProvider] && (
              <button
                onClick={() => openOAuth(activeProvider)}
                className="flex items-center gap-1.5 bg-[#1877F2] hover:bg-[#166FE5] text-white text-xs font-semibold px-3 py-2 rounded-xl transition-colors"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                </svg>
                Conectar com Meta
              </button>
            )}
            <button
              onClick={() => openCreate(activeProvider)}
              className="flex-shrink-0 bg-white hover:bg-gray-50 text-gray-600 text-xs font-semibold px-4 py-2 rounded-xl border border-gray-200 transition-colors"
            >
              + Manual
            </button>
          </div>
        </div>
      </div>

      {/* Channel list for active provider */}
      {loading ? (
        <div className="flex justify-center py-10">
          <span className="loading loading-spinner loading-lg text-primary" />
        </div>
      ) : providerChannels(activeProvider).length === 0 ? (
        <div className="bg-white rounded-2xl border border-dashed border-gray-200 p-10 text-center">
          <p className="text-4xl mb-3">{meta.icon}</p>
          <p className="font-medium text-gray-500 text-sm">Nenhuma conta {meta.label} configurada</p>
          <p className="text-xs text-gray-400 mt-1 mb-4">Conecte sua conta Meta em 1 clique</p>
          <div className="flex gap-2 justify-center">
            {META_APP_ID && META_CONFIG_IDS[activeProvider] && (
              <button
                onClick={() => openOAuth(activeProvider)}
                className="flex items-center gap-1.5 bg-[#1877F2] hover:bg-[#166FE5] text-white text-xs font-semibold px-4 py-2 rounded-xl"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                </svg>
                Conectar com Meta
              </button>
            )}
            <button onClick={() => openCreate(activeProvider)} className="bg-white border border-gray-200 text-gray-600 text-xs font-semibold px-4 py-2 rounded-xl hover:bg-gray-50">
              + Configuração manual
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {providerChannels(activeProvider).map(ch => {
            const status = STATUS_BADGE[ch.verification_status] ?? STATUS_BADGE.pending;
            return (
              <div key={ch.id} className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
                <div className="flex items-start gap-3">
                  <div className={`w-10 h-10 rounded-xl ${meta.color} flex items-center justify-center text-lg flex-shrink-0`}>
                    {meta.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-semibold text-gray-800 text-sm">
                        {ch.name || meta.label}
                      </p>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${status.cls}`}>
                        {status.label}
                      </span>
                      {!ch.is_active && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">Inativo</span>
                      )}
                      {ch.is_simulated && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-600">Simulado</span>
                      )}
                      {ch.provider === 'whatsapp' && ch.quality_rating && (
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          ch.quality_rating === 'GREEN'  ? 'bg-green-100 text-green-700'  :
                          ch.quality_rating === 'YELLOW' ? 'bg-yellow-100 text-yellow-700' :
                          ch.quality_rating === 'RED'    ? 'bg-red-100 text-red-700'    :
                          'bg-gray-100 text-gray-500'
                        }`}>
                          {ch.quality_rating === 'GREEN'  ? '● Qualidade Alta'   :
                           ch.quality_rating === 'YELLOW' ? '● Qualidade Média'  :
                           ch.quality_rating === 'RED'    ? '● Qualidade Baixa'  :
                           ch.quality_rating}
                        </span>
                      )}
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 mt-2">
                      {ch.phone_number_id && (
                        <p className="text-xs text-gray-500"><span className="font-medium text-gray-600">Phone ID:</span> {ch.phone_number_id}</p>
                      )}
                      {ch.business_account_id && (
                        <p className="text-xs text-gray-500"><span className="font-medium text-gray-600">WABA ID:</span> {ch.business_account_id}</p>
                      )}
                      {ch.instagram_account_id && (
                        <p className="text-xs text-gray-500"><span className="font-medium text-gray-600">Instagram ID:</span> {ch.instagram_account_id}</p>
                      )}
                      {ch.page_id && (
                        <p className="text-xs text-gray-500"><span className="font-medium text-gray-600">Page ID:</span> {ch.page_id}</p>
                      )}
                      {ch.app_id && (
                        <p className="text-xs text-gray-500"><span className="font-medium text-gray-600">App ID:</span> {ch.app_id}</p>
                      )}
                      {ch.access_token_masked && (
                        <p className="text-xs text-gray-500"><span className="font-medium text-gray-600">Token:</span> {ch.access_token_masked}</p>
                      )}
                      {ch.webhook_url && (
                        <p className="text-xs text-gray-400 truncate col-span-2">↗ {ch.webhook_url}</p>
                      )}
                      {ch.provider === 'whatsapp' && ch.quality_synced_at && (
                        <p className="text-xs text-gray-400 col-span-2">
                          Sync: {new Date(ch.quality_synced_at).toLocaleString('pt-BR')}
                        </p>
                      )}
                    </div>

                    {/* Quality history (colapsável) */}
                    {ch.provider === 'whatsapp' && showHistoryId === ch.id && (
                      <div className="mt-3 border-t border-gray-100 pt-3">
                        <p className="text-xs font-semibold text-gray-500 mb-2">Histórico de qualidade</p>
                        {(qualityHistory[ch.id] ?? []).length === 0 ? (
                          <p className="text-xs text-gray-400">Nenhuma mudança registrada ainda.</p>
                        ) : (
                          <div className="space-y-1">
                            {(qualityHistory[ch.id] ?? []).map(ev => (
                              <div key={ev.id} className="flex items-center gap-2 text-xs">
                                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                                  ev.new_rating === 'GREEN'  ? 'bg-green-500'  :
                                  ev.new_rating === 'YELLOW' ? 'bg-yellow-500' :
                                  ev.new_rating === 'RED'    ? 'bg-red-500'    :
                                  'bg-gray-400'
                                }`} />
                                <span className="text-gray-500">
                                  {ev.previous_rating || '—'} → <strong>{ev.new_rating}</strong>
                                  {ev.is_degradation && <span className="text-red-500 ml-1">↓</span>}
                                </span>
                                <span className="text-gray-400 ml-auto">
                                  {new Date(ev.created_at).toLocaleString('pt-BR')}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col gap-2 flex-shrink-0 items-end">
                    <div className="flex gap-2">
                      <button onClick={() => openEdit(ch)} className="text-xs text-blue-600 hover:underline font-medium">Editar</button>
                      <button onClick={() => handleDelete(ch.id)} className="text-xs text-red-500 hover:underline font-medium">Excluir</button>
                    </div>
                    {ch.provider === 'whatsapp' && !ch.is_simulated && (
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSyncQuality(ch.id)}
                          disabled={syncingId === ch.id}
                          title="Sincronizar quality rating agora"
                          className="flex items-center gap-1 text-xs text-gray-500 hover:text-blue-600 border border-gray-200 rounded-lg px-2 py-1 hover:border-blue-300 disabled:opacity-50 transition-colors"
                        >
                          <svg className={`w-3 h-3 ${syncingId === ch.id ? 'animate-spin' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.95"/>
                          </svg>
                          {syncingId === ch.id ? 'Sincronizando...' : 'Sync'}
                        </button>
                        <button
                          onClick={() => toggleQualityHistory(ch.id)}
                          className="text-xs text-gray-500 hover:text-blue-600 border border-gray-200 rounded-lg px-2 py-1 hover:border-blue-300 transition-colors"
                        >
                          {showHistoryId === ch.id ? 'Fechar' : 'Histórico'}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Help box */}
      {META_APP_ID && META_CONFIG_IDS[activeProvider] ? (
        <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-4 text-sm text-emerald-700">
          <p className="font-semibold mb-1">Configuração automática disponível</p>
          <p className="text-xs text-emerald-600">
            Clique em <strong>Conectar com Meta</strong> para autorizar o acesso ao seu Business Portfolio.
            O token gerado pertence à sua empresa — não à conta pessoal de ninguém.
            Webhooks e credenciais são configurados automaticamente.
          </p>
        </div>
      ) : (
        <div className="bg-blue-50 border border-blue-100 rounded-2xl p-4 text-sm text-blue-700">
          <p className="font-semibold mb-1">Como obter as credenciais?</p>
          <ol className="list-decimal list-inside space-y-0.5 text-xs text-blue-600">
            <li>Acesse <strong>developers.facebook.com</strong> e crie ou acesse seu aplicativo</li>
            <li>Em <strong>WhatsApp → Configuração</strong>, copie o Phone Number ID e o WABA ID</li>
            <li>Gere um token de acesso permanente no <strong>Meta Business Suite</strong></li>
            <li>Configure o Webhook apontando para sua URL pública com o token de verificação</li>
          </ol>
        </div>
      )}

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg shadow-2xl flex flex-col max-h-[90vh]">
            {/* Modal header */}
            <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100">
              <div className={`w-9 h-9 rounded-xl ${PROVIDERS[form.provider as ProviderKey]?.color ?? 'bg-gray-400'} flex items-center justify-center text-lg`}>
                {PROVIDERS[form.provider as ProviderKey]?.icon}
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-gray-800 text-sm">
                  {editing ? 'Editar' : 'Novo'} — {PROVIDERS[form.provider as ProviderKey]?.label}
                </h3>
                <div className="flex items-center gap-3 mt-0.5">
                  {editing && <p className="text-xs text-gray-400">Campos secretos em branco = mantém valor atual</p>}
                  {PROVIDERS[form.provider as ProviderKey]?.docsUrl && (
                    <a
                      href={PROVIDERS[form.provider as ProviderKey].docsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-500 hover:text-blue-700 hover:underline flex items-center gap-1"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Ver documentação
                    </a>
                  )}
                </div>
              </div>
              <button onClick={() => setShowForm(false)} className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-gray-100 text-gray-400 text-lg">✕</button>
            </div>

            {/* Modal body */}
            <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">
              {error && <div className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2">{error}</div>}

              {/* Provider selector (only on create) */}
              {!editing && (
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Plataforma</label>
                  <div className="grid grid-cols-2 gap-2">
                    {(Object.keys(PROVIDERS) as ProviderKey[]).map(p => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => setForm(f => ({
                          ...EMPTY_FORM(p),
                          name: f.name,
                          webhook_verify_token: f.webhook_verify_token || generateVerifyToken(),
                          webhook_url: `${API_URL}${WEBHOOK_PATHS[p]}`,
                        }))}
                        className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-sm transition-all
                          ${form.provider === p
                            ? 'border-blue-500 bg-blue-50 text-blue-700 font-semibold'
                            : 'border-gray-200 text-gray-600 hover:border-gray-300'}`}
                      >
                        <span>{PROVIDERS[p].icon}</span>
                        <span>{PROVIDERS[p].label.split(' ')[0]}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Name */}
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">Nome do canal</label>
                <input
                  type="text"
                  placeholder={`Ex: ${meta.label} Principal`}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-900 bg-white outline-none focus:border-blue-400"
                  value={form.name ?? ''}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                />
              </div>

              {/* Dynamic fields per provider */}
              {PROVIDERS[form.provider as ProviderKey]?.fields.map(field => {
                const isWebhookUrl = field.key === 'webhook_url';
                const isVerifyToken = field.key === 'webhook_verify_token';
                const fieldValue = (form as Record<string, string>)[String(field.key)] ?? '';

                return (
                  <div key={String(field.key)}>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-xs font-semibold text-gray-600">{field.label}</label>
                      <div className="flex items-center gap-2">
                        {isVerifyToken && (
                          <button
                            type="button"
                            onClick={() => setForm(f => ({ ...f, webhook_verify_token: generateVerifyToken() }))}
                            className="text-xs text-blue-500 hover:text-blue-700 font-medium"
                          >
                            ↻ Gerar novo
                          </button>
                        )}
                        {field.link && (
                          <a
                            href={field.link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-500 hover:text-blue-700 hover:underline flex items-center gap-1"
                          >
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                            {field.link.label}
                          </a>
                        )}
                      </div>
                    </div>
                    <div className="relative">
                      <input
                        type={field.secret && !showSecrets[String(field.key)] ? 'password' : 'text'}
                        placeholder={field.placeholder}
                        readOnly={isWebhookUrl}
                        className={`w-full border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-900 outline-none pr-10 ${
                          isWebhookUrl
                            ? 'bg-gray-50 text-gray-500 cursor-default focus:border-gray-200'
                            : 'bg-white focus:border-blue-400'
                        }`}
                        value={fieldValue}
                        onChange={e => !isWebhookUrl && setForm(f => ({ ...f, [field.key]: e.target.value }))}
                      />
                      {isWebhookUrl && fieldValue && (
                        <button
                          type="button"
                          title="Copiar URL"
                          onClick={() => navigator.clipboard.writeText(fieldValue)}
                          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-blue-600 text-xs"
                        >
                          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                          </svg>
                        </button>
                      )}
                      {field.secret && (
                        <button
                          type="button"
                          onClick={() => toggleSecret(String(field.key))}
                          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs"
                        >
                          {showSecrets[String(field.key)] ? '🙈' : '👁️'}
                        </button>
                      )}
                    </div>
                    {isWebhookUrl && (
                      <p className="text-xs text-gray-400 mt-1">URL gerada automaticamente — copie e configure no painel Meta.</p>
                    )}
                    {field.help && !isWebhookUrl && <p className="text-xs text-gray-400 mt-1">{field.help}</p>}
                  </div>
                );
              })}

              {/* Toggles */}
              <div className="flex gap-6 pt-1">
                <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-600">
                  <input type="checkbox" className="toggle toggle-sm toggle-primary"
                    checked={form.is_active ?? true}
                    onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))} />
                  Ativo
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-600">
                  <input type="checkbox" className="toggle toggle-sm"
                    checked={form.is_simulated ?? false}
                    onChange={e => setForm(f => ({ ...f, is_simulated: e.target.checked }))} />
                  Modo simulado
                </label>
              </div>
            </div>

            {/* Modal footer */}
            <div className="flex gap-2 px-5 py-4 border-t border-gray-100">
              <button onClick={() => setShowForm(false)} className="flex-1 border border-gray-200 text-gray-600 text-sm font-medium rounded-xl py-2.5 hover:bg-gray-50">
                Cancelar
              </button>
              <button onClick={handleSave} disabled={saving}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-semibold rounded-xl py-2.5 flex items-center justify-center gap-2">
                {saving ? <span className="loading loading-spinner loading-xs" /> : '💾 Salvar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Meta OAuth Modal */}
      {showOAuthModal && (
        <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl flex flex-col max-h-[90vh]">

            {/* Header */}
            <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100">
              <div className={`w-9 h-9 rounded-xl ${PROVIDERS[oauthProvider].color} flex items-center justify-center text-lg`}>
                {PROVIDERS[oauthProvider].icon}
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-gray-800 text-sm">Conectar {PROVIDERS[oauthProvider].label}</h3>
                <p className="text-xs text-gray-400">Via Business Portfolio — sem dados pessoais</p>
              </div>
              <button onClick={closeOAuthModal} className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-gray-100 text-gray-400 text-lg">✕</button>
            </div>

            {/* Body */}
            <div className="overflow-y-auto flex-1 px-5 py-6">

              {/* idle */}
              {oauthStep.status === 'idle' && (
                <div className="text-center space-y-4">
                  <p className="text-sm text-gray-600">
                    Autorize o acesso ao seu <strong>Business Portfolio</strong> na Meta.
                    O token gerado pertence à sua empresa e não expira.
                  </p>
                  <ul className="text-left text-xs text-gray-500 space-y-1">
                    <li>✓ Sem dados de conta pessoal coletados</li>
                    <li>✓ Webhooks configurados automaticamente</li>
                    <li>✓ Token vinculado ao Business Portfolio, não à pessoa</li>
                  </ul>
                  <button
                    onClick={startOAuth}
                    className="w-full flex items-center justify-center gap-2 bg-[#1877F2] hover:bg-[#166FE5] text-white font-semibold py-3 rounded-xl transition-colors"
                  >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                    </svg>
                    Continuar com Meta
                  </button>
                </div>
              )}

              {/* loading */}
              {oauthStep.status === 'loading' && (
                <div className="flex flex-col items-center gap-3 py-8">
                  <span className="loading loading-spinner loading-lg text-primary" />
                  <p className="text-sm text-gray-500">Autenticando com a Meta…</p>
                </div>
              )}

              {/* selecting */}
              {oauthStep.status === 'selecting' && (() => {
                const { discover } = oauthStep;
                return (
                  <div className="space-y-4">
                    <p className="text-xs text-gray-500">Selecione qual conta deseja conectar:</p>

                    {/* WhatsApp selection */}
                    {oauthProvider === 'whatsapp' && (() => {
                      const wabas = discover.assets as MetaWabaAsset[];
                      const waba = wabas[selectedWabaIdx];
                      return (
                        <div className="space-y-3">
                          {wabas.length > 1 && (
                            <div>
                              <label className="text-xs font-semibold text-gray-600 mb-1.5 block">WhatsApp Business Account</label>
                              <select
                                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-900 bg-white outline-none focus:border-blue-400"
                                value={selectedWabaIdx}
                                onChange={e => { setSelectedWabaIdx(+e.target.value); setSelectedPhoneIdx(0); }}
                              >
                                {wabas.map((w, i) => (
                                  <option key={w.waba_id} value={i}>{w.waba_name || w.waba_id}</option>
                                ))}
                              </select>
                            </div>
                          )}
                          {waba && (
                            <div>
                              <label className="text-xs font-semibold text-gray-600 mb-1.5 block">Número de telefone</label>
                              {waba.phone_numbers.length === 0 ? (
                                <p className="text-xs text-red-500">Nenhum número encontrado nesta WABA.</p>
                              ) : (
                                <div className="space-y-2">
                                  {waba.phone_numbers.map((ph, i) => (
                                    <label key={ph.id} className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all
                                      ${selectedPhoneIdx === i ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}>
                                      <input
                                        type="radio"
                                        name="phone"
                                        className="accent-blue-600"
                                        checked={selectedPhoneIdx === i}
                                        onChange={() => setSelectedPhoneIdx(i)}
                                      />
                                      <div>
                                        <p className="text-sm font-medium text-gray-800">{ph.display_phone_number}</p>
                                        <p className="text-xs text-gray-400">{ph.verified_name}</p>
                                      </div>
                                    </label>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })()}

                    {/* Facebook / Messenger / Instagram selection */}
                    {oauthProvider !== 'whatsapp' && (() => {
                      const pages = discover.assets as MetaPageAsset[];
                      return (
                        <div className="space-y-2">
                          {pages.length === 0 ? (
                            <p className="text-xs text-red-500">Nenhuma Página encontrada para este usuário.</p>
                          ) : pages.map((pg, i) => (
                            <label key={pg.id} className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all
                              ${selectedPageIdx === i ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}>
                              <input
                                type="radio"
                                name="page"
                                className="accent-blue-600 mt-0.5"
                                checked={selectedPageIdx === i}
                                onChange={() => setSelectedPageIdx(i)}
                              />
                              <div>
                                <p className="text-sm font-medium text-gray-800">{pg.name}</p>
                                {pg.instagram_business_account && (
                                  <p className="text-xs text-gray-400">Instagram: @{pg.instagram_business_account.username}</p>
                                )}
                              </div>
                            </label>
                          ))}
                        </div>
                      );
                    })()}

                    {/* Name override */}
                    <div>
                      <label className="text-xs font-semibold text-gray-600 mb-1.5 block">Nome do canal (opcional)</label>
                      <input
                        type="text"
                        placeholder="Ex: WhatsApp Principal"
                        className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-900 bg-white outline-none focus:border-blue-400"
                        value={channelName}
                        onChange={e => setChannelName(e.target.value)}
                      />
                    </div>
                  </div>
                );
              })()}

              {/* finalizing */}
              {oauthStep.status === 'finalizing' && (
                <div className="flex flex-col items-center gap-3 py-8">
                  <span className="loading loading-spinner loading-lg text-primary" />
                  <p className="text-sm text-gray-500">Configurando webhooks e salvando canal…</p>
                </div>
              )}

              {/* done */}
              {oauthStep.status === 'done' && (
                <div className="text-center space-y-3 py-4">
                  <div className="text-5xl">✅</div>
                  <p className="font-semibold text-gray-800">Canal conectado!</p>
                  <p className="text-sm text-gray-500">
                    <strong>{oauthStep.channelName}</strong> foi configurado com sucesso.
                    Webhooks ativos e canal pronto para uso.
                  </p>
                </div>
              )}

              {/* error */}
              {oauthStep.status === 'error' && (
                <div className="space-y-4">
                  <div className="bg-red-50 border border-red-100 rounded-xl px-4 py-3 text-xs text-red-700">
                    {oauthStep.message}
                  </div>
                  <button
                    onClick={() => setOauthStep({ status: 'idle' })}
                    className="w-full border border-gray-200 text-gray-600 text-sm font-medium rounded-xl py-2.5 hover:bg-gray-50"
                  >
                    Tentar novamente
                  </button>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex gap-2 px-5 py-4 border-t border-gray-100">
              <button onClick={closeOAuthModal} className="flex-1 border border-gray-200 text-gray-600 text-sm font-medium rounded-xl py-2.5 hover:bg-gray-50">
                {oauthStep.status === 'done' ? 'Fechar' : 'Cancelar'}
              </button>
              {oauthStep.status === 'selecting' && (
                <button
                  onClick={finalizeOAuth}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-xl py-2.5"
                >
                  Conectar e configurar
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Success toast */}
      {success && (
        <div className="fixed bottom-6 right-6 z-50 bg-emerald-600 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg flex items-center gap-2">
          ✅ {success}
          <button onClick={() => setSuccess('')} className="ml-2 text-white/70 hover:text-white">✕</button>
        </div>
      )}
    </div>
  );
}
