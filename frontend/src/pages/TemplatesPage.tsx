import { useEffect, useRef, useState } from 'react';
import { messageTemplatesService, type CreateTemplatePayload } from '../services/messageTemplates';
import { mediaUploadService } from '../services/mediaUpload';
import { channelsService } from '../services/channels';
import api from '../services/api';
import type { MessageTemplate, TemplateCategory, TemplateHeaderType, TemplateStatus, ChannelProvider } from '../types';

const HEADER_TYPE_OPTIONS: { value: TemplateHeaderType; label: string; icon: string; description: string }[] = [
  { value: 'NONE',     label: 'Sem cabeçalho', icon: '—',  description: 'Somente texto no corpo' },
  { value: 'TEXT',     label: 'Texto',          icon: 'T',  description: 'Título em texto simples' },
  { value: 'IMAGE',    label: 'Imagem',          icon: '🖼', description: 'Foto JPEG/PNG enviada no momento do envio' },
  { value: 'VIDEO',    label: 'Vídeo',           icon: '▶', description: 'Vídeo MP4 enviado no momento do envio' },
  { value: 'DOCUMENT', label: 'Documento',       icon: '📄', description: 'PDF ou arquivo enviado no momento do envio' },
];

const CATEGORY_OPTIONS: { value: TemplateCategory; label: string; description: string }[] = [
  { value: 'UTILITY', label: 'Utilitário', description: 'Confirmações, atualizações, lembretes' },
  { value: 'MARKETING', label: 'Marketing', description: 'Promoções, ofertas, novidades' },
  { value: 'AUTHENTICATION', label: 'Autenticação', description: 'Senhas, códigos de verificação' },
];

const LANGUAGE_OPTIONS = [
  { value: 'pt_BR', label: 'Português (Brasil)' },
  { value: 'en_US', label: 'English (US)' },
  { value: 'es_ES', label: 'Español (España)' },
];

const STATUS_CONFIG: Record<TemplateStatus, { label: string; color: string; bg: string }> = {
  DRAFT:    { label: 'Rascunho', color: 'text-slate-600', bg: 'bg-slate-100' },
  APPROVED: { label: 'Aprovado', color: 'text-green-700', bg: 'bg-green-100' },
  PENDING:  { label: 'Pendente', color: 'text-yellow-700', bg: 'bg-yellow-100' },
  REJECTED: { label: 'Rejeitado', color: 'text-red-700', bg: 'bg-red-100' },
  PAUSED:   { label: 'Pausado', color: 'text-orange-700', bg: 'bg-orange-100' },
  DISABLED: { label: 'Desativado', color: 'text-gray-600', bg: 'bg-gray-100' },
};

const MEDIA_LIMITS: Record<string, string> = {
  IMAGE:    'JPEG ou PNG • máx 5 MB',
  VIDEO:    'MP4 • máx 16 MB • até ~3 min',
  DOCUMENT: 'PDF • máx 100 MB',
};

const EMPTY_FORM: CreateTemplatePayload = {
  name: '',
  language: 'pt_BR',
  category: 'UTILITY',
  header_type: 'NONE',
  header_text: '',
  header_media_url: '',
  body_text: '',
  footer_text: '',
  channel: null,
};

function VariableHighlight({ text }: { text: string }) {
  const parts = text.split(/(\{\{\d+\}\})/g);
  return (
    <span>
      {parts.map((part, i) =>
        /\{\{\d+\}\}/.test(part) ? (
          <span key={i} className="bg-blue-100 text-blue-700 rounded px-0.5 font-mono text-xs">
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </span>
  );
}

const ACCEPT_BY_TYPE: Record<string, string> = {
  IMAGE:    'image/jpeg,image/png,image/webp',
  VIDEO:    'video/mp4,video/3gpp',
  DOCUMENT: 'application/pdf',
};

interface MediaUploadFieldProps {
  headerType: string;
  value: string;
  onChange: (url: string) => void;
  disabled?: boolean;
}

function MediaUploadField({ headerType, value, onChange, disabled }: MediaUploadFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    setUploading(true);
    try {
      const result = await mediaUploadService.upload(file);
      onChange(result.url);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Erro ao fazer upload. Tente novamente.';
      setError(msg);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const limits = MEDIA_LIMITS[headerType] ?? '';
  const accept = ACCEPT_BY_TYPE[headerType] ?? '*/*';
  const typeLabel = headerType === 'IMAGE' ? 'imagem' : headerType === 'VIDEO' ? 'vídeo' : 'documento';

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={handleFileChange}
        disabled={disabled || uploading}
      />

      {/* Preview */}
      {value && (
        <div className="rounded-xl overflow-hidden border border-gray-200 bg-gray-50 relative group">
          {headerType === 'IMAGE' && (
            <img
              src={value}
              alt="Preview"
              className="w-full max-h-48 object-cover"
              onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
          )}
          {headerType === 'VIDEO' && (
            <video src={value} controls className="w-full max-h-48" />
          )}
          {headerType === 'DOCUMENT' && (
            <div className="flex items-center gap-2 px-3 py-3 text-sm text-gray-700">
              <svg className="w-5 h-5 text-red-500 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10 9 9 9 8 9"/>
              </svg>
              <span className="truncate text-xs">{value.split('/').pop()}</span>
            </div>
          )}
          {/* Botão de remover */}
          {!disabled && (
            <button
              type="button"
              onClick={() => onChange('')}
              className="absolute top-2 right-2 w-6 h-6 bg-black/50 hover:bg-black/70 text-white rounded-full flex items-center justify-center transition-colors"
              title="Remover mídia"
            >
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          )}
        </div>
      )}

      {/* Botões de ação */}
      {!disabled && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 px-3 py-2 text-sm border border-gray-200 rounded-xl bg-white hover:bg-gray-50 disabled:opacity-50 transition-colors font-medium text-gray-700"
          >
            {uploading ? (
              <>
                <svg className="w-4 h-4 animate-spin text-blue-500" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                </svg>
                Enviando...
              </>
            ) : (
              <>
                <svg className="w-4 h-4 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                {value ? `Trocar ${typeLabel}` : `Anexar ${typeLabel}`}
              </>
            )}
          </button>
          <span className="text-xs text-gray-400">{limits}</span>
        </div>
      )}

      {error && (
        <p className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-1.5">{error}</p>
      )}
    </div>
  );
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [channels, setChannels] = useState<ChannelProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<MessageTemplate | null>(null);
  const [form, setForm] = useState<CreateTemplatePayload>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [syncingAll, setSyncingAll] = useState(false);
  const [submittingId, setSubmittingId] = useState<number | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);
  const [mediaBaseUrl, setMediaBaseUrl] = useState('');
  const [linkingId, setLinkingId] = useState<number | null>(null);
  const [linkInput, setLinkInput] = useState('');
  const [linkSaving, setLinkSaving] = useState(false);

  const showToast = (msg: string, type: 'success' | 'error' = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const loadAll = async () => {
    setLoading(true);
    try {
      const [tmpl, ch, cfg] = await Promise.all([
        messageTemplatesService.list(),
        channelsService.getAll(),
        api.get<{ media_base_url: string }>('/server-config/').then(r => r.data).catch(() => ({ media_base_url: '' })),
      ]);
      setTemplates(tmpl);
      setChannels(ch.filter(c => c.provider === 'whatsapp'));
      setMediaBaseUrl(cfg.media_base_url);
    } catch {
      showToast('Erro ao carregar templates.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM, channel: channels[0]?.id ?? null });
    setShowModal(true);
  };

  const openEdit = (t: MessageTemplate) => {
    setEditing(t);
    setForm({
      name: t.name,
      language: t.language,
      category: t.category,
      header_type: t.header_type,
      header_text: t.header_text,
      header_media_url: t.header_media_url ?? '',
      body_text: t.body_text,
      footer_text: t.footer_text,
      channel: t.channel,
    });
    setShowModal(true);
  };

  const handleSave = async (mode: 'draft' | 'submit') => {
    if (!form.name.trim() || !form.body_text.trim()) {
      showToast('Nome e corpo são obrigatórios.', 'error');
      return;
    }
    if (!/^[a-z0-9_]+$/.test(form.name)) {
      showToast('Nome deve conter apenas letras minúsculas, números e underscores.', 'error');
      return;
    }
    setSaving(true);
    const payload = { ...form, draft: mode === 'draft' };
    try {
      if (editing) {
        await messageTemplatesService.update(editing.id, payload);
        showToast(mode === 'draft' ? 'Rascunho salvo.' : 'Template atualizado e reenviado para aprovação.');
      } else {
        await messageTemplatesService.create(payload);
        showToast(mode === 'draft' ? 'Rascunho salvo com sucesso!' : 'Template criado e enviado para aprovação na Meta!');
      }
      setShowModal(false);
      loadAll();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Erro ao salvar template.';
      showToast(msg, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleSubmitForApproval = async (t: MessageTemplate) => {
    setSubmittingId(t.id);
    try {
      const updated = await messageTemplatesService.submitForApproval(t.id);
      setTemplates(prev => prev.map(x => x.id === t.id ? updated : x));
      showToast('Template enviado para aprovação na Meta!');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Erro ao enviar para aprovação.';
      showToast(msg, 'error');
    } finally {
      setSubmittingId(null);
    }
  };

  const handleSync = async (t: MessageTemplate) => {
    setSyncingId(t.id);
    try {
      const updated = await messageTemplatesService.sync(t.id);
      setTemplates(prev => prev.map(x => x.id === t.id ? updated : x));
      showToast(`Status sincronizado: ${updated.status_display}`);
    } catch {
      showToast('Erro ao sincronizar com a Meta.', 'error');
    } finally {
      setSyncingId(null);
    }
  };

  const handleLinkMetaId = async (t: MessageTemplate) => {
    if (!linkInput.trim()) return;
    setLinkSaving(true);
    try {
      const updated = await messageTemplatesService.linkMetaId(t.id, linkInput.trim());
      setTemplates(prev => prev.map(x => x.id === t.id ? updated : x));
      setLinkingId(null);
      setLinkInput('');
      showToast(`Template vinculado com sucesso! Status: ${updated.status}`);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Erro ao vincular template.';
      showToast(msg, 'error');
    } finally {
      setLinkSaving(false);
    }
  };

  const handleSyncAll = async () => {
    setSyncingAll(true);
    try {
      const result = await messageTemplatesService.syncAll();
      const parts: string[] = [];
      if (result.updated.length) parts.push(`${result.updated.length} atualizado(s)`);
      if (result.imported.length) parts.push(`${result.imported.length} importado(s) da Meta`);
      showToast(parts.length ? parts.join(' • ') : 'Nenhuma alteração.');
      if (result.errors.length) showToast(result.errors[0], 'error');
      loadAll();
    } catch {
      showToast('Erro ao sincronizar todos.', 'error');
    } finally {
      setSyncingAll(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await messageTemplatesService.remove(id);
      setTemplates(prev => prev.filter(t => t.id !== id));
      showToast('Template excluído.');
    } catch {
      showToast('Erro ao excluir template.', 'error');
    } finally {
      setDeleteConfirm(null);
    }
  };

  const draftCount    = templates.filter(t => t.status === 'DRAFT').length;
  const approvedCount = templates.filter(t => t.status === 'APPROVED').length;
  const pendingCount  = templates.filter(t => t.status === 'PENDING').length;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-lg text-sm font-medium
          ${toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'}`}>
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Templates WhatsApp</h1>
          <p className="text-base text-gray-500 mt-1">
            Templates HSM aprovados pela Meta — necessários para enviar mensagens após 24h sem resposta.
          </p>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <button
            onClick={handleSyncAll}
            disabled={syncingAll}
            className="flex items-center gap-2 px-3 py-2 text-sm border border-gray-200 rounded-xl bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            <svg className={`w-4 h-4 ${syncingAll ? 'animate-spin' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
            {syncingAll ? 'Sincronizando...' : 'Sincronizar todos'}
          </button>
          <button
            onClick={openCreate}
            className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-xl hover:bg-blue-700 font-medium"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            Novo Template
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          { label: 'Total', value: templates.length, color: 'text-gray-900' },
          { label: 'Rascunhos', value: draftCount, color: 'text-slate-500' },
          { label: 'Aprovados', value: approvedCount, color: 'text-green-600' },
          { label: 'Pendentes', value: pendingCount, color: 'text-yellow-600' },
          { label: 'Rejeitados', value: templates.filter(t => t.status === 'REJECTED').length, color: 'text-red-600' },
        ].map(stat => (
          <div key={stat.label} className="bg-white rounded-xl border border-gray-200 px-4 py-3">
            <p className="text-sm text-gray-500">{stat.label}</p>
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Banner de domínio de mídia */}
      {mediaBaseUrl && (
        <div className={`border rounded-xl px-4 py-3 flex gap-3 ${
          mediaBaseUrl.includes('ngrok')
            ? 'bg-amber-50 border-amber-200'
            : 'bg-green-50 border-green-200'
        }`}>
          <svg className={`w-5 h-5 flex-shrink-0 mt-0.5 ${mediaBaseUrl.includes('ngrok') ? 'text-amber-500' : 'text-green-500'}`}
            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <div className="text-sm">
            <p className={`font-semibold ${mediaBaseUrl.includes('ngrok') ? 'text-amber-800' : 'text-green-800'}`}>
              {mediaBaseUrl.includes('ngrok') ? 'Domínio Ngrok ativo' : 'Domínio de mídia configurado'}
            </p>
            <p className={`mt-0.5 ${mediaBaseUrl.includes('ngrok') ? 'text-amber-700' : 'text-green-700'}`}>
              Mídias enviadas para a Meta usam o domínio:{' '}
              <code className="font-mono text-xs bg-black/10 px-1.5 py-0.5 rounded">{mediaBaseUrl}</code>
              {mediaBaseUrl.includes('ngrok') && (
                <span className="block mt-1 text-xs">
                  Ngrok funciona para testes, mas o domínio muda ao reiniciar (a menos que use domínio fixo).
                  Para produção, defina <code className="font-mono bg-black/10 px-1 rounded">MEDIA_BASE_URL</code> no <code className="font-mono bg-black/10 px-1 rounded">.env</code> com seu domínio HTTPS fixo.
                </span>
              )}
            </p>
          </div>
        </div>
      )}

      {/* 24h info banner */}
      <div className="bg-orange-50 border border-orange-200 rounded-xl px-4 py-3 flex gap-3">
        <svg className="w-5 h-5 text-orange-500 flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <div className="text-sm">
          <p className="font-semibold text-orange-800">Janela de 24h do WhatsApp</p>
          <p className="text-orange-700 mt-0.5">
            Após 24h sem resposta do usuário, a Meta bloqueia mensagens livres. Templates aprovados são a única forma de reabrir a conversa.
            Categoria <strong>UTILITY</strong> tem aprovação mais rápida e menor custo.
          </p>
        </div>
      </div>

      {/* Templates list */}
      {loading ? (
        <div className="text-center py-16 text-gray-400">Carregando templates...</div>
      ) : templates.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-2xl border border-dashed border-gray-200">
          <div className="w-14 h-14 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <p className="text-gray-600 font-medium">Nenhum template cadastrado</p>
          <p className="text-sm text-gray-400 mt-1">Crie o primeiro template para poder enviar mensagens após 24h</p>
          <button onClick={openCreate} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700">
            Criar template
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {templates.map(t => {
            const sc = STATUS_CONFIG[t.status] ?? STATUS_CONFIG.PENDING;
            return (
              <div key={t.id} className="bg-white rounded-2xl border border-gray-200 p-5">
                <div className="flex items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-sm font-semibold text-gray-900">{t.name}</span>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${sc.bg} ${sc.color}`}>
                        {sc.label}
                      </span>
                      <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                        {CATEGORY_OPTIONS.find(c => c.value === t.category)?.label ?? t.category}
                      </span>
                      <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                        {LANGUAGE_OPTIONS.find(l => l.value === t.language)?.label ?? t.language}
                      </span>
                      {t.header_type && t.header_type !== 'NONE' && (
                        <span className="text-xs text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full">
                          {HEADER_TYPE_OPTIONS.find(h => h.value === t.header_type)?.icon}{' '}
                          {HEADER_TYPE_OPTIONS.find(h => h.value === t.header_type)?.label}
                        </span>
                      )}
                      {t.variable_count > 0 && (
                        <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                          {t.variable_count} variável{t.variable_count !== 1 ? 'is' : ''}
                        </span>
                      )}
                    </div>

                    {t.header_type === 'TEXT' && t.header_text && (
                      <p className="mt-2 text-xs text-gray-500 font-medium uppercase tracking-wide">Cabeçalho</p>
                    )}
                    {t.header_type === 'TEXT' && t.header_text && (
                      <p className="text-sm text-gray-700">{t.header_text}</p>
                    )}
                    {t.header_type && ['IMAGE', 'VIDEO', 'DOCUMENT'].includes(t.header_type) && (
                      <div className="mt-2 max-w-xs">
                        {t.header_media_url ? (
                          t.header_type === 'IMAGE' ? (
                            <div className="rounded-lg overflow-hidden border border-gray-200">
                              <img
                                src={t.header_media_url}
                                alt="Cabeçalho"
                                className="w-full max-h-36 object-cover"
                                onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                              />
                            </div>
                          ) : t.header_type === 'VIDEO' ? (
                            <div className="rounded-lg overflow-hidden border border-gray-200">
                              <video src={t.header_media_url} controls className="w-full max-h-36" />
                            </div>
                          ) : (
                            <a
                              href={t.header_media_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5 text-xs text-blue-600 hover:bg-blue-50 transition-colors"
                            >
                              <svg className="w-4 h-4 text-red-500 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                                <polyline points="14 2 14 8 20 8"/>
                              </svg>
                              <span className="truncate">{t.header_media_url.split('/').pop() || 'Documento'}</span>
                            </a>
                          )
                        ) : (
                          <div className="flex items-center gap-2 text-xs text-gray-400 bg-gray-50 border border-dashed border-gray-200 rounded-lg px-3 py-1.5">
                            <span>{HEADER_TYPE_OPTIONS.find(h => h.value === t.header_type)?.icon}</span>
                            <span>Sem mídia anexada — adicione ao editar</span>
                          </div>
                        )}
                      </div>
                    )}

                    <p className="mt-2 text-sm text-gray-800 whitespace-pre-wrap line-clamp-3">
                      <VariableHighlight text={t.body_text} />
                    </p>

                    {t.footer_text && (
                      <p className="mt-1 text-xs text-gray-400 italic">{t.footer_text}</p>
                    )}

                    {t.rejection_reason && (
                      <p className="mt-2 text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">
                        <strong>Motivo da rejeição:</strong> {t.rejection_reason}
                      </p>
                    )}

                    <div className="mt-2 flex items-center gap-3 text-xs text-gray-400">
                      {t.channel_name && <span>Canal: {t.channel_name}</span>}
                      {t.meta_template_id && <span>Meta ID: {t.meta_template_id}</span>}
                    </div>
                  </div>

                  <div className="flex flex-col gap-2 flex-shrink-0">
                    {t.status === 'DRAFT' ? (
                      <>
                        <button
                          onClick={() => handleSubmitForApproval(t)}
                          disabled={submittingId === t.id}
                          title="Enviar para aprovação na Meta via API"
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium disabled:opacity-50 whitespace-nowrap"
                        >
                          {submittingId === t.id ? (
                            <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                            </svg>
                          ) : (
                            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                              <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                            </svg>
                          )}
                          {submittingId === t.id ? 'Enviando...' : 'Enviar para aprovação'}
                        </button>

                        {/* Vincular ID da Meta — para templates criados no Business Manager */}
                        {linkingId === t.id ? (
                          <div className="flex flex-col gap-1.5">
                            <input
                              type="text"
                              value={linkInput}
                              onChange={e => setLinkInput(e.target.value)}
                              placeholder="Cole o ID da Meta aqui"
                              className="text-xs border border-gray-300 rounded-lg px-2 py-1.5 w-44 focus:outline-none focus:ring-1 focus:ring-blue-400"
                              autoFocus
                            />
                            <div className="flex gap-1">
                              <button
                                onClick={() => handleLinkMetaId(t)}
                                disabled={linkSaving || !linkInput.trim()}
                                className="flex-1 px-2 py-1 text-xs bg-green-600 hover:bg-green-700 text-white rounded-lg disabled:opacity-50"
                              >
                                {linkSaving ? 'Vinculando...' : 'Vincular'}
                              </button>
                              <button
                                onClick={() => { setLinkingId(null); setLinkInput(''); }}
                                className="px-2 py-1 text-xs border border-gray-200 rounded-lg hover:bg-gray-50"
                              >
                                ✕
                              </button>
                            </div>
                          </div>
                        ) : (
                          <button
                            onClick={() => { setLinkingId(t.id); setLinkInput(''); }}
                            title="Criou o template no Meta Business Manager? Vincule o ID aqui"
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 text-gray-600 text-xs font-medium whitespace-nowrap"
                          >
                            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
                              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
                            </svg>
                            Vincular ID da Meta
                          </button>
                        )}
                      </>
                    ) : (
                      <button
                        onClick={() => handleSync(t)}
                        disabled={syncingId === t.id}
                        title="Sincronizar status com a Meta"
                        className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50"
                      >
                        <svg className={`w-4 h-4 text-gray-500 ${syncingId === t.id ? 'animate-spin' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                          <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                        </svg>
                      </button>
                    )}
                    <button
                      onClick={() => openEdit(t)}
                      title="Editar template"
                      className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50"
                    >
                      <svg className="w-4 h-4 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                      </svg>
                    </button>
                    {deleteConfirm === t.id ? (
                      <div className="flex gap-1">
                        <button onClick={() => handleDelete(t.id)} className="p-1.5 rounded-lg bg-red-500 text-white text-xs">
                          Sim
                        </button>
                        <button onClick={() => setDeleteConfirm(null)} className="p-1.5 rounded-lg border border-gray-200 text-xs">
                          Não
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setDeleteConfirm(t.id)}
                        title="Excluir template"
                        className="p-2 rounded-lg border border-gray-200 hover:bg-red-50"
                      >
                        <svg className="w-4 h-4 text-gray-400 hover:text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/>
                          <path d="M9 6V4h6v2"/>
                        </svg>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal de criação/edição */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">
                {editing ? 'Editar Template' : 'Novo Template'}
              </h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
              {/* Canal */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Canal WhatsApp</label>
                <select
                  value={form.channel ?? ''}
                  onChange={e => setForm(f => ({ ...f, channel: e.target.value ? Number(e.target.value) : null }))}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Sem canal vinculado</option>
                  {channels.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <p className="text-xs text-gray-400 mt-1">Necessário para enviar para aprovação na Meta.</p>
              </div>

              {/* Nome */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nome do template <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_') }))}
                  placeholder="reengajamento_24h"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-400 mt-1">Apenas letras minúsculas, números e underscores. Exigência da Meta.</p>
              </div>

              {/* Categoria e idioma */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Categoria</label>
                  <select
                    value={form.category}
                    onChange={e => setForm(f => ({ ...f, category: e.target.value as 'UTILITY' | 'MARKETING' | 'AUTHENTICATION' }))}
                    className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {CATEGORY_OPTIONS.map(c => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Idioma</label>
                  <select
                    value={form.language}
                    onChange={e => setForm(f => ({ ...f, language: e.target.value }))}
                    className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {LANGUAGE_OPTIONS.map(l => (
                      <option key={l.value} value={l.value}>{l.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Tipo de Cabeçalho */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Tipo de cabeçalho</label>
                <div className="grid grid-cols-5 gap-1.5">
                  {HEADER_TYPE_OPTIONS.map(opt => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setForm(f => ({
                        ...f,
                        header_type: opt.value,
                        header_text: opt.value !== 'TEXT' ? '' : f.header_text,
                        header_media_url: ['IMAGE', 'VIDEO', 'DOCUMENT'].includes(opt.value) ? f.header_media_url : '',
                      }))}
                      className={`flex flex-col items-center gap-1 px-2 py-2.5 rounded-xl border-2 text-center transition-colors ${
                        form.header_type === opt.value
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <span className="text-lg leading-none">{opt.icon}</span>
                      <span className="text-xs font-medium text-gray-700 leading-tight">{opt.label}</span>
                    </button>
                  ))}
                </div>
                {form.header_type && form.header_type !== 'NONE' && (
                  <p className="text-xs text-gray-400 mt-1.5">
                    {HEADER_TYPE_OPTIONS.find(o => o.value === form.header_type)?.description}
                  </p>
                )}
              </div>

              {/* Cabeçalho de texto (somente se TEXT) */}
              {form.header_type === 'TEXT' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Texto do cabeçalho</label>
                  <input
                    type="text"
                    value={form.header_text}
                    onChange={e => setForm(f => ({ ...f, header_text: e.target.value }))}
                    placeholder="Ex: Oferta especial para você!"
                    maxLength={60}
                    className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              )}

              {/* Upload de mídia para cabeçalho IMAGE/VIDEO/DOCUMENT */}
              {form.header_type && ['IMAGE', 'VIDEO', 'DOCUMENT'].includes(form.header_type) && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Mídia do cabeçalho
                  </label>
                  <MediaUploadField
                    headerType={form.header_type}
                    value={form.header_media_url ?? ''}
                    onChange={url => setForm(f => ({ ...f, header_media_url: url }))}
                  />
                  <p className="text-xs text-gray-400 mt-1.5">
                    Salva como padrão no rascunho. Será pré-preenchida na Campanha — pode trocar na hora do envio.
                  </p>
                </div>
              )}

              {/* Corpo */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Corpo <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={form.body_text}
                  onChange={e => setForm(f => ({ ...f, body_text: e.target.value }))}
                  rows={5}
                  placeholder={'Olá {{1}}! Sentimos sua falta 😊\n\nAinda está interessado em um Border Collie? Temos filhotes disponíveis.\n\nResponda essa mensagem para conversarmos!'}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Use <code className="bg-gray-100 px-1 rounded">{'{{1}}'}</code>, <code className="bg-gray-100 px-1 rounded">{'{{2}}'}</code> etc. para variáveis personalizadas (ex: nome do cliente).
                </p>
                {form.body_text && (
                  <div className="mt-2 bg-gray-50 rounded-xl px-3 py-2 text-sm text-gray-700">
                    <p className="text-xs text-gray-400 mb-1">Pré-visualização:</p>
                    <VariableHighlight text={form.body_text} />
                  </div>
                )}
              </div>

              {/* Rodapé */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Rodapé (opcional)</label>
                <input
                  type="text"
                  value={form.footer_text}
                  onChange={e => setForm(f => ({ ...f, footer_text: e.target.value }))}
                  placeholder="Ex: Responda PARAR para cancelar notificações"
                  maxLength={60}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Info da categoria selecionada */}
              {form.category && (
                <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 text-sm text-blue-700">
                  <strong>{CATEGORY_OPTIONS.find(c => c.value === form.category)?.label}:</strong>{' '}
                  {CATEGORY_OPTIONS.find(c => c.value === form.category)?.description}
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-between gap-3">
              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-xl hover:bg-gray-50"
              >
                Cancelar
              </button>
              <div className="flex gap-2">
                <button
                  onClick={() => handleSave('draft')}
                  disabled={saving}
                  className="px-4 py-2 text-sm text-slate-700 border border-gray-200 rounded-xl hover:bg-gray-50 font-medium disabled:opacity-50 flex items-center gap-2"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                    <polyline points="17 21 17 13 7 13 7 21"/>
                    <polyline points="7 3 7 8 15 8"/>
                  </svg>
                  Salvar rascunho
                </button>
                <button
                  onClick={() => handleSave('submit')}
                  disabled={saving}
                  className="px-5 py-2 text-sm bg-blue-600 text-white rounded-xl hover:bg-blue-700 font-medium disabled:opacity-50 flex items-center gap-2"
                >
                  {saving ? (
                    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                    </svg>
                  )}
                  {saving ? 'Enviando...' : editing ? 'Salvar e enviar para aprovação' : 'Enviar para aprovação'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
