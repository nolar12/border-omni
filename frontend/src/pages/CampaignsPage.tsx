import { useEffect, useState, useRef } from 'react';
import { leadsService } from '../services/leads';
import { messageTemplatesService } from '../services/messageTemplates';
import { mediaUploadService } from '../services/mediaUpload';
import type { LeadListItem, MessageTemplate } from '../types';

type SendStatus = 'pending' | 'sending' | 'success' | 'error';

interface LeadResult {
  status: SendStatus;
  errorMsg?: string;
}

type Phase = 'setup' | 'sending' | 'done';

const STATUS_LABELS: Record<string, string> = {
  NEW: 'Novo',
  QUALIFYING: 'Qualificando',
  QUALIFIED: 'Qualificado',
  HANDOFF: 'Handoff',
  CLOSED: 'Fechado',
};

const TIER_COLORS: Record<string, string> = {
  A: 'bg-green-100 text-green-700',
  B: 'bg-blue-100 text-blue-700',
  C: 'bg-gray-100 text-gray-600',
};

const CATEGORY_LABELS: Record<string, string> = {
  MARKETING: 'Marketing',
  UTILITY: 'Utilitário',
  AUTHENTICATION: 'Autenticação',
};

function detectChannel(channels_used: string): string {
  const raw = (channels_used || '').toLowerCase();
  if (raw.includes('instagram')) return 'instagram';
  if (raw.includes('facebook') || raw.includes('messenger')) return 'facebook';
  return 'whatsapp';
}

function ChannelBadge({ channels_used }: { channels_used: string }) {
  const ch = detectChannel(channels_used);
  if (ch === 'instagram')
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-700">
        <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z" />
        </svg>
        Instagram
      </span>
    );
  if (ch === 'facebook')
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700">
        <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
        </svg>
        Facebook
      </span>
    );
  return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700">
      <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="currentColor">
        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413z" />
      </svg>
      WhatsApp
    </span>
  );
}

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
        ),
      )}
    </span>
  );
}

function SpinnerIcon() {
  return (
    <svg className="w-4 h-4 animate-spin text-blue-500" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg className="w-4 h-4 text-green-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg className="w-4 h-4 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

const ACCEPT_BY_TYPE: Record<string, string> = {
  IMAGE:    'image/jpeg,image/png,image/webp',
  VIDEO:    'video/mp4,video/3gpp',
  DOCUMENT: 'application/pdf',
};

interface CampaignMediaFieldProps {
  headerType: string;
  value: string;
  onChange: (url: string) => void;
  disabled?: boolean;
}

function CampaignMediaField({ headerType, value, onChange, disabled }: CampaignMediaFieldProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const typeLabel = headerType === 'IMAGE' ? 'imagem' : headerType === 'VIDEO' ? 'vídeo' : 'documento';

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError('');
    setUploading(true);
    try {
      const result = await mediaUploadService.upload(file);
      onChange(result.url);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Erro no upload. Tente novamente.';
      setUploadError(msg);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div className="space-y-2">
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPT_BY_TYPE[headerType] ?? '*/*'}
        className="hidden"
        onChange={handleFileChange}
        disabled={disabled || uploading}
      />

      {/* Preview compacto */}
      {value && (
        <div className="rounded-lg overflow-hidden border border-gray-200 bg-gray-50 relative">
          {headerType === 'IMAGE' && (
            <img
              src={value}
              alt="Mídia"
              className="w-full max-h-32 object-cover"
              onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
          )}
          {headerType === 'VIDEO' && (
            <video src={value} controls className="w-full max-h-32" />
          )}
          {headerType === 'DOCUMENT' && (
            <div className="flex items-center gap-2 px-3 py-2 text-[10px] text-gray-600">
              <svg className="w-4 h-4 text-red-500 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              <span className="truncate">{value.split('/').pop()}</span>
            </div>
          )}
          {!disabled && (
            <button
              type="button"
              onClick={() => onChange('')}
              className="absolute top-1 right-1 w-5 h-5 bg-black/50 hover:bg-black/70 text-white rounded-full flex items-center justify-center"
            >
              <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          )}
        </div>
      )}

      {!disabled && (
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-400 hover:bg-blue-50 disabled:opacity-50 transition-colors text-gray-500 hover:text-blue-600"
        >
          {uploading ? (
            <>
              <svg className="w-3.5 h-3.5 animate-spin text-blue-500" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
              </svg>
              Enviando...
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
              {value ? `Trocar ${typeLabel}` : `Anexar ${typeLabel}`}
              {!value && <span className="text-red-400 font-medium">(obrigatório)</span>}
            </>
          )}
        </button>
      )}

      {uploadError && (
        <p className="text-[10px] text-red-600 bg-red-50 rounded px-2 py-1">{uploadError}</p>
      )}
    </div>
  );
}

export default function CampaignsPage() {
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [leads, setLeads] = useState<LeadListItem[]>([]);
  const [loadingLeads, setLoadingLeads] = useState(true);
  const [loadingTemplates, setLoadingTemplates] = useState(true);

  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [variables, setVariables] = useState<string[]>([]);
  const [headerMediaUrl, setHeaderMediaUrl] = useState('');
  const [templateSearch, setTemplateSearch] = useState('');

  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterTier, setFilterTier] = useState('');

  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const [phase, setPhase] = useState<Phase>('setup');
  const [results, setResults] = useState<Map<number, LeadResult>>(new Map());
  const [sentCount, setSentCount] = useState(0);
  const [errorCount, setErrorCount] = useState(0);
  const abortRef = useRef(false);

  const selectedTemplate = templates.find(t => t.id === selectedTemplateId) ?? null;

  useEffect(() => {
    messageTemplatesService
      .list()
      .then(data => {
        setTemplates(data.filter(t => t.status === 'APPROVED'));
        setLoadingTemplates(false);
      })
      .catch(() => setLoadingTemplates(false));
  }, []);

  useEffect(() => {
    const fetchAll = async () => {
      setLoadingLeads(true);
      const allLeads: LeadListItem[] = [];
      let page = 1;
      while (page <= 15) {
        const resp = await leadsService.getLeads({ page });
        allLeads.push(...resp.results);
        if (!resp.next) break;
        page++;
      }
      setLeads(allLeads);
      setLoadingLeads(false);
    };
    fetchAll().catch(() => setLoadingLeads(false));
  }, []);

  useEffect(() => {
    if (selectedTemplate) {
      setVariables(Array(selectedTemplate.variable_count).fill(''));
      setHeaderMediaUrl(selectedTemplate.header_media_url ?? '');
    } else {
      setVariables([]);
      setHeaderMediaUrl('');
    }
  }, [selectedTemplateId]);

  const filteredTemplates = templates.filter(
    t =>
      !templateSearch ||
      t.name.toLowerCase().includes(templateSearch.toLowerCase()) ||
      t.body_text.toLowerCase().includes(templateSearch.toLowerCase()),
  );

  const filteredLeads = leads.filter(l => {
    if (
      search &&
      !`${l.full_name ?? ''} ${l.phone}`.toLowerCase().includes(search.toLowerCase())
    )
      return false;
    if (filterStatus && l.status !== filterStatus) return false;
    if (filterTier && l.tier !== filterTier) return false;
    return true;
  });

  const toggleLead = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const allFilteredSelected =
    filteredLeads.length > 0 && filteredLeads.every(l => selectedIds.has(l.id));

  const toggleSelectAll = () => {
    if (allFilteredSelected) {
      setSelectedIds(prev => {
        const next = new Set(prev);
        filteredLeads.forEach(l => next.delete(l.id));
        return next;
      });
    } else {
      setSelectedIds(prev => {
        const next = new Set(prev);
        filteredLeads.forEach(l => next.add(l.id));
        return next;
      });
    }
  };

  const variablesComplete = variables.length === 0 || variables.every(v => v.trim() !== '');
  const headerRequired =
    selectedTemplate &&
    ['IMAGE', 'VIDEO', 'DOCUMENT'].includes(selectedTemplate.header_type);
  const canSend =
    selectedTemplate &&
    selectedIds.size > 0 &&
    variablesComplete &&
    (!headerRequired || headerMediaUrl.trim() !== '');

  const sendCampaign = async () => {
    if (!selectedTemplate) return;
    abortRef.current = false;
    setPhase('sending');

    const leadIds = [...selectedIds];
    const initial = new Map<number, LeadResult>();
    leadIds.forEach(id => initial.set(id, { status: 'pending' }));
    setResults(new Map(initial));

    let sent = 0;
    let errors = 0;

    for (const leadId of leadIds) {
      if (abortRef.current) break;

      setResults(prev => new Map(prev).set(leadId, { status: 'sending' }));

      try {
        await leadsService.sendTemplate(
          leadId,
          selectedTemplate.id,
          variables,
          headerMediaUrl || undefined,
        );
        sent++;
        setSentCount(sent);
        setResults(prev => new Map(prev).set(leadId, { status: 'success' }));
      } catch (e: unknown) {
        errors++;
        const msg =
          (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          'Erro ao enviar';
        setErrorCount(errors);
        setResults(prev => new Map(prev).set(leadId, { status: 'error', errorMsg: msg }));
      }
    }

    setPhase('done');
  };

  const reset = () => {
    abortRef.current = false;
    setPhase('setup');
    setResults(new Map());
    setSentCount(0);
    setErrorCount(0);
  };

  const totalToSend = selectedIds.size;
  const processed = sentCount + errorCount;
  const progress = totalToSend > 0 ? Math.round((processed / totalToSend) * 100) : 0;

  return (
    <div className="flex flex-col h-full min-h-0 bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Campanhas WhatsApp</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Envie templates aprovados para um grupo de leads via WhatsApp
            </p>
          </div>
          {phase === 'done' && (
            <button
              onClick={reset}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <polyline points="1 4 1 10 7 10" />
                <path d="M3.51 15a9 9 0 1 0 .49-3.95" />
              </svg>
              Nova Campanha
            </button>
          )}
        </div>

        {/* Progress bar (sending/done) */}
        {(phase === 'sending' || phase === 'done') && (
          <div className="mt-3">
            <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
              <span>
                {phase === 'sending'
                  ? `Enviando... ${processed} de ${totalToSend}`
                  : `Concluído — ${sentCount} enviados, ${errorCount} com erro`}
              </span>
              <span className="font-semibold">{progress}%</span>
            </div>
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${
                  phase === 'done'
                    ? errorCount === 0
                      ? 'bg-green-500'
                      : 'bg-yellow-500'
                    : 'bg-blue-500'
                }`}
                style={{ width: `${progress}%` }}
              />
            </div>
            {phase === 'done' && (
              <div className="flex gap-4 mt-2">
                <span className="flex items-center gap-1 text-xs text-green-600 font-medium">
                  <CheckIcon />
                  {sentCount} enviados com sucesso
                </span>
                {errorCount > 0 && (
                  <span className="flex items-center gap-1 text-xs text-red-600 font-medium">
                    <XIcon />
                    {errorCount} com falha
                  </span>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left: Template Config */}
        <div
          className="flex flex-col border-r border-gray-200 bg-white overflow-y-auto flex-shrink-0"
          style={{ width: 340 }}
        >
          <div className="p-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <svg className="w-4 h-4 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              1. Selecionar Template
            </h2>

            {/* Template search */}
            <div className="relative">
              <svg
                className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
              >
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                value={templateSearch}
                onChange={e => setTemplateSearch(e.target.value)}
                placeholder="Buscar template..."
                disabled={phase !== 'setup'}
                className="w-full pl-8 pr-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50 disabled:opacity-50"
              />
            </div>
          </div>

          {/* Template list */}
          <div className="flex-1 overflow-y-auto">
            {loadingTemplates ? (
              <div className="flex items-center justify-center py-10 text-gray-400 text-sm gap-2">
                <SpinnerIcon />
                Carregando templates...
              </div>
            ) : filteredTemplates.length === 0 ? (
              <div className="p-4 text-center text-sm text-gray-400">
                {templates.length === 0
                  ? 'Nenhum template aprovado. Crie e aprove templates na aba Templates WhatsApp.'
                  : 'Nenhum template encontrado.'}
              </div>
            ) : (
              <div className="p-2 space-y-1.5">
                {filteredTemplates.map(t => (
                  <button
                    key={t.id}
                    onClick={() =>
                      phase === 'setup' &&
                      setSelectedTemplateId(prev => (prev === t.id ? null : t.id))
                    }
                    disabled={phase !== 'setup'}
                    className={`w-full text-left rounded-lg p-3 border transition-all text-xs ${
                      selectedTemplateId === t.id
                        ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-400'
                        : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-gray-800 truncate">{t.name}</span>
                      <span className="ml-2 flex-shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">
                        {CATEGORY_LABELS[t.category] ?? t.category}
                      </span>
                    </div>
                    <p className="text-gray-500 line-clamp-2 leading-relaxed">{t.body_text}</p>
                    {t.variable_count > 0 && (
                      <span className="inline-block mt-1 text-[10px] text-blue-600 bg-blue-50 rounded px-1.5 py-0.5">
                        {t.variable_count} variável{t.variable_count !== 1 ? 'eis' : ''}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Variables & media config */}
          {selectedTemplate && (
            <div className="border-t border-gray-100 p-4 space-y-3 bg-gray-50">
              <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                Preview do Template
              </h3>
              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden text-xs text-gray-700 leading-relaxed">
                {/* Preview de mídia do cabeçalho */}
                {headerRequired && headerMediaUrl && (
                  selectedTemplate.header_type === 'IMAGE' ? (
                    <img
                      src={headerMediaUrl}
                      alt="Cabeçalho"
                      className="w-full max-h-40 object-cover"
                      onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                  ) : selectedTemplate.header_type === 'VIDEO' ? (
                    <video src={headerMediaUrl} controls className="w-full max-h-40" />
                  ) : (
                    <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-100 text-[10px] text-gray-600">
                      <svg className="w-3.5 h-3.5 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                      </svg>
                      <span className="truncate">{headerMediaUrl.split('/').pop()}</span>
                    </div>
                  )
                )}
                <div className="p-3">
                  {selectedTemplate.header_text && (
                    <p className="font-semibold mb-1">{selectedTemplate.header_text}</p>
                  )}
                  <VariableHighlight text={selectedTemplate.body_text} />
                  {selectedTemplate.footer_text && (
                    <p className="text-gray-400 mt-1 text-[10px]">{selectedTemplate.footer_text}</p>
                  )}
                </div>
              </div>

              {headerRequired && (
                <CampaignMediaField
                  headerType={selectedTemplate.header_type}
                  value={headerMediaUrl}
                  onChange={setHeaderMediaUrl}
                  disabled={phase !== 'setup'}
                />
              )}

              {selectedTemplate.variable_count > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                    Preencher Variáveis
                  </h3>
                  {variables.map((v, i) => (
                    <div key={i}>
                      <label className="block text-[10px] text-gray-500 mb-0.5">
                        Variável {`{{${i + 1}}}`}
                      </label>
                      <input
                        value={v}
                        onChange={e => {
                          const next = [...variables];
                          next[i] = e.target.value;
                          setVariables(next);
                        }}
                        disabled={phase !== 'setup'}
                        placeholder={`Valor para {{${i + 1}}}`}
                        className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right: Lead Selection */}
        <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
          {/* Filter bar */}
          <div className="px-4 py-3 bg-white border-b border-gray-100 flex-shrink-0">
            <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <svg className="w-4 h-4 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
              2. Selecionar Leads
              {selectedIds.size > 0 && (
                <span className="ml-auto text-xs font-semibold text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full">
                  {selectedIds.size} selecionado{selectedIds.size !== 1 ? 's' : ''}
                </span>
              )}
            </h2>
            <div className="flex gap-2 flex-wrap">
              <div className="relative flex-1 min-w-32">
                <svg
                  className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Buscar por nome ou telefone..."
                  disabled={phase !== 'setup'}
                  className="w-full pl-8 pr-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50 disabled:opacity-50"
                />
              </div>
              <select
                value={filterStatus}
                onChange={e => setFilterStatus(e.target.value)}
                disabled={phase !== 'setup'}
                className="px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50 disabled:opacity-50"
              >
                <option value="">Todos os status</option>
                {Object.entries(STATUS_LABELS).map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
              <select
                value={filterTier}
                onChange={e => setFilterTier(e.target.value)}
                disabled={phase !== 'setup'}
                className="px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50 disabled:opacity-50"
              >
                <option value="">Todos os tiers</option>
                <option value="A">Tier A</option>
                <option value="B">Tier B</option>
                <option value="C">Tier C</option>
              </select>
            </div>

            {/* Select all toolbar */}
            {phase === 'setup' && (
              <div className="flex items-center gap-3 mt-2 pt-2 border-t border-gray-100">
                <button
                  onClick={toggleSelectAll}
                  className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors"
                >
                  <div
                    className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                      allFilteredSelected
                        ? 'bg-blue-600 border-blue-600'
                        : filteredLeads.some(l => selectedIds.has(l.id))
                        ? 'bg-blue-200 border-blue-400'
                        : 'border-gray-300'
                    }`}
                  >
                    {allFilteredSelected && (
                      <svg className="w-2.5 h-2.5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                    {!allFilteredSelected && filteredLeads.some(l => selectedIds.has(l.id)) && (
                      <div className="w-2 h-0.5 bg-blue-600 rounded" />
                    )}
                  </div>
                  {allFilteredSelected ? 'Desmarcar todos' : 'Marcar todos'}
                  <span className="text-gray-400 font-normal">({filteredLeads.length})</span>
                </button>
                {selectedIds.size > 0 && (
                  <button
                    onClick={() => setSelectedIds(new Set())}
                    className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    Limpar seleção
                  </button>
                )}
                <span className="ml-auto text-xs text-gray-400">
                  {filteredLeads.length} lead{filteredLeads.length !== 1 ? 's' : ''} encontrado
                  {filteredLeads.length !== 1 ? 's' : ''}
                </span>
              </div>
            )}
          </div>

          {/* Lead list */}
          <div className="flex-1 overflow-y-auto">
            {loadingLeads ? (
              <div className="flex items-center justify-center py-16 text-gray-400 text-sm gap-2">
                <SpinnerIcon />
                Carregando leads...
              </div>
            ) : filteredLeads.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <svg className="w-12 h-12 text-gray-200 mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                </svg>
                <p className="text-gray-400 text-sm">Nenhum lead encontrado com os filtros aplicados.</p>
              </div>
            ) : (
              <>
                {/* Banner informativo multi-canal */}
                <div className="mx-4 mt-3 mb-1 flex items-start gap-2.5 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5 text-xs text-amber-800">
                  <svg className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <span>
                    <strong>WhatsApp:</strong> envia como template HSM aprovado.{' '}
                    <strong>Instagram / Facebook:</strong> envia o texto do template como mensagem de texto simples via DM (válido apenas dentro da janela de 24h de interação).
                  </span>
                </div>
              <table className="w-full text-xs mt-2">
                <thead className="bg-gray-50 border-b border-gray-200 sticky top-0">
                  <tr>
                    <th className="w-10 px-4 py-2.5" />
                    <th className="text-left px-3 py-2.5 text-gray-500 font-medium">Lead</th>
                    <th className="text-left px-3 py-2.5 text-gray-500 font-medium">Telefone</th>
                    <th className="text-left px-3 py-2.5 text-gray-500 font-medium">Status</th>
                    <th className="text-left px-3 py-2.5 text-gray-500 font-medium">Tier</th>
                    <th className="text-left px-3 py-2.5 text-gray-500 font-medium">Canal</th>
                    {phase !== 'setup' && (
                      <th className="text-left px-3 py-2.5 text-gray-500 font-medium">Resultado</th>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredLeads
                    .filter(l => phase === 'setup' || selectedIds.has(l.id))
                    .map(lead => {
                      const result = results.get(lead.id);
                      const isSelected = selectedIds.has(lead.id);
                      return (
                        <tr
                          key={lead.id}
                          onClick={() => phase === 'setup' && toggleLead(lead.id)}
                          className={`group transition-colors ${
                            phase === 'setup'
                              ? 'cursor-pointer hover:bg-blue-50'
                              : ''
                          } ${isSelected && phase === 'setup' ? 'bg-blue-50/60' : 'bg-white'}`}
                        >
                          <td className="px-4 py-2.5">
                            {phase === 'setup' ? (
                              <div
                                className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
                                  isSelected
                                    ? 'bg-blue-600 border-blue-600'
                                    : 'border-gray-300 group-hover:border-blue-400'
                                }`}
                              >
                                {isSelected && (
                                  <svg
                                    className="w-2.5 h-2.5 text-white"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth={3}
                                  >
                                    <polyline points="20 6 9 17 4 12" />
                                  </svg>
                                )}
                              </div>
                            ) : (
                              <div className="w-4 h-4 flex items-center justify-center">
                                {result?.status === 'pending' && (
                                  <div className="w-2 h-2 rounded-full bg-gray-300" />
                                )}
                                {result?.status === 'sending' && <SpinnerIcon />}
                                {result?.status === 'success' && <CheckIcon />}
                                {result?.status === 'error' && <XIcon />}
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            <span className="font-medium text-gray-800">
                              {lead.full_name || '—'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-gray-500 font-mono">{lead.phone}</td>
                          <td className="px-3 py-2.5">
                            <span className="px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">
                              {STATUS_LABELS[lead.status] ?? lead.status}
                            </span>
                          </td>
                          <td className="px-3 py-2.5">
                            {lead.tier ? (
                              <span
                                className={`px-1.5 py-0.5 rounded-full font-semibold ${TIER_COLORS[lead.tier] ?? 'bg-gray-100 text-gray-600'}`}
                              >
                                {lead.tier}
                              </span>
                            ) : (
                              <span className="text-gray-300">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            <ChannelBadge channels_used={lead.channels_used} />
                          </td>
                          {phase !== 'setup' && (
                            <td className="px-3 py-2.5">
                              {result?.status === 'success' && (
                                <span className="text-green-600">Enviado</span>
                              )}
                              {result?.status === 'error' && (
                                <span className="text-red-500" title={result.errorMsg}>
                                  Falhou
                                </span>
                              )}
                              {result?.status === 'sending' && (
                                <span className="text-blue-500">Enviando...</span>
                              )}
                              {result?.status === 'pending' && (
                                <span className="text-gray-400">Aguardando</span>
                              )}
                            </td>
                          )}
                        </tr>
                      );
                    })}
                </tbody>
              </table>
              </>
            )}
          </div>

          {/* Bottom action bar */}
          {phase === 'setup' && (
            <div className="flex-shrink-0 bg-white border-t border-gray-200 px-6 py-4 flex items-center justify-between gap-4">
              <div className="text-sm text-gray-500">
                {!selectedTemplate && (
                  <span className="flex items-center gap-1.5 text-amber-600">
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="8" x2="12" y2="12" />
                      <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                    Selecione um template aprovado
                  </span>
                )}
                {selectedTemplate && selectedIds.size === 0 && (
                  <span className="flex items-center gap-1.5 text-amber-600">
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="8" x2="12" y2="12" />
                      <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                    Selecione pelo menos um lead
                  </span>
                )}
                {selectedTemplate && selectedIds.size > 0 && !variablesComplete && (
                  <span className="flex items-center gap-1.5 text-amber-600">
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="8" x2="12" y2="12" />
                      <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                    Preencha todas as variáveis do template
                  </span>
                )}
                {selectedTemplate && selectedIds.size > 0 && variablesComplete && headerRequired && !headerMediaUrl && (
                  <span className="flex items-center gap-1.5 text-amber-600">
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="8" x2="12" y2="12" />
                      <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                    Informe a URL da mídia do cabeçalho
                  </span>
                )}
                {canSend && (
                  <span className="text-gray-500">
                    Template:{' '}
                    <strong className="text-gray-700">{selectedTemplate!.name}</strong>
                  </span>
                )}
              </div>
              <button
                onClick={sendCampaign}
                disabled={!canSend}
                className={`flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-semibold transition-all shadow-sm ${
                  canSend
                    ? 'bg-blue-600 hover:bg-blue-700 text-white'
                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                }`}
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
                Enviar campanha
                {selectedIds.size > 0 && (
                  <span
                    className={`ml-1 px-2 py-0.5 rounded-full text-xs font-bold ${
                      canSend ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-500'
                    }`}
                  >
                    {selectedIds.size}
                  </span>
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
