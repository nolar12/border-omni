import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { leadsService } from '../services/leads';
import { authService } from '../services/auth';
import type { LeadListItem, Lead, Message } from '../types';
import TierBadge from '../components/TierBadge';
import StatusBadge from '../components/StatusBadge';
import AIStatusBadge from '../components/AIStatusBadge';
import QuickReplyDrawer from '../components/QuickReplyDrawer';

// ─── Lead List Item (middle column) ──────────────────────────────────────────

function LeadRow({ lead, isActive, onClick }: { lead: LeadListItem; isActive: boolean; onClick: () => void }) {
  const name = lead.full_name || lead.phone;
  const initials = name.slice(0, 2).toUpperCase();
  const timeAgo = new Date(lead.updated_at).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });

  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-3 border-b border-gray-100 hover:bg-gray-50 transition-colors text-left ${
        isActive ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''
      }`}
    >
      {/* Avatar */}
      <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold ${
        lead.is_ai_active ? 'bg-blue-100 text-blue-600' : 'bg-green-100 text-green-600'
      }`}>
        {initials}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-1 mb-0.5">
          <p className="text-sm font-semibold text-gray-800 truncate">{name}</p>
          <span className="text-xs text-gray-400 flex-shrink-0">{timeAgo}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <TierBadge tier={lead.tier} />
          <StatusBadge status={lead.status} />
          {!lead.is_ai_active && lead.assigned_to && (
            <span className="text-xs text-gray-400 truncate">
              → {lead.assigned_to.first_name}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

// ─── Message Content renderer (texto, imagem, documento) ─────────────────────

function MessageContent({ text }: { text: string }) {
  // Detecta padrão: "🖼️ legenda\nhttps://..." ou "📄 legenda\nhttps://..."
  const lines = text.split('\n');
  const firstLine = lines[0] || '';
  const secondLine = lines[1] || '';
  const isMediaMsg = secondLine.startsWith('https://') && /[🖼️📄🎵🎥🎭📎]/.test(firstLine);

  if (isMediaMsg) {
    const isImage = firstLine.startsWith('🖼️');
    return (
      <div className="space-y-1">
        {isImage ? (
          <a href={secondLine} target="_blank" rel="noopener noreferrer">
            <img
              src={secondLine}
              alt={firstLine}
              className="max-w-[200px] rounded-lg border border-white/20 cursor-pointer hover:opacity-90"
              onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
          </a>
        ) : (
          <a
            href={secondLine}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 bg-white/20 rounded-lg px-3 py-2 hover:bg-white/30 transition-colors"
          >
            <span className="text-lg">{firstLine.slice(0, 2)}</span>
            <span className="text-sm underline truncate max-w-[160px]">
              {firstLine.slice(2).trim() || 'Abrir arquivo'}
            </span>
          </a>
        )}
      </div>
    );
  }

  return <p className="text-sm whitespace-pre-wrap break-words">{text}</p>;
}

// ─── Chat Panel (right column) ───────────────────────────────────────────────

function ChatPanel({ leadId, onBack }: { leadId: number; onBack: () => void }) {
  const [lead, setLead] = useState<Lead | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [msgText, setMsgText] = useState('');
  const [sending, setSending] = useState(false);
  const [assuming, setAssuming] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [showQR, setShowQR] = useState(false);
  const [sendingFile, setSendingFile] = useState(false);
  const [fileCaption, setFileCaption] = useState('');
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<'chat' | 'info' | 'notes'>('chat');
  const chatEndRef = useRef<HTMLDivElement>(null);
  const user = authService.getCurrentUser();

  useEffect(() => {
    setLoading(true);
    setTab('chat');
    Promise.all([
      leadsService.getLead(leadId),
      leadsService.getMessages(leadId),
    ]).then(([l, msgs]) => {
      setLead(l);
      setMessages(msgs);
    }).finally(() => setLoading(false));
  }, [leadId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleAssume() {
    if (!lead) return;
    setAssuming(true);
    try {
      const updated = await leadsService.assumeLead(lead.id);
      setLead(updated);
      const msgs = await leadsService.getMessages(lead.id);
      setMessages(msgs);
    } finally {
      setAssuming(false);
    }
  }

  async function handleRelease() {
    if (!lead) return;
    const updated = await leadsService.releaseLead(lead.id);
    setLead(updated);
  }

  async function handleSend() {
    if (!lead || !msgText.trim()) return;
    setSending(true);
    try {
      const msg = await leadsService.sendMessage(lead.id, msgText.trim());
      setMessages(prev => [...prev, msg]);
      setMsgText('');
    } finally {
      setSending(false);
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) setPendingFile(file);
    e.target.value = '';
  }

  async function handleSendFile() {
    if (!lead || !pendingFile) return;
    setSendingFile(true);
    try {
      const msg = await leadsService.sendFile(lead.id, pendingFile, fileCaption);
      setMessages(prev => [...prev, msg]);
      setPendingFile(null);
      setFileCaption('');
    } finally {
      setSendingFile(false);
    }
  }

  async function handleAddNote() {
    if (!lead || !noteText.trim()) return;
    await leadsService.addNote(lead.id, noteText.trim());
    const updated = await leadsService.getLead(lead.id);
    setLead(updated);
    setNoteText('');
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="loading loading-spinner loading-md text-primary" />
      </div>
    );
  }

  if (!lead) return null;

  const agentName = `${user?.first_name ?? ''} ${user?.last_name ?? ''}`.trim() || user?.email || '';

  return (
    <div className="flex-1 flex flex-col h-full bg-white min-w-0">
      {/* Chat Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 bg-white flex-shrink-0">
        {/* Back button (mobile) */}
        <button onClick={onBack} className="md:hidden flex items-center justify-center w-8 h-8 rounded-lg hover:bg-gray-100">
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>

        {/* Avatar */}
        <div className="w-9 h-9 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
          <span className="text-blue-600 font-bold text-sm">
            {(lead.full_name || lead.phone).slice(0, 2).toUpperCase()}
          </span>
        </div>

        {/* Lead info */}
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-800 text-sm truncate">
            {lead.full_name || lead.phone}
          </p>
          <p className="text-xs text-gray-400">{lead.phone}</p>
        </div>

        {/* Badges + actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="hidden sm:flex items-center gap-1.5">
            <TierBadge tier={lead.tier} />
            <AIStatusBadge isAiActive={lead.is_ai_active} assignedTo={lead.assigned_to} />
          </div>

          {lead.is_ai_active ? (
            <button
              onClick={handleAssume}
              disabled={assuming}
              className="btn btn-warning btn-xs hidden sm:flex"
            >
              {assuming ? <span className="loading loading-spinner loading-xs" /> : '🤝 Assumir'}
            </button>
          ) : (
            <button onClick={handleRelease} className="btn btn-ghost btn-xs text-blue-600 hidden sm:flex">
              🤖 IA
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-100 bg-white flex-shrink-0">
        {(['chat', 'info', 'notes'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2 text-xs font-semibold uppercase tracking-wide transition-colors ${
              tab === t
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            {t === 'chat' ? 'Chat' : t === 'info' ? 'Perfil' : 'Notas'}
          </button>
        ))}
      </div>

      {/* ── CHAT TAB ── */}
      {tab === 'chat' && (
        <>
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2 bg-gray-50">
            {messages.length === 0 && (
              <p className="text-center text-gray-400 text-xs pt-8">Nenhuma mensagem ainda.</p>
            )}
            {messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.direction === 'OUT' ? 'justify-end' : 'justify-start'}`}>
                <div className={msg.direction === 'OUT' ? 'chat-bubble-out' : 'chat-bubble-in'}>
                  <MessageContent text={msg.text} />
                  <p className={`text-[10px] mt-1 opacity-60 ${msg.direction === 'OUT' ? 'text-right' : ''}`}>
                    {new Date(msg.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          {/* Input area */}
          {!lead.is_ai_active ? (
            <div className="border-t border-gray-100 bg-white flex-shrink-0">

              {/* Preview de arquivo pendente */}
              {pendingFile && (
                <div className="flex items-center gap-2 px-3 pt-2 pb-1">
                  <div className="flex-1 flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-xl px-3 py-2">
                    <svg className="w-4 h-4 text-blue-500 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-gray-800 truncate">{pendingFile.name}</p>
                      <p className="text-xs text-gray-400">{(pendingFile.size / 1024).toFixed(0)} KB</p>
                    </div>
                    <button onClick={() => setPendingFile(null)} className="text-gray-400 hover:text-red-500 flex-shrink-0">
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                      </svg>
                    </button>
                  </div>
                  <button
                    onClick={handleSendFile}
                    disabled={sendingFile}
                    className="flex items-center justify-center w-9 h-9 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 transition-colors flex-shrink-0"
                  >
                    {sendingFile
                      ? <span className="loading loading-spinner loading-xs" />
                      : <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                    }
                  </button>
                </div>
              )}

              {/* Legenda opcional para o arquivo */}
              {pendingFile && (
                <div className="px-3 pb-1">
                  <input
                    type="text"
                    placeholder="Legenda (opcional)..."
                    className="w-full text-xs border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-blue-400 transition-colors"
                    value={fileCaption}
                    onChange={e => setFileCaption(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSendFile()}
                  />
                </div>
              )}

              {/* Barra principal de input */}
              <div className="px-3 py-2 flex gap-2">
                {/* Respostas rápidas */}
                <button
                  onClick={() => setShowQR(true)}
                  title="Respostas rápidas"
                  className="flex items-center justify-center w-8 h-8 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-blue-600 transition-colors flex-shrink-0"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                  </svg>
                </button>

                {/* Anexar arquivo */}
                <button
                  onClick={() => fileInputRef.current?.click()}
                  title="Enviar arquivo / documento"
                  className="flex items-center justify-center w-8 h-8 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-blue-600 transition-colors flex-shrink-0"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
                  </svg>
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png,.gif,.webp,.mp4,.mp3"
                  onChange={handleFileSelect}
                />

                <input
                  type="text"
                  placeholder="Digite sua mensagem..."
                  className="flex-1 text-sm border border-gray-200 rounded-xl px-3 py-2 outline-none focus:border-blue-400 transition-colors"
                  value={msgText}
                  onChange={e => setMsgText(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
                />
                <button
                  onClick={handleSend}
                  disabled={sending || !msgText.trim()}
                  className="flex items-center justify-center w-9 h-9 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 transition-colors flex-shrink-0"
                >
                  {sending
                    ? <span className="loading loading-spinner loading-xs" />
                    : (
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <line x1="22" y1="2" x2="11" y2="13"/>
                        <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                      </svg>
                    )
                  }
                </button>
              </div>
            </div>
          ) : (
            <div className="border-t border-gray-100 bg-blue-50 px-4 py-2.5 flex items-center gap-2 flex-shrink-0">
              <span className="text-blue-500 text-sm">🤖</span>
              <p className="text-xs text-blue-600 flex-1">
                IA respondendo automaticamente
              </p>
              <button
                onClick={handleAssume}
                disabled={assuming}
                className="btn btn-warning btn-xs"
              >
                {assuming ? <span className="loading loading-spinner loading-xs" /> : 'Assumir'}
              </button>
            </div>
          )}
        </>
      )}

      {/* ── INFO TAB ── */}
      {tab === 'info' && (
        <div className="flex-1 overflow-y-auto p-4 bg-white">
          {/* Mobile actions */}
          <div className="flex gap-2 mb-4 sm:hidden">
            <TierBadge tier={lead.tier} size="md" />
            <StatusBadge status={lead.status} />
            {lead.is_ai_active ? (
              <button onClick={handleAssume} className="btn btn-warning btn-xs">🤝 Assumir</button>
            ) : (
              <button onClick={handleRelease} className="btn btn-ghost btn-xs text-blue-600">🤖 IA</button>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2">
            {[
              ['Score', `${lead.score}/100`],
              ['Localização', lead.city ? `${lead.city}/${lead.state}` : '—'],
              ['Moradia', lead.housing_type === 'HOUSE' ? 'Casa' : lead.housing_type === 'APT' ? 'Apartamento' : '—'],
              ['Tempo/dia', lead.daily_time_minutes ? `${lead.daily_time_minutes}min` : '—'],
              ['Experiência', lead.experience_level?.replace(/_/g, ' ').toLowerCase() ?? '—'],
              ['Orçamento', lead.budget_ok ?? '—'],
              ['Timeline', lead.timeline ?? '—'],
              ['Finalidade', lead.purpose ?? '—'],
              ['Tem filhos', lead.has_kids ? 'Sim' : 'Não'],
              ['Tem pets', lead.has_other_pets ? 'Sim' : 'Não'],
              ['Fonte', lead.source],
              ['Estado IA', lead.conversation_state ?? '—'],
            ].map(([label, value]) => (
              <div key={label} className="bg-gray-50 rounded-lg p-2.5">
                <p className="text-xs text-gray-400 mb-0.5">{label}</p>
                <p className="text-sm font-medium text-gray-700 capitalize">{value}</p>
              </div>
            ))}
          </div>

          {lead.tags.length > 0 && (
            <div className="mt-3">
              <p className="text-xs text-gray-400 mb-1.5">Tags</p>
              <div className="flex flex-wrap gap-1.5">
                {lead.tags.map(tag => (
                  <span key={tag} className="badge badge-outline badge-sm">{tag}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── NOTES TAB ── */}
      {tab === 'notes' && (
        <div className="flex-1 overflow-y-auto p-4 bg-white">
          <div className="flex gap-2 mb-4">
            <textarea
              placeholder="Adicionar nota..."
              className="flex-1 text-sm border border-gray-200 rounded-xl px-3 py-2 outline-none focus:border-blue-400 resize-none"
              rows={2}
              value={noteText}
              onChange={e => setNoteText(e.target.value)}
            />
            <button
              onClick={handleAddNote}
              disabled={!noteText.trim()}
              className="btn btn-primary btn-sm self-end"
            >
              Salvar
            </button>
          </div>

          {lead.notes.length === 0 ? (
            <p className="text-center text-gray-400 text-sm py-4">Nenhuma nota.</p>
          ) : (
            <div className="space-y-2">
              {lead.notes.map(note => (
                <div key={note.id} className="bg-gray-50 rounded-xl p-3">
                  <p className="text-sm text-gray-700">{note.text}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    {note.author_name} · {new Date(note.created_at).toLocaleString('pt-BR')}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <QuickReplyDrawer
        isOpen={showQR}
        onClose={() => setShowQR(false)}
        onSelect={text => setMsgText(text)}
        userName={agentName}
        leadName={lead.full_name ?? ''}
      />
    </div>
  );
}

// ─── Main Page (3-column layout) ─────────────────────────────────────────────

type LeadFilter = {
  tier: string;
  status: string;
  is_ai_active: string;
  search: string;
};

const FILTER_DEFAULTS: LeadFilter = { tier: '', status: '', is_ai_active: '', search: '' };

export default function LeadsPage() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const selectedId = id ? Number(id) : null;

  const [leads, setLeads] = useState<LeadListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<LeadFilter>(FILTER_DEFAULTS);
  const [showFilters, setShowFilters] = useState(false);

  const load = useCallback((f: LeadFilter = filters, p: number = 1) => {
    setLoading(true);
    const params: Record<string, string | number | boolean> = { page: p };
    if (f.tier) params.tier = f.tier;
    if (f.status) params.status = f.status;
    if (f.is_ai_active) params.is_ai_active = f.is_ai_active === 'true';
    if (f.search) params.search = f.search;

    leadsService.getLeads(params as never)
      .then(data => {
        setLeads(p === 1 ? data.results : prev => [...prev, ...data.results]);
        setTotal(data.count);
        setHasMore(!!data.next);
        setPage(p);
      })
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => { load(); }, []);

  function applyFilter(key: keyof LeadFilter, value: string) {
    const next = { ...filters, [key]: value };
    setFilters(next);
    load(next, 1);
  }

  function clearFilters() {
    setFilters(FILTER_DEFAULTS);
    load(FILTER_DEFAULTS, 1);
  }

  const hasActiveFilters = Object.values(filters).some(v => v !== '');

  // On mobile, if a lead is selected, show only the chat
  const showMobileChat = selectedId !== null;
  const showMobileList = !showMobileChat;

  return (
    <div className="flex h-full bg-white">

      {/* ── Col 2: Leads List ── */}
      <div className={`
        flex flex-col border-r border-gray-100
        w-full md:w-72 lg:w-80 flex-shrink-0
        ${showMobileChat ? 'hidden md:flex' : 'flex'}
      `}>

        {/* List Header */}
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-gray-100 bg-white flex-shrink-0">
          <div>
            <p className="font-semibold text-sm text-gray-800">Leads</p>
            <p className="text-xs text-gray-400">{total} total</p>
          </div>
          <button
            onClick={() => setShowFilters(v => !v)}
            className={`flex items-center justify-center w-8 h-8 rounded-lg transition-colors ${
              hasActiveFilters ? 'bg-blue-100 text-blue-600' : 'text-gray-400 hover:bg-gray-100'
            }`}
            title="Filtros"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
            </svg>
          </button>
        </div>

        {/* Search */}
        <div className="px-3 py-2 border-b border-gray-100 flex-shrink-0">
          <div className="relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              type="search"
              placeholder="Buscar..."
              className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-blue-400 bg-gray-50"
              value={filters.search}
              onChange={e => applyFilter('search', e.target.value)}
            />
          </div>
        </div>

        {/* Filter dropdowns (collapsible) */}
        {showFilters && (
          <div className="px-3 py-2 border-b border-gray-100 bg-gray-50 flex flex-wrap gap-2 flex-shrink-0">
            <select
              className="text-xs border border-gray-200 rounded-lg px-2 py-1 bg-white outline-none flex-1 min-w-[80px]"
              value={filters.tier}
              onChange={e => applyFilter('tier', e.target.value)}
            >
              <option value="">Tier</option>
              <option value="A">A</option>
              <option value="B">B</option>
              <option value="C">C</option>
            </select>
            <select
              className="text-xs border border-gray-200 rounded-lg px-2 py-1 bg-white outline-none flex-1 min-w-[90px]"
              value={filters.status}
              onChange={e => applyFilter('status', e.target.value)}
            >
              <option value="">Status</option>
              <option value="NEW">Novo</option>
              <option value="QUALIFYING">Qualif.</option>
              <option value="QUALIFIED">Qualif.✓</option>
              <option value="HANDOFF">Handoff</option>
              <option value="CLOSED">Fechado</option>
            </select>
            <select
              className="text-xs border border-gray-200 rounded-lg px-2 py-1 bg-white outline-none flex-1 min-w-[80px]"
              value={filters.is_ai_active}
              onChange={e => applyFilter('is_ai_active', e.target.value)}
            >
              <option value="">IA</option>
              <option value="true">Ativa</option>
              <option value="false">Humano</option>
            </select>
            {hasActiveFilters && (
              <button onClick={clearFilters} className="text-xs text-red-500 hover:underline">Limpar</button>
            )}
          </div>
        )}

        {/* Lead list */}
        <div className="flex-1 overflow-y-auto">
          {loading && leads.length === 0 ? (
            <div className="flex justify-center py-10">
              <span className="loading loading-spinner loading-md text-primary" />
            </div>
          ) : leads.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-gray-400">
              <p className="text-3xl mb-2">🔍</p>
              <p className="text-sm">Nenhum lead encontrado</p>
            </div>
          ) : (
            <>
              {leads.map(lead => (
                <LeadRow
                  key={lead.id}
                  lead={lead}
                  isActive={selectedId === lead.id}
                  onClick={() => navigate(`/leads/${lead.id}`)}
                />
              ))}
              {hasMore && (
                <button
                  onClick={() => load(filters, page + 1)}
                  className="w-full py-3 text-xs text-blue-600 hover:bg-gray-50 border-t"
                  disabled={loading}
                >
                  {loading ? <span className="loading loading-spinner loading-xs" /> : 'Carregar mais'}
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Col 3: Chat / Detail ── */}
      <div className={`
        flex-1 flex flex-col min-w-0
        ${showMobileList && !selectedId ? 'hidden md:flex' : 'flex'}
      `}>
        {selectedId ? (
          <ChatPanel
            key={selectedId}
            leadId={selectedId}
            onBack={() => navigate('/leads')}
          />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-gray-300 select-none">
            <svg className="w-16 h-16 mb-4 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1}>
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            <p className="text-sm font-medium">Selecione um lead</p>
            <p className="text-xs mt-1">Escolha uma conversa na lista ao lado</p>
          </div>
        )}
      </div>
    </div>
  );
}
