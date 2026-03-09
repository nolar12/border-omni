import { useEffect, useState } from 'react';
import { channelsService } from '../services/channels';
import type { ChannelProvider } from '../types';

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

const EMPTY_FORM = (provider: ProviderKey): FormData => ({
  name: '', provider, app_id: '', app_secret: '', access_token: '',
  phone_number_id: '', business_account_id: '', instagram_account_id: '',
  page_id: '', webhook_verify_token: '', webhook_url: '',
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

  function load() {
    channelsService.getAll().then(setChannels).finally(() => setLoading(false));
  }
  useEffect(() => { load(); }, []);

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

  const providerChannels = (p: ProviderKey) => channels.filter(c => c.provider === p);
  const meta = PROVIDERS[activeProvider];

  return (
    <div className="max-w-4xl space-y-6">

      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-gray-800">Integrações & Canais</h1>
        <p className="text-sm text-gray-500 mt-0.5">Configure suas contas da Meta para receber e enviar mensagens.</p>
      </div>

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
          <button
            onClick={() => openCreate(activeProvider)}
            className="flex-shrink-0 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-xl transition-colors"
          >
            + Adicionar
          </button>
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
          <p className="text-xs text-gray-400 mt-1 mb-4">Clique em "Adicionar" para conectar sua conta</p>
          <button onClick={() => openCreate(activeProvider)} className="bg-blue-600 text-white text-xs font-semibold px-4 py-2 rounded-xl">
            + Adicionar {meta.label.split(' ')[0]}
          </button>
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
                    </div>
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    <button onClick={() => openEdit(ch)} className="text-xs text-blue-600 hover:underline font-medium">Editar</button>
                    <button onClick={() => handleDelete(ch.id)} className="text-xs text-red-500 hover:underline font-medium">Excluir</button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Help box */}
      <div className="bg-blue-50 border border-blue-100 rounded-2xl p-4 text-sm text-blue-700">
        <p className="font-semibold mb-1">Como obter as credenciais?</p>
        <ol className="list-decimal list-inside space-y-0.5 text-xs text-blue-600">
          <li>Acesse <strong>developers.facebook.com</strong> e crie ou acesse seu aplicativo</li>
          <li>Em <strong>WhatsApp → Configuração</strong>, copie o Phone Number ID e o WABA ID</li>
          <li>Gere um token de acesso permanente no <strong>Meta Business Suite</strong></li>
          <li>Configure o Webhook apontando para sua URL pública com o token de verificação</li>
        </ol>
      </div>

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
                        onClick={() => setForm(f => ({ ...EMPTY_FORM(p), name: f.name }))}
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
              {PROVIDERS[form.provider as ProviderKey]?.fields.map(field => (
                <div key={String(field.key)}>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-semibold text-gray-600">{field.label}</label>
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
                  <div className="relative">
                    <input
                      type={field.secret && !showSecrets[String(field.key)] ? 'password' : 'text'}
                      placeholder={field.placeholder}
                      className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-900 bg-white outline-none focus:border-blue-400 pr-10"
                      value={(form as Record<string, string>)[String(field.key)] ?? ''}
                      onChange={e => setForm(f => ({ ...f, [field.key]: e.target.value }))}
                    />
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
                  {field.help && <p className="text-xs text-gray-400 mt-1">{field.help}</p>}
                </div>
              ))}

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
