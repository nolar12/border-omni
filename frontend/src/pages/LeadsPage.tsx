import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { leadsService } from '../services/leads';
import { authService } from '../services/auth';
import type { LeadListItem, Lead, Message, ChannelType } from '../types';
import TierBadge from '../components/TierBadge';
import StatusBadge from '../components/StatusBadge';
import AIStatusBadge from '../components/AIStatusBadge';
import QuickReplyDrawer from '../components/QuickReplyDrawer';

// ─── Lead List Item (middle column) ──────────────────────────────────────────

function LeadRow({ lead, isActive, onClick }: { lead: LeadListItem; isActive: boolean; onClick: () => void }) {
  const name = lead.full_name || lead.phone;
  const initials = name.slice(0, 2).toUpperCase();
  const timeAgo = new Date(lead.updated_at).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
  const needsReply = lead.last_message_direction === 'IN' && lead.status !== 'CLOSED';
  const isClosed = lead.status === 'CLOSED';

  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-3 border-b border-gray-100 transition-colors text-left ${
        isActive
          ? 'bg-blue-50 border-l-2 border-l-blue-500'
          : isClosed
            ? 'opacity-50 hover:opacity-70'
            : needsReply
              ? 'bg-amber-50 hover:bg-amber-100'
              : 'hover:bg-gray-50'
      }`}
    >
      {/* Avatar */}
      <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${
        isClosed
          ? 'bg-gray-100'
          : lead.is_ai_active
            ? 'bg-blue-50'
            : 'bg-green-50'
      }`}>
        <ChannelIcon
          channel={(lead.channels_used?.split(',')[0].trim() as ChannelType) || 'whatsapp'}
          size="md"
        />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-1 mb-0.5">
          <p className={`text-sm truncate ${
            isClosed
              ? 'font-normal text-gray-400'
              : needsReply
                ? 'font-bold text-gray-900'
                : 'font-semibold text-gray-800'
          }`}>
            {name}
          </p>
          <div className="flex items-center gap-1 flex-shrink-0">
            {needsReply && (
              <span className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" title="Aguardando resposta" />
            )}
            <span className="text-xs text-gray-400">{timeAgo}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {!isClosed && <TierBadge tier={lead.tier} />}
          {isClosed
            ? <StatusBadge status={lead.status} />
            : lead.lead_classification
              ? (
                <span className={`inline-flex items-center gap-0.5 text-xs font-semibold rounded-md px-1.5 py-0.5 ${
                  lead.lead_classification === 'HOT_LEAD'  ? 'bg-red-100 text-red-700'    :
                  lead.lead_classification === 'WARM_LEAD' ? 'bg-amber-100 text-amber-700' :
                                                             'bg-blue-100 text-blue-600'
                }`}>
                  {lead.lead_classification === 'HOT_LEAD' ? '🔥' : lead.lead_classification === 'WARM_LEAD' ? '🟡' : '❄️'}
                  {lead.lead_classification === 'HOT_LEAD' ? 'Hot' : lead.lead_classification === 'WARM_LEAD' ? 'Warm' : 'Cold'}
                </span>
              )
              : <StatusBadge status={lead.status} />
          }
          {!lead.is_ai_active && lead.assigned_to && !isClosed && (
            <span className="text-xs text-gray-400 truncate">
              → {lead.assigned_to.first_name}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

// ─── Message Status Icon (✓ ✓✓ lido) ─────────────────────────────────────────

type MsgStatus = 'sent' | 'delivered' | 'read' | 'failed' | null;

function MessageStatusIcon({ status }: { status: MsgStatus }) {
  if (!status || status === 'failed') {
    return (
      <svg className="inline w-3 h-3 opacity-50" viewBox="0 0 16 11" fill="currentColor">
        <path d="M11.071.653a.75.75 0 0 1 .023 1.06L5.458 7.899 4 6.44l-.554.555a.75.75 0 1 1-1.062-1.06l1.085-1.086a.75.75 0 0 1 1.061 0l1.458 1.458 5.023-5.631a.75.75 0 0 1 1.06-.023Z"/>
      </svg>
    );
  }
  if (status === 'sent') {
    return (
      <svg className="inline w-3.5 h-3 opacity-60" viewBox="0 0 16 11" fill="currentColor">
        <path d="M11.071.653a.75.75 0 0 1 .023 1.06L5.458 7.899 4 6.44l-.554.555a.75.75 0 1 1-1.062-1.06l1.085-1.086a.75.75 0 0 1 1.061 0l1.458 1.458 5.023-5.631a.75.75 0 0 1 1.06-.023Z"/>
      </svg>
    );
  }
  if (status === 'delivered') {
    return (
      <svg className="inline w-4 h-3 opacity-60" viewBox="0 0 18 11" fill="currentColor">
        <path d="M5.458 7.899 4 6.44l-.554.555a.75.75 0 1 1-1.062-1.06l1.085-1.086a.75.75 0 0 1 1.061 0l1.458 1.458 5.023-5.631a.75.75 0 0 1 1.083 1.037L6.52 8.96a.75.75 0 0 1-1.062-.06Z"/>
        <path d="M14.071.653a.75.75 0 0 1 .023 1.06L8.458 7.899l-.53-.53 5.083-5.693a.75.75 0 0 1 1.06-.023Z"/>
      </svg>
    );
  }
  // read → duplo tique verde
  return (
    <svg className="inline w-4 h-3.5" viewBox="0 0 18 11" fill="#25D366" stroke="#25D366" strokeWidth="0.6" strokeLinejoin="round">
      <path d="M5.458 7.899 4 6.44l-.554.555a.75.75 0 1 1-1.062-1.06l1.085-1.086a.75.75 0 0 1 1.061 0l1.458 1.458 5.023-5.631a.75.75 0 0 1 1.083 1.037L6.52 8.96a.75.75 0 0 1-1.062-.06Z"/>
      <path d="M14.071.653a.75.75 0 0 1 .023 1.06L8.458 7.899l-.53-.53 5.083-5.693a.75.75 0 0 1 1.06-.023Z"/>
    </svg>
  );
}

// ─── Message Content renderer (texto, imagem, documento) ─────────────────────

function MessageContent({ text }: { text: string }) {
  const lines = text.split('\n');
  const firstLine = lines[0] || '';
  const secondLine = lines[1] || '';

  const isMediaUrl = (s: string) => s.startsWith('https://') || s.startsWith('http://') || s.startsWith('/media/');
  const toAbsolute = (s: string) => s.startsWith('/media/') ? `http://localhost:9022${s}` : s;
  const isMediaMsg = isMediaUrl(secondLine) && /[\u{1F5BC}\u{1F4C4}\u{1F3B5}\u{1F3A5}\u{1F3AD}\u{1F4CE}📎]/u.test(firstLine);

  if (isMediaMsg) {
    const url = toAbsolute(secondLine);
    const isImage = firstLine.startsWith('🖼');
    const label = firstLine.replace(/^[\s\S]{1,2}/, '').trim() || (isImage ? 'Ver imagem' : 'Abrir arquivo');

    // Detecta pelo emoji OU pela extensão da URL
    const urlExt = url.split('?')[0].split('.').pop()?.toLowerCase() || '';
    const imageExts = new Set(['jpg','jpeg','png','gif','webp','heic','heif']);
    const videoExts = new Set(['mp4','mov','avi','mkv','3gp']);
    const audioExts = new Set(['mp3','ogg','aac','m4a','opus']);

    const isVideo = firstLine.startsWith('🎥') || videoExts.has(urlExt);
    const isAudio = firstLine.startsWith('🎵') || audioExts.has(urlExt);
    const isImageByExt = imageExts.has(urlExt);
    const isImageFinal = (firstLine.startsWith('🖼') || isImageByExt) && !isVideo && !isAudio;

    return (
      <div className="space-y-1.5">
        {isImageFinal ? (
          <>
            <a href={url} target="_blank" rel="noopener noreferrer">
              <img
                src={url}
                alt={label}
                className="max-w-[220px] rounded-lg border border-white/20 cursor-pointer hover:opacity-90 transition-opacity"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
            </a>
            {label && <p className="text-xs opacity-70">{label}</p>}
          </>
        ) : isVideo ? (
          <>
            <video
              src={url}
              controls
              className="max-w-[280px] rounded-lg border border-white/20"
              style={{ maxHeight: 200 }}
            />
            {label && <p className="text-xs opacity-70">{label}</p>}
          </>
        ) : isAudio ? (
          <>
            <audio src={url} controls className="w-full max-w-[260px]" />
            {label && <p className="text-xs opacity-70">{label}</p>}
          </>
        ) : (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 bg-black/10 rounded-xl px-3 py-2 hover:bg-black/20 transition-colors"
          >
            <span className="text-xl flex-shrink-0">{firstLine.slice(0, 2)}</span>
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">{label}</p>
              <p className="text-xs opacity-60">Toque para abrir ↗</p>
            </div>
          </a>
        )}
      </div>
    );
  }

  return <p className="text-sm whitespace-pre-wrap break-words">{text}</p>;
}

// ─── Channel helpers ──────────────────────────────────────────────────────────

const CHANNEL_LABELS: Record<ChannelType, string> = {
  whatsapp: 'WhatsApp',
  instagram: 'Instagram',
  facebook: 'Facebook',
  messenger: 'Messenger',
};

function ChannelIcon({ channel, size = 'sm' }: { channel: ChannelType; size?: 'xs' | 'sm' | 'md' }) {
  const cls = size === 'xs' ? 'w-3 h-3' : size === 'md' ? 'w-5 h-5' : 'w-4 h-4';
  if (channel === 'whatsapp') {
    return (
      <svg className={`${cls} text-green-500`} viewBox="0 0 24 24" fill="currentColor">
        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/>
        <path d="M12 0C5.373 0 0 5.373 0 12c0 2.128.558 4.127 1.534 5.859L.057 23.082a.75.75 0 0 0 .916.937l5.403-1.416A11.945 11.945 0 0 0 12 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-1.885 0-3.652-.508-5.165-1.395l-.361-.215-3.739.98.997-3.64-.235-.376A9.96 9.96 0 0 1 2 12C2 6.477 6.477 2 12 2s10 4.477 10 10-4.477 10-10 10z"/>
      </svg>
    );
  }
  if (channel === 'instagram') {
    return (
      <svg className={`${cls} text-pink-500`} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z"/>
      </svg>
    );
  }
  if (channel === 'facebook' || channel === 'messenger') {
    return (
      <svg className={`${cls} text-blue-600`} viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 0C5.373 0 0 5.373 0 12c0 5.99 4.388 10.954 10.125 11.854V15.47H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.384C19.612 22.954 24 17.99 24 12c0-6.627-5.373-12-12-12z"/>
      </svg>
    );
  }
  return <span className={`${cls === 'w-3 h-3' ? 'text-xs' : 'text-sm'}`}>💬</span>;
}

// ─── Chat Panel (right column) ───────────────────────────────────────────────

function ChatPanel({ leadId, onBack, onDeleted }: { leadId: number; onBack: () => void; onDeleted: () => void }) {
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
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [closing, setClosing] = useState(false);
  const [showClassMenu, setShowClassMenu] = useState(false);
  const [ragSuggestion, setRagSuggestion] = useState<string | null>(null);
  const [loadingSuggestion, setLoadingSuggestion] = useState(false);
  const lastSuggestedMsgId = useRef<number | null>(null);
  const [cordialityPreview, setCordialityPreview] = useState<{ original: string; enhanced: string } | null>(null);
  const [enhancing, setEnhancing] = useState(false);
  const [selectedChannel, setSelectedChannel] = useState<ChannelType | null>(null);
  const user = authService.getCurrentUser();

  useEffect(() => {
    setLoading(true);
    setTab('chat');
    leadsService.getLead(leadId).then(async (l) => {
      setLead(l);
      // Seleciona o canal da conversa mais recente como padrão
      const mostRecent = [...(l.conversations ?? [])].sort(
        (a, b) => new Date(b.last_message_at ?? b.created_at).getTime() - new Date(a.last_message_at ?? a.created_at).getTime()
      )[0];
      const defaultChannel = mostRecent?.channel ?? null;
      setSelectedChannel(defaultChannel);
      const msgs = await leadsService.getMessages(leadId, defaultChannel ?? undefined);
      setMessages(msgs);
    }).finally(() => setLoading(false));
  }, [leadId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Recarrega mensagens quando o canal selecionado muda
  useEffect(() => {
    if (!leadId) return;
    leadsService.getMessages(leadId, selectedChannel ?? undefined).then(setMessages).catch(() => {});
  }, [selectedChannel, leadId]);

  // Polling silencioso de mensagens — detecta novas mensagens do lead sem recarregar a página
  useEffect(() => {
    if (!leadId) return;
    const timer = setInterval(async () => {
      try {
        const msgs = await leadsService.getMessages(leadId, selectedChannel ?? undefined);
        setMessages(prev => {
          if (msgs.length === prev.length) return prev; // sem mudança
          return msgs;
        });
      } catch { /* silencia erros de rede */ }
    }, 8_000);
    return () => clearInterval(timer);
  }, [leadId, selectedChannel]);

  // Sugere resposta RAG quando nova mensagem IN chega e atendente está no controle
  useEffect(() => {
    if (!lead || lead.is_ai_active || messages.length === 0) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg.direction !== 'IN') return;
    if (lastSuggestedMsgId.current === lastMsg.id) return;
    lastSuggestedMsgId.current = lastMsg.id;
    setRagSuggestion(null);
    setLoadingSuggestion(true);
    leadsService.suggestResponse(lead.id, lastMsg.text).then(suggestion => {
      if (suggestion) setRagSuggestion(suggestion);
    }).finally(() => setLoadingSuggestion(false));
  }, [messages, lead]);

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
    const rawText = msgText.trim();
    setEnhancing(true);
    try {
      const result = await leadsService.enhanceMessage(lead.id, rawText);
      if (result.changed) {
        setCordialityPreview({ original: result.original, enhanced: result.enhanced });
        return;
      }
      // Texto não foi alterado — envia direto
      setSending(true);
      const msg = await leadsService.sendMessage(lead.id, rawText);
      setMessages(prev => [...prev, msg]);
      setMsgText('');
    } finally {
      setEnhancing(false);
      setSending(false);
    }
  }

  async function handleSendEnhanced() {
    if (!lead || !cordialityPreview) return;
    setSending(true);
    try {
      const msg = await leadsService.sendMessage(lead.id, cordialityPreview.enhanced);
      setMessages(prev => [...prev, msg]);
      setMsgText('');
      setCordialityPreview(null);
    } finally {
      setSending(false);
    }
  }

  const [fileError, setFileError] = useState('');

  const FILE_LIMITS: Record<string, number> = {
    'image':    5  * 1024 * 1024,  // 5 MB
    'video':    16 * 1024 * 1024,  // 16 MB
    'audio':    16 * 1024 * 1024,  // 16 MB
    'default': 100 * 1024 * 1024,  // 100 MB
  };

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    setFileError('');

    const kind = file.type.startsWith('image/') ? 'image'
               : file.type.startsWith('video/') ? 'video'
               : file.type.startsWith('audio/') ? 'audio'
               : 'default';
    const limit = FILE_LIMITS[kind];

    if (file.size > limit) {
      const limitMB = limit / (1024 * 1024);
      setFileError(`❌ Arquivo muito grande. Limite do WhatsApp: ${limitMB}MB para ${kind === 'default' ? 'documentos' : kind}.`);
      return;
    }
    setPendingFile(file);
  }

  async function handleSendFile() {
    if (!lead || !pendingFile) return;
    setSendingFile(true);
    setFileError('');
    try {
      const msg = await leadsService.sendFile(lead.id, pendingFile, fileCaption);
      setMessages(prev => [...prev, msg]);
      setPendingFile(null);
      setFileCaption('');
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Erro ao enviar arquivo.';
      setFileError(`❌ ${detail}`);
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

  async function handleClose() {
    if (!lead) return;
    setClosing(true);
    try {
      const updated = await leadsService.closeLead(lead.id);
      setLead(updated);
      onDeleted(); // recarrega a lista
    } finally {
      setClosing(false);
    }
  }

  async function handleReopen() {
    if (!lead) return;
    const updated = await leadsService.reopenLead(lead.id);
    setLead(updated);
    onDeleted();
  }

  async function handleDelete() {
    if (!lead) return;
    setDeleting(true);
    try {
      await leadsService.deleteLead(lead.id);
      onDeleted();
      onBack();
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
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

        {/* Lead info + channel selector */}
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-800 text-sm truncate">
            {lead.full_name || lead.phone}
          </p>
          <div className="flex items-center gap-1 mt-0.5 flex-wrap">
            {lead.conversations && lead.conversations.length > 1 ? (
              lead.conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => setSelectedChannel(conv.channel)}
                  className={`inline-flex items-center gap-1 text-xs rounded-full px-2 py-0.5 transition-colors ${
                    selectedChannel === conv.channel
                      ? 'bg-blue-100 text-blue-700 font-semibold'
                      : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                  }`}
                >
                  <ChannelIcon channel={conv.channel} size="xs" />
                  {CHANNEL_LABELS[conv.channel]}
                </button>
              ))
            ) : (
              <span className="inline-flex items-center gap-1 text-xs text-gray-400">
                <ChannelIcon channel={selectedChannel ?? 'whatsapp'} size="xs" />
                {lead.phone || lead.facebook_psid || lead.instagram_user_id || ''}
              </span>
            )}
          </div>
        </div>

        {/* Badges + actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="hidden sm:flex items-center gap-1.5">
            <TierBadge tier={lead.tier} />

            {/* Classification dropdown */}
            <div className="relative">
              <button
                onClick={() => setShowClassMenu(v => !v)}
                className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-semibold transition-colors hover:opacity-80"
                style={{ minWidth: 52 }}
                title="Alterar classificação"
              >
                {lead.lead_classification === 'HOT_LEAD'  && <><span>🔥</span><span className="text-red-700">Hot</span></>}
                {lead.lead_classification === 'WARM_LEAD' && <><span>🟡</span><span className="text-amber-700">Warm</span></>}
                {lead.lead_classification === 'COLD_LEAD' && <><span>❄️</span><span className="text-blue-600">Cold</span></>}
                {!lead.lead_classification && <span className="text-gray-400 italic">+ classificar</span>}
                <svg className="w-3 h-3 text-gray-400 ml-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><polyline points="6 9 12 15 18 9"/></svg>
              </button>

              {showClassMenu && (
                <>
                  {/* backdrop */}
                  <div className="fixed inset-0 z-10" onClick={() => setShowClassMenu(false)} />
                  <div className="absolute right-0 top-full mt-1 z-20 bg-white border border-gray-200 rounded-xl shadow-lg py-1 min-w-[130px]">
                    {([
                      { value: 'HOT_LEAD',  label: 'Hot',  icon: '🔥', cls: 'hover:bg-red-50 text-gray-700 hover:text-red-700' },
                      { value: 'WARM_LEAD', label: 'Warm', icon: '🟡', cls: 'hover:bg-amber-50 text-gray-700 hover:text-amber-700' },
                      { value: 'COLD_LEAD', label: 'Cold', icon: '❄️', cls: 'hover:bg-blue-50 text-gray-700 hover:text-blue-600' },
                    ] as const).map(({ value, label, icon, cls }) => (
                      <button
                        key={value}
                        onClick={async () => {
                          setShowClassMenu(false);
                          const next = lead.lead_classification === value ? null : value;
                          const updated = await leadsService.updateLead(lead.id, { lead_classification: next });
                          setLead(updated);
                        }}
                        className={`w-full flex items-center gap-2 px-3 py-1.5 text-sm ${cls} ${lead.lead_classification === value ? 'font-bold' : ''}`}
                      >
                        <span>{icon}</span>{label}
                        {lead.lead_classification === value && <span className="ml-auto text-xs opacity-50">✓</span>}
                      </button>
                    ))}
                    {lead.lead_classification && (
                      <>
                        <div className="border-t border-gray-100 my-1" />
                        <button
                          onClick={async () => {
                            setShowClassMenu(false);
                            const updated = await leadsService.updateLead(lead.id, { lead_classification: null });
                            setLead(updated);
                          }}
                          className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-gray-400 hover:bg-gray-50"
                        >
                          <span>✕</span> Remover
                        </button>
                      </>
                    )}
                  </div>
                </>
              )}
            </div>

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

          {/* Close / Reopen button */}
          {lead.status === 'CLOSED' ? (
            <button
              onClick={handleReopen}
              title="Reabrir lead"
              className="flex items-center justify-center w-8 h-8 rounded-lg text-gray-300 hover:bg-green-50 hover:text-green-600 transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <polyline points="1 4 1 10 7 10"/>
                <path d="M3.51 15a9 9 0 1 0 .49-3.5"/>
              </svg>
            </button>
          ) : (
            <button
              onClick={handleClose}
              disabled={closing}
              title="Fechar conversa"
              className="flex items-center justify-center w-8 h-8 rounded-lg text-gray-300 hover:bg-gray-100 hover:text-gray-500 transition-colors"
            >
              {closing
                ? <span className="loading loading-spinner loading-xs" />
                : (
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                )
              }
            </button>
          )}

          {/* Delete button */}
          {confirmDelete ? (
            <div className="flex items-center gap-1">
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="btn btn-error btn-xs"
              >
                {deleting ? <span className="loading loading-spinner loading-xs" /> : 'Confirmar'}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="btn btn-ghost btn-xs text-gray-400"
              >
                Cancelar
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              title="Excluir lead"
              className="flex items-center justify-center w-8 h-8 rounded-lg text-gray-300 hover:bg-red-50 hover:text-red-500 transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                <path d="M10 11v6"/><path d="M14 11v6"/>
                <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
              </svg>
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
            {messages.map(msg => {
              const isComment = msg.text.startsWith('[Comentário]');
              const isSuggestion = msg.text.startsWith('[Sugestão]');
              const displayText = isComment
                ? msg.text.replace(/^\[Comentário\]\s*/, '')
                : isSuggestion
                  ? msg.text.replace(/^\[Sugestão\]\s*/, '')
                  : msg.text;

              if (isComment) {
                return (
                  <div key={msg.id} className="flex justify-start">
                    <div className="max-w-[75%] bg-pink-50 border border-pink-200 rounded-2xl rounded-tl-sm px-3 py-2">
                      <div className="flex items-center gap-1 mb-1">
                        <ChannelIcon channel="instagram" size="xs" />
                        <span className="text-[10px] font-semibold text-pink-600 uppercase tracking-wide">Comentário</span>
                      </div>
                      <MessageContent text={displayText} />
                      <p className="text-[10px] mt-1 opacity-50">
                        {new Date(msg.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  </div>
                );
              }

              if (isSuggestion) {
                return (
                  <div key={msg.id} className="flex justify-end">
                    <div className="max-w-[75%] bg-amber-50 border border-amber-200 rounded-2xl rounded-tr-sm px-3 py-2">
                      <div className="flex items-center gap-1 mb-1">
                        <span className="text-[10px] font-semibold text-amber-600 uppercase tracking-wide">💡 Sugestão IA</span>
                      </div>
                      <p className="text-sm text-gray-700 whitespace-pre-wrap break-words">{displayText}</p>
                      {!lead.is_ai_active && (
                        <button
                          onClick={() => setMsgText(displayText)}
                          className="mt-2 text-xs px-2.5 py-1 rounded-lg bg-amber-500 text-white hover:bg-amber-600 transition-colors font-medium"
                        >
                          Usar como resposta
                        </button>
                      )}
                      <p className="text-[10px] mt-1 opacity-50 text-right">
                        {new Date(msg.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  </div>
                );
              }

              return (
                <div key={msg.id} className={`flex ${msg.direction === 'OUT' ? 'justify-end' : 'justify-start'}`}>
                  <div className={msg.direction === 'OUT' ? 'chat-bubble-out' : 'chat-bubble-in'}>
                    <MessageContent text={msg.text} />
                    <p className={`text-[10px] mt-1 opacity-60 ${msg.direction === 'OUT' ? 'text-right' : ''} flex items-center gap-0.5 ${msg.direction === 'OUT' ? 'justify-end' : ''}`}>
                      <span>{new Date(msg.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span>
                      {msg.direction === 'OUT' && <MessageStatusIcon status={msg.msg_status} />}
                    </p>
                  </div>
                </div>
              );
            })}
            <div ref={chatEndRef} />
          </div>

          {/* Input area */}
          {!lead.is_ai_active ? (
            <div className="border-t border-gray-100 bg-white flex-shrink-0">

              {/* Banner de sugestão RAG */}
              {(loadingSuggestion || ragSuggestion) && (
                <div className="flex items-start gap-2 px-3 pt-2 pb-1">
                  <div className="flex-1 flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                    <span className="text-amber-500 text-sm flex-shrink-0 mt-0.5">💡</span>
                    {loadingSuggestion && !ragSuggestion ? (
                      <span className="text-xs text-amber-600 italic">Gerando sugestão...</span>
                    ) : (
                      <p className="text-xs text-gray-700 flex-1 leading-relaxed">{ragSuggestion}</p>
                    )}
                  </div>
                  {ragSuggestion && (
                    <div className="flex flex-col gap-1 flex-shrink-0">
                      <button
                        onClick={() => { setMsgText(ragSuggestion); setRagSuggestion(null); }}
                        className="text-xs px-2 py-1 rounded-lg bg-amber-500 text-white hover:bg-amber-600 transition-colors font-medium"
                      >
                        Usar
                      </button>
                      <button
                        onClick={() => setRagSuggestion(null)}
                        className="text-xs px-2 py-1 rounded-lg bg-gray-100 text-gray-500 hover:bg-gray-200 transition-colors"
                      >
                        Ignorar
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Aviso de erro de arquivo */}
              {fileError && (
                <div className="flex items-center gap-2 px-3 pt-2">
                  <p className="text-xs text-red-500 flex-1">{fileError}</p>
                  <button onClick={() => setFileError('')} className="text-red-400 hover:text-red-600">
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                  </button>
                </div>
              )}

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

                <textarea
                  rows={1}
                  placeholder="Digite sua mensagem..."
                  className="flex-1 text-sm border border-gray-200 rounded-xl px-3 py-2 outline-none focus:border-blue-400 transition-colors resize-none overflow-hidden"
                  value={msgText}
                  onChange={e => {
                    setMsgText(e.target.value);
                    if (ragSuggestion) setRagSuggestion(null);
                    e.target.style.height = 'auto';
                    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
                  }}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />
                <button
                  onClick={handleSend}
                  disabled={sending || enhancing || !msgText.trim()}
                  className="flex items-center justify-center w-9 h-9 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 transition-colors flex-shrink-0"
                  title={enhancing ? 'Aprimorando mensagem...' : 'Enviar'}
                >
                  {(sending || enhancing)
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
          <div className="flex flex-wrap gap-2 mb-4 sm:hidden">
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
              ['Moradia', lead.housing_type === 'HOUSE_Y' ? 'Casa c/ pátio' : lead.housing_type === 'HOUSE_N' ? 'Casa s/ pátio' : lead.housing_type === 'HOUSE' ? 'Casa' : lead.housing_type === 'APT' ? 'Apartamento' : '—'],
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

      {/* ── Modal de aprovação de cordialidade ── */}
      {cordialityPreview && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100 bg-gradient-to-r from-blue-50 to-indigo-50">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
                </svg>
              </div>
              <div>
                <p className="font-semibold text-gray-800 text-sm">Mensagem aprimorada</p>
                <p className="text-xs text-gray-500">A IA tornou sua mensagem mais cordial. Deseja enviá-la?</p>
              </div>
            </div>

            {/* Body */}
            <div className="px-5 py-4 space-y-3 max-h-72 overflow-y-auto">
              <div>
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">Original</p>
                <p className="text-sm text-gray-500 bg-gray-50 rounded-xl px-3 py-2.5 whitespace-pre-wrap leading-relaxed">
                  {cordialityPreview.original}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-blue-500 uppercase tracking-wide mb-1">Versão aprimorada</p>
                <p className="text-sm text-gray-800 bg-blue-50 border border-blue-100 rounded-xl px-3 py-2.5 whitespace-pre-wrap leading-relaxed">
                  {cordialityPreview.enhanced}
                </p>
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center gap-2 px-5 py-4 border-t border-gray-100 bg-gray-50">
              <button
                onClick={() => setCordialityPreview(null)}
                className="flex-1 py-2 rounded-xl text-sm font-medium text-gray-600 bg-white border border-gray-200 hover:bg-gray-100 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleSendEnhanced}
                disabled={sending}
                className="flex-1 py-2 rounded-xl text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {sending ? <span className="loading loading-spinner loading-xs" /> : 'Enviar versão aprimorada'}
              </button>
            </div>
          </div>
        </div>
      )}
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

  const buildParams = (f: LeadFilter, p: number) => {
    const params: Record<string, string | number | boolean> = { page: p };
    if (f.tier) params.tier = f.tier;
    if (f.status) params.status = f.status;
    if (f.is_ai_active) params.is_ai_active = f.is_ai_active === 'true';
    if (f.search) params.search = f.search;
    return params;
  };

  const load = useCallback((f: LeadFilter = filters, p: number = 1) => {
    setLoading(true);
    leadsService.getLeads(buildParams(f, p) as never)
      .then(data => {
        setLeads(p === 1 ? data.results : prev => [...prev, ...data.results]);
        setTotal(data.count);
        setHasMore(!!data.next);
        setPage(p);
      })
      .finally(() => setLoading(false));
  }, [filters]);

  // Polling silencioso da lista — sem spinner, só atualiza os dados
  const silentRefresh = useCallback((f: LeadFilter = filters) => {
    leadsService.getLeads(buildParams(f, 1) as never).then(data => {
      setLeads(data.results);
      setTotal(data.count);
      setHasMore(!!data.next);
    }).catch(() => {});
  }, [filters]);

  useEffect(() => { load(); }, []);

  useEffect(() => {
    const timer = setInterval(() => silentRefresh(filters), 15_000);
    return () => clearInterval(timer);
  }, [filters, silentRefresh]);

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
              {[...leads]
                .sort((a, b) => {
                  const aClosed = a.status === 'CLOSED' ? 2 : a.last_message_direction === 'IN' ? 0 : 1;
                  const bClosed = b.status === 'CLOSED' ? 2 : b.last_message_direction === 'IN' ? 0 : 1;
                  if (aClosed !== bClosed) return aClosed - bClosed;
                  return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
                })
                .map(lead => (
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
            onDeleted={() => load(filters, 1)}
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
