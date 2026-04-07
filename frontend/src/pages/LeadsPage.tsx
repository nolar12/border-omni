import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { config } from '../config';
import { leadsService } from '../services/leads';
import { authService } from '../services/auth';
import { messageTemplatesService } from '../services/messageTemplates';
import { mediaUploadService } from '../services/mediaUpload';
import { galleryService, type GalleryMedia } from '../services/gallery';
import { quickRepliesService } from '../services/quickReplies';
import type { LeadListItem, Lead, Message, ChannelType, MessageTemplate } from '../types';
import TierBadge from '../components/TierBadge';
import StatusBadge from '../components/StatusBadge';
import AIStatusBadge from '../components/AIStatusBadge';
import QuickReplyDrawer from '../components/QuickReplyDrawer';
import VideoThumbnail from '../components/VideoThumbnail';

// ─── Lead List Item (middle column) ──────────────────────────────────────────

function WhatsApp24hBadge({ lastMessageAt }: { lastMessageAt: string | null }) {
  if (!lastMessageAt) return null;
  const delta = Date.now() - new Date(lastMessageAt).getTime();
  const windowMs = 24 * 60 * 60 * 1000;
  if (delta >= windowMs) return null;

  const remainingMs = windowMs - delta;
  const remainingHours = remainingMs / (60 * 60 * 1000);
  const isExpiringSoon = remainingHours < 4;

  const hoursLabel = remainingHours < 1
    ? `${Math.ceil(remainingMs / (60 * 1000))}min`
    : `${Math.floor(remainingHours)}h`;

  return (
    <span
      className={`inline-flex items-center gap-0.5 text-xs font-semibold rounded-md px-1.5 py-0.5 ${
        isExpiringSoon
          ? 'bg-orange-100 text-orange-700'
          : 'bg-green-100 text-green-700'
      }`}
      title={`Janela WhatsApp expira em ${hoursLabel}`}
    >
      <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
      </svg>
      {hoursLabel}
    </span>
  );
}

function LeadRow({ lead, isActive, onClick }: { lead: LeadListItem; isActive: boolean; onClick: () => void }) {
  const name = lead.full_name || lead.phone;
  const timeAgo = new Date(lead.updated_at).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' });
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
          <p className={`text-base truncate ${
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
            <span className="text-sm text-gray-400">{timeAgo}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {!isClosed && <TierBadge tier={lead.tier} />}
          {isClosed
            ? <StatusBadge status={lead.status} />
            : lead.lead_classification
              ? (
                <span className={`inline-flex items-center gap-0.5 text-xs font-semibold rounded-md px-1.5 py-0.5 ${
                  lead.lead_classification === 'DANGER_LEAD' ? 'bg-red-900 text-white'        :
                  lead.lead_classification === 'HOT_LEAD'    ? 'bg-red-100 text-red-700'      :
                  lead.lead_classification === 'WARM_LEAD'   ? 'bg-amber-100 text-amber-700'  :
                                                               'bg-blue-100 text-blue-600'
                }`}>
                  {lead.lead_classification === 'DANGER_LEAD' ? '⚠️' :
                   lead.lead_classification === 'HOT_LEAD'    ? '🔥' :
                   lead.lead_classification === 'WARM_LEAD'   ? '🟡' : '❄️'}
                  {lead.lead_classification === 'DANGER_LEAD' ? 'Danger' :
                   lead.lead_classification === 'HOT_LEAD'    ? 'Hot'    :
                   lead.lead_classification === 'WARM_LEAD'   ? 'Warm'   : 'Cold'}
                </span>
              )
              : <StatusBadge status={lead.status} />
          }
          {!isClosed && (
            <WhatsApp24hBadge lastMessageAt={lead.whatsapp_last_message_at} />
          )}
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
  const toAbsolute = (s: string) => s.startsWith('/media/') ? `${config.apiUrl}${s}` : s;
  const isMediaMsg = isMediaUrl(secondLine) && /[\u{1F5BC}\u{1F4C4}\u{1F3B5}\u{1F3A5}\u{1F3AD}\u{1F4CE}📎]/u.test(firstLine);

  if (isMediaMsg) {
    const url = toAbsolute(secondLine);
    const isImage = firstLine.startsWith('🖼');
    const label = firstLine.replace(/^[\s\S]{1,2}/, '').trim() || (isImage ? 'Ver imagem' : 'Abrir arquivo');

    // Detecta pelo emoji OU pela extensão da URL
    const urlExt = url.split('?')[0].split('.').pop()?.toLowerCase() || '';
    const imageExts = new Set(['jpg','jpeg','png','gif','webp','heic','heif']);
    const videoExts = new Set(['mp4','mov','avi','mkv','3gp']);
    const audioExts = new Set(['mp3','ogg','oga','aac','m4a','opus','webm','amr']);

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

  return <p className="text-base whitespace-pre-wrap break-words">{text}</p>;
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
  const navigate = useNavigate();
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
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<'chat' | 'info' | 'notes'>('chat');
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [closing, setClosing] = useState(false);
  const [reclassifying, setReclassifying] = useState(false);
  const [showBriefPanel, setShowBriefPanel] = useState(false);
  const [briefText, setBriefText] = useState('');
  const [loadingBrief, setLoadingBrief] = useState(false);
  const [showClassMenu, setShowClassMenu] = useState(false);
  const [ragSuggestions, setRagSuggestions] = useState<string[]>([]);
  const [loadingSuggestion, setLoadingSuggestion] = useState(false);
  const lastSuggestedMsgId = useRef<number | null>(null);
  const isSendingRef = useRef(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [selectedChannel, setSelectedChannel] = useState<ChannelType | null>(null);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [approvedTemplates, setApprovedTemplates] = useState<MessageTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<MessageTemplate | null>(null);
  const [templateVars, setTemplateVars] = useState<string[]>([]);
  const [templateMediaUrl, setTemplateMediaUrl] = useState('');
  const [sendingTemplate, setSendingTemplate] = useState(false);
  const [templateError, setTemplateError] = useState('');
  const [uploadingMedia, setUploadingMedia] = useState(false);
  const mediaFileInputRef = useRef<HTMLInputElement>(null);
  const [templateModalView, setTemplateModalView] = useState<'list' | 'detail'>('list');
  const [showTemplateGalleryPicker, setShowTemplateGalleryPicker] = useState(false);
  const [templateGalleryItems, setTemplateGalleryItems] = useState<GalleryMedia[]>([]);
  const [loadingTemplateGallery, setLoadingTemplateGallery] = useState(false);
  const [templateVideoPreview, setTemplateVideoPreview] = useState<GalleryMedia | null>(null);
  const [showGalleryModal, setShowGalleryModal] = useState(false);
  const [galleryItems, setGalleryItems] = useState<GalleryMedia[]>([]);
  const [galleryFilter, setGalleryFilter] = useState<'ALL' | 'IMAGE' | 'VIDEO' | 'DOCUMENT'>('ALL');
  const [gallerySelections, setGallerySelections] = useState<Map<number, { item: GalleryMedia; sendDesc: boolean }>>(new Map());
  const [galleryVideoPreview, setGalleryVideoPreview] = useState<GalleryMedia | null>(null);
  const [sendingGallery, setSendingGallery] = useState(false);
  const [galleryError, setGalleryError] = useState('');
  const [loadingGallery, setLoadingGallery] = useState(false);
  const [uploadingGalleryItem, setUploadingGalleryItem] = useState(false);
  const galleryUploadInputRef = useRef<HTMLInputElement>(null);
  const [saveAsQR, setSaveAsQR] = useState(false);
  const [showSaveQRModal, setShowSaveQRModal] = useState(false);
  const [pendingQRBody, setPendingQRBody] = useState('');
  const [qrTitle, setQrTitle] = useState('');
  const [qrShortcut, setQrShortcut] = useState('');
  const [savingQR, setSavingQR] = useState(false);
  const [qrSavedToast, setQrSavedToast] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const user = authService.getCurrentUser();

  // Calcula se a janela de 24h do WhatsApp está aberta
  const isWhatsappWindowOpen = (() => {
    if (!lead) return true;
    const whatsappConv = lead.conversations?.find(c => c.channel === 'whatsapp');
    if (!whatsappConv?.last_message_at) return true;
    const delta = Date.now() - new Date(whatsappConv.last_message_at).getTime();
    return delta < 24 * 60 * 60 * 1000;
  })();

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

  // Recalcula altura do textarea quando msgText muda programaticamente (ex: ao clicar "Usar")
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [msgText]);

  // Sugere 3 respostas quando o lead tem mensagem sem resposta humana ainda.
  // Mensagens automáticas/bot (sem provider_message_id) não contam como resposta humana.
  useEffect(() => {
    if (!lead || lead.is_ai_active || messages.length === 0) return;

    // Último IN do lead
    const lastIn = [...messages].reverse().find(m => m.direction === 'IN');
    if (!lastIn) return;

    // Último OUT humano (com provider_message_id preenchido)
    const lastHumanOut = [...messages].reverse().find(
      m => m.direction === 'OUT' && m.provider_message_id,
    );

    // Se já há resposta humana mais recente que o último IN, não sugere
    if (lastHumanOut && new Date(lastHumanOut.created_at) > new Date(lastIn.created_at)) return;

    if (lastSuggestedMsgId.current === lastIn.id) return;
    lastSuggestedMsgId.current = lastIn.id;
    setRagSuggestions([]);
    setLoadingSuggestion(true);
    leadsService.suggestResponse(lead.id, lastIn.text, selectedChannel ?? 'whatsapp').then(suggestions => {
      if (suggestions.length > 0) setRagSuggestions(suggestions);
      else console.warn('[IA] suggestResponse retornou vazio para msg id:', lastIn.id);
    }).catch(e => console.error('[IA] suggestResponse erro:', e))
      .finally(() => setLoadingSuggestion(false));
  }, [messages, lead, selectedChannel]);

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

  async function openTemplateModal() {
    try {
      const all = await messageTemplatesService.list();
      setApprovedTemplates(all.filter(t => t.status === 'APPROVED'));
    } catch {
      setApprovedTemplates([]);
    }
    setSelectedTemplate(null);
    setTemplateVars([]);
    setTemplateMediaUrl('');
    setTemplateError('');
    setShowTemplateGalleryPicker(false);
    setTemplateModalView('list');
    setShowTemplateModal(true);
  }

  async function handleSendTemplate() {
    if (!lead || !selectedTemplate) return;
    const needsMedia = ['IMAGE', 'VIDEO', 'DOCUMENT'].includes(selectedTemplate.header_type);
    if (needsMedia && !templateMediaUrl.trim()) {
      setTemplateError(`Informe a URL do ${selectedTemplate.header_type === 'IMAGE' ? 'imagem' : selectedTemplate.header_type === 'VIDEO' ? 'vídeo' : 'documento'} para enviar este template.`);
      return;
    }
    setTemplateError('');
    setSendingTemplate(true);
    try {
      const msg = await leadsService.sendTemplate(
        lead.id,
        selectedTemplate.id,
        templateVars,
        templateMediaUrl || undefined,
      );
      setMessages(prev => [...prev, msg]);
      setShowTemplateModal(false);
      setSelectedTemplate(null);
      setTemplateVars([]);
      setTemplateMediaUrl('');
      setTemplateError('');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setTemplateError(detail ?? 'Erro ao enviar template. Verifique os logs.');
    } finally {
      setSendingTemplate(false);
    }
  }

  async function handleMediaFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingMedia(true);
    setTemplateError('');
    try {
      const result = await mediaUploadService.upload(file);
      setTemplateMediaUrl(result.url);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setTemplateError(detail ?? 'Erro ao fazer upload do arquivo.');
    } finally {
      setUploadingMedia(false);
      if (mediaFileInputRef.current) mediaFileInputRef.current.value = '';
    }
  }

  async function openGalleryModal() {
    setGallerySelections(new Map());
    setGalleryError('');
    setGalleryFilter('ALL');
    setShowGalleryModal(true);
    setLoadingGallery(true);
    try {
      const data = await galleryService.list();
      setGalleryItems(data);
    } finally {
      setLoadingGallery(false);
    }
  }

  async function handleSendGalleryItem() {
    if (!lead || gallerySelections.size === 0) return;
    setSendingGallery(true);
    setGalleryError('');
    try {
      const allMsgs: Message[] = [];
      for (const { item, sendDesc } of gallerySelections.values()) {
        const caption = sendDesc ? (item.description ?? '') : '';
        const msgs = await leadsService.sendGalleryItem(lead.id, item.id, caption);
        allMsgs.push(...msgs);
      }
      setMessages(prev => [...prev, ...allMsgs]);
      setShowGalleryModal(false);
      setGallerySelections(new Map());
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setGalleryError(detail ?? 'Erro ao enviar itens da galeria.');
    } finally {
      setSendingGallery(false);
    }
  }

  async function openTemplateGalleryPicker(mediaType: 'IMAGE' | 'VIDEO') {
    setShowTemplateGalleryPicker(true);
    setLoadingTemplateGallery(true);
    try {
      const data = await galleryService.list(mediaType);
      setTemplateGalleryItems(data);
    } finally {
      setLoadingTemplateGallery(false);
    }
  }

  async function handleGalleryModalUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    setUploadingGalleryItem(true);
    setGalleryError('');
    for (const file of files) {
      try {
        const item = await galleryService.upload(file, file.name);
        setGalleryItems(prev => [item, ...prev]);
      } catch (err: unknown) {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setGalleryError(detail ?? `Erro ao enviar ${file.name}.`);
      }
    }
    setUploadingGalleryItem(false);
    if (galleryUploadInputRef.current) galleryUploadInputRef.current.value = '';
  }

  function triggerSaveQRModal(text: string) {
    if (!saveAsQR) return;
    setPendingQRBody(text);
    setQrTitle('');
    setQrShortcut('');
    setShowSaveQRModal(true);
  }

  async function handleSend() {
    if (!lead || !msgText.trim() || isSendingRef.current) return;
    isSendingRef.current = true;
    const rawText = msgText.trim();
    setSending(true);
    try {
      const msg = await leadsService.sendMessage(lead.id, rawText);
      setMessages(prev => [...prev, msg]);
      setMsgText('');
      triggerSaveQRModal(rawText);
    } finally {
      setSending(false);
      isSendingRef.current = false;
    }
  }

  async function startRecording() {
    if (!lead) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferredTypes = ['audio/ogg;codecs=opus', 'audio/mp4', 'audio/webm;codecs=opus', 'audio/webm'];
      const mimeType = preferredTypes.find(t => MediaRecorder.isTypeSupported(t)) ?? 'audio/webm';
      const extMap: Record<string, string> = { 'audio/ogg;codecs=opus': 'ogg', 'audio/mp4': 'm4a' };
      const ext = extMap[mimeType] ?? 'webm';
      const uploadMime = mimeType.split(';')[0];
      const recorder = new MediaRecorder(stream, { mimeType });
      audioChunksRef.current = [];
      recorder.ondataavailable = e => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(audioChunksRef.current, { type: uploadMime });
        const file = new File([blob], `audio_${Date.now()}.${ext}`, { type: uploadMime });
        setSending(true);
        try {
          const msg = await leadsService.sendFile(lead.id, file, '');
          setMessages(prev => [...prev, msg]);
        } catch (err: any) {
          const detail = err?.response?.data?.detail || 'Erro ao enviar áudio.';
          setFileError(`❌ ${detail}`);
        } finally {
          setSending(false);
        }
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setRecordingSeconds(0);
      recordingTimerRef.current = setInterval(() => setRecordingSeconds(s => s + 1), 1000);
    } catch {
      alert('Não foi possível acessar o microfone. Verifique as permissões do navegador.');
    }
  }

  function stopRecording(send: boolean) {
    if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
    setIsRecording(false);
    setRecordingSeconds(0);
    if (!send) {
      mediaRecorderRef.current?.stream?.getTracks().forEach(t => t.stop());
      audioChunksRef.current = [];
      mediaRecorderRef.current = null;
      return;
    }
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
  }

  async function handleSaveQR() {
    if (!qrTitle.trim() || !pendingQRBody) return;
    setSavingQR(true);
    try {
      await quickRepliesService.create({
        title: qrTitle.trim(),
        body: pendingQRBody,
        shortcut: qrShortcut.trim() || undefined,
      });
      setShowSaveQRModal(false);
      setSaveAsQR(false);
      setPendingQRBody('');
      setQrTitle('');
      setQrShortcut('');
      setQrSavedToast(true);
      setTimeout(() => setQrSavedToast(false), 3000);
    } catch {
      // silently ignore
    } finally {
      setSavingQR(false);
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
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    e.target.value = '';
    setFileError('');

    const errors: string[] = [];
    const valid: File[] = [];

    for (const file of files) {
      const kind = file.type.startsWith('image/') ? 'image'
                 : file.type.startsWith('video/') ? 'video'
                 : file.type.startsWith('audio/') ? 'audio'
                 : 'default';
      const limit = FILE_LIMITS[kind];
      if (file.size > limit) {
        const limitMB = limit / (1024 * 1024);
        errors.push(`"${file.name}" (limite ${limitMB}MB)`);
      } else {
        valid.push(file);
      }
    }

    if (errors.length) setFileError(`❌ Muito grande: ${errors.join(', ')}`);
    if (valid.length) setPendingFiles(prev => [...prev, ...valid]);
  }

  async function handleSendFile() {
    if (!lead || !pendingFiles.length) return;
    setSendingFile(true);
    setFileError('');
    try {
      for (const file of pendingFiles) {
        const caption = pendingFiles.length === 1 ? fileCaption : '';
        const msg = await leadsService.sendFile(lead.id, file, caption);
        setMessages(prev => [...prev, msg]);
      }
      setPendingFiles([]);
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

  async function handleArchive() {
    if (!lead) return;
    setArchiving(true);
    try {
      await leadsService.archiveLead(lead.id);
      onDeleted();
      onBack();
    } finally {
      setArchiving(false);
      setConfirmArchive(false);
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
                {lead.lead_classification === 'DANGER_LEAD' && <><span>⚠️</span><span className="text-red-900 font-bold">Danger</span></>}
                {lead.lead_classification === 'HOT_LEAD'    && <><span>🔥</span><span className="text-red-700">Hot</span></>}
                {lead.lead_classification === 'WARM_LEAD'   && <><span>🟡</span><span className="text-amber-700">Warm</span></>}
                {lead.lead_classification === 'COLD_LEAD'   && <><span>❄️</span><span className="text-blue-600">Cold</span></>}
                {!lead.lead_classification && <span className="text-gray-400 italic">+ classificar</span>}
                <svg className="w-3 h-3 text-gray-400 ml-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><polyline points="6 9 12 15 18 9"/></svg>
              </button>

              {showClassMenu && (
                <>
                  {/* backdrop */}
                  <div className="fixed inset-0 z-10" onClick={() => setShowClassMenu(false)} />
                  <div className="absolute right-0 top-full mt-1 z-20 bg-white border border-gray-200 rounded-xl shadow-lg py-1 min-w-[130px]">
                    {([
                      { value: 'DANGER_LEAD', label: 'Danger', icon: '⚠️', cls: 'hover:bg-red-100 text-gray-700 hover:text-red-900 font-semibold' },
                      { value: 'HOT_LEAD',    label: 'Hot',    icon: '🔥', cls: 'hover:bg-red-50 text-gray-700 hover:text-red-700' },
                      { value: 'WARM_LEAD',   label: 'Warm',   icon: '🟡', cls: 'hover:bg-amber-50 text-gray-700 hover:text-amber-700' },
                      { value: 'COLD_LEAD',   label: 'Cold',   icon: '❄️', cls: 'hover:bg-blue-50 text-gray-700 hover:text-blue-600' },
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

            {/* Reclassificar IA */}
            <button
              onClick={async () => {
                setReclassifying(true);
                try {
                  const result = await leadsService.reclassifyLead(lead.id);
                  setLead(prev => prev ? { ...prev, lead_classification: result.lead_classification as never, score: result.score } : prev);
                } catch { /* silencia */ } finally {
                  setReclassifying(false);
                }
              }}
              disabled={reclassifying}
              title="Reclassificar com IA"
              className="flex items-center justify-center w-7 h-7 rounded-lg text-gray-300 hover:bg-violet-50 hover:text-violet-500 transition-colors disabled:opacity-40"
            >
              {reclassifying
                ? <span className="loading loading-spinner loading-xs" />
                : <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M12 2a10 10 0 0 1 10 10"/><path d="M12 22a10 10 0 0 1-10-10"/><polyline points="22 12 18 16 14 12"/><polyline points="2 12 6 8 10 12"/></svg>
              }
            </button>

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
              className="flex items-center justify-center w-10 h-10 rounded-xl text-gray-300 hover:bg-green-50 hover:text-green-600 transition-colors"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <polyline points="1 4 1 10 7 10"/>
                <path d="M3.51 15a9 9 0 1 0 .49-3.5"/>
              </svg>
            </button>
          ) : (
            <button
              onClick={handleClose}
              disabled={closing}
              title="Fechar conversa"
              className="flex items-center justify-center w-10 h-10 rounded-xl text-gray-300 hover:bg-gray-100 hover:text-gray-500 transition-colors"
            >
              {closing
                ? <span className="loading loading-spinner loading-xs" />
                : (
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                )
              }
            </button>
          )}

          {/* Archive button */}
          {confirmArchive ? (
            <div className="flex items-center gap-1">
              <button
                onClick={handleArchive}
                disabled={archiving}
                className="btn btn-warning btn-xs"
              >
                {archiving ? <span className="loading loading-spinner loading-xs" /> : 'Arquivar?'}
              </button>
              <button
                onClick={() => setConfirmArchive(false)}
                className="btn btn-ghost btn-xs text-gray-400"
              >
                Cancelar
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmArchive(true)}
              title="Arquivar lead"
              className="flex items-center justify-center w-10 h-10 rounded-xl text-gray-300 hover:bg-amber-50 hover:text-amber-500 transition-colors"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <polyline points="21 8 21 21 3 21 3 8"/>
                <rect x="1" y="3" width="22" height="5"/>
                <line x1="10" y1="12" x2="14" y2="12"/>
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-100 bg-white flex-shrink-0">
        {/* Botão voltar — mobile only, à esquerda das tabs */}
        <button
          onClick={onBack}
          className="md:hidden flex items-center justify-center w-12 flex-shrink-0 text-gray-500 hover:bg-gray-100 transition-colors border-r border-gray-100"
          title="Voltar"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>

        {(['chat', 'info', 'notes'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2.5 text-sm font-semibold uppercase tracking-wide transition-colors ${
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
                        <span className="text-xs font-semibold text-pink-600 uppercase tracking-wide">Comentário</span>
                      </div>
                      <MessageContent text={displayText} />
                      <p className="text-xs mt-1 opacity-50">
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
                        <span className="text-xs font-semibold text-amber-600 uppercase tracking-wide">💡 Sugestão IA</span>
                      </div>
                      <p className="text-base text-gray-700 whitespace-pre-wrap break-words">{displayText}</p>
                      {!lead.is_ai_active && (
                        <button
                          onClick={() => setMsgText(displayText)}
                          className="mt-2 text-xs px-2.5 py-1 rounded-lg bg-amber-500 text-white hover:bg-amber-600 transition-colors font-medium"
                        >
                          Usar como resposta
                        </button>
                      )}
                      <p className="text-xs mt-1 opacity-50 text-right">
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
                    <p className={`text-xs mt-1 opacity-60 ${msg.direction === 'OUT' ? 'text-right' : ''} flex items-center gap-0.5 ${msg.direction === 'OUT' ? 'justify-end' : ''}`}>
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

              {/* Banner janela 24h expirada */}
              {!isWhatsappWindowOpen && selectedChannel === 'whatsapp' && (
                <div className="flex items-center gap-2 px-3 py-2 bg-orange-50 border-b border-orange-200">
                  <svg className="w-4 h-4 text-orange-500 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  <p className="text-xs text-orange-700 flex-1">
                    <strong>Janela de 24h expirada.</strong> Apenas templates aprovados podem ser enviados.
                  </p>
                  <button
                    onClick={openTemplateModal}
                    className="text-xs px-3 py-1.5 bg-orange-500 text-white rounded-lg hover:bg-orange-600 font-medium flex-shrink-0"
                  >
                    Enviar Template
                  </button>
                </div>
              )}

              {/* Banner de sugestões IA — 3 opções clicáveis */}
              {(loadingSuggestion || ragSuggestions.length > 0) && (
                <div className="px-3 pt-2 pb-1">
                  <div className="bg-violet-50 border border-violet-200 rounded-xl overflow-hidden">
                    {/* Cabeçalho */}
                    <div className="flex items-center justify-between px-3 py-1.5 border-b border-violet-100">
                      <span className="text-xs font-semibold text-violet-700 flex items-center gap-1">
                        ✨ Sugestões IA
                      </span>
                      {ragSuggestions.length > 0 && (
                        <button
                          onClick={() => setRagSuggestions([])}
                          className="text-violet-400 hover:text-violet-600 transition-colors p-0.5"
                          title="Ignorar sugestões"
                        >
                          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                          </svg>
                        </button>
                      )}
                    </div>
                    {/* Loading */}
                    {loadingSuggestion && ragSuggestions.length === 0 && (
                      <div className="px-3 py-2.5 flex items-center gap-2">
                        <svg className="w-3.5 h-3.5 text-violet-500 animate-spin" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                        </svg>
                        <span className="text-xs text-violet-600 italic">Gerando sugestões...</span>
                      </div>
                    )}
                    {/* Opções */}
                    {ragSuggestions.map((option, idx) => (
                      <div
                        key={idx}
                        className={`flex items-start gap-2 px-3 py-2${idx < ragSuggestions.length - 1 ? ' border-b border-violet-100' : ''}`}
                      >
                        <span className="text-[10px] font-bold text-violet-400 mt-0.5 flex-shrink-0 w-4">{idx + 1}</span>
                        <p className="text-xs text-gray-700 flex-1 leading-relaxed whitespace-pre-wrap">{option}</p>
                        <button
                          onClick={() => { setMsgText(option); setRagSuggestions([]); }}
                          className="flex-shrink-0 text-xs px-2 py-1 rounded-lg bg-violet-500 text-white hover:bg-violet-600 transition-colors font-medium"
                          title="Usar esta resposta"
                        >
                          Usar
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Aviso de erro de arquivo */}
              {fileError && (
                <div className="flex items-center gap-2 px-3 pt-2">
                  <p className="text-xs text-red-500 flex-1">{fileError}</p>
                  <button onClick={() => setFileError('')} className="text-red-400 hover:text-red-600 p-1">
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                  </button>
                </div>
              )}

              {/* Preview de arquivos pendentes */}
              {pendingFiles.length > 0 && (
                <div className="px-3 pt-2 pb-1 space-y-1.5">
                  {pendingFiles.map((file, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <div className="flex-1 flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-xl px-3 py-2 min-w-0">
                        {file.type.startsWith('image/') ? (
                          <svg className="w-4 h-4 text-blue-500 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>
                          </svg>
                        ) : file.type.startsWith('video/') ? (
                          <svg className="w-4 h-4 text-blue-500 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/>
                          </svg>
                        ) : (
                          <svg className="w-4 h-4 text-blue-500 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                          </svg>
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-800 truncate">{file.name}</p>
                          <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(0)} KB</p>
                        </div>
                        <button
                          onClick={() => setPendingFiles(prev => prev.filter((_, i) => i !== idx))}
                          className="text-gray-400 hover:text-red-500 flex-shrink-0 p-1"
                        >
                          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                          </svg>
                        </button>
                      </div>
                      {/* Botão de envio só no último item */}
                      {idx === pendingFiles.length - 1 && (
                        <button
                          onClick={handleSendFile}
                          disabled={sendingFile}
                          className="flex items-center justify-center w-11 h-11 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 transition-colors flex-shrink-0"
                          title={pendingFiles.length > 1 ? `Enviar ${pendingFiles.length} arquivos` : 'Enviar arquivo'}
                        >
                          {sendingFile
                            ? <span className="loading loading-spinner loading-sm" />
                            : <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                          }
                        </button>
                      )}
                    </div>
                  ))}

                  {/* Legenda só quando há 1 arquivo */}
                  {pendingFiles.length === 1 && (
                    <input
                      type="text"
                      placeholder="Legenda (opcional)..."
                      className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-blue-400 transition-colors"
                      value={fileCaption}
                      onChange={e => setFileCaption(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleSendFile()}
                    />
                  )}
                </div>
              )}

              {/* Checkbox — salvar como resposta rápida */}
              {msgText.trim() && (
                <div className="px-4 pb-1 flex items-center gap-1.5">
                  <input
                    id="saveAsQR"
                    type="checkbox"
                    checked={saveAsQR}
                    onChange={e => setSaveAsQR(e.target.checked)}
                    className="w-3.5 h-3.5 accent-blue-600 cursor-pointer"
                  />
                  <label htmlFor="saveAsQR" className="text-[11px] text-gray-500 cursor-pointer select-none">
                    Salvar como resposta rápida
                  </label>
                </div>
              )}

              {/* Barra principal de input */}
              <div className="px-3 pt-2 pb-2.5 flex flex-col gap-1.5">
                {/* Textarea — largura total */}
                <textarea
                  ref={textareaRef}
                  rows={3}
                  placeholder={!isWhatsappWindowOpen && selectedChannel === 'whatsapp'
                    ? 'Janela de 24h expirada — use um template'
                    : 'Digite sua mensagem...'}
                  disabled={!isWhatsappWindowOpen && selectedChannel === 'whatsapp'}
                  className="w-full text-lg border border-gray-200 rounded-xl px-3 py-2.5 outline-none focus:border-blue-400 transition-colors resize-none overflow-hidden disabled:bg-gray-50 disabled:text-gray-400 disabled:cursor-not-allowed"
                  style={{ minHeight: '4.5rem' }}
                  value={msgText}
                  onChange={e => {
                    setMsgText(e.target.value);
                    if (ragSuggestions.length > 0) setRagSuggestions([]);
                    e.target.style.height = 'auto';
                    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
                  }}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey && !isSendingRef.current) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />

                {/* Painel de briefing manual IA */}
                {showBriefPanel && (
                  <div className="flex items-center gap-2 py-1.5 border-t border-violet-100">
                    <input
                      type="text"
                      value={briefText}
                      onChange={e => setBriefText(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          const lastIn = [...messages].reverse().find(m => m.direction === 'IN');
                          if (!lastIn || !lead) return;
                          setLoadingBrief(true);
                          leadsService.suggestResponse(lead.id, lastIn.text, selectedChannel ?? 'whatsapp', briefText)
                            .then(s => { if (s.length > 0) setRagSuggestions(s); })
                            .finally(() => setLoadingBrief(false));
                        }
                        if (e.key === 'Escape') { setShowBriefPanel(false); setBriefText(''); }
                      }}
                      placeholder="Diga o que quer responder… (opcional)"
                      className="flex-1 text-sm border border-violet-200 rounded-lg px-2.5 py-1.5 outline-none focus:border-violet-400 bg-violet-50 placeholder:text-violet-300"
                      autoFocus
                    />
                    <button
                      onClick={() => {
                        const lastIn = [...messages].reverse().find(m => m.direction === 'IN');
                        if (!lastIn || !lead) return;
                        setLoadingBrief(true);
                        leadsService.suggestResponse(lead.id, lastIn.text, selectedChannel ?? 'whatsapp', briefText)
                          .then(s => { if (s.length > 0) setRagSuggestions(s); })
                          .finally(() => setLoadingBrief(false));
                      }}
                      disabled={loadingBrief}
                      className="flex items-center gap-1.5 px-3 h-8 rounded-lg bg-violet-500 text-white text-xs font-medium hover:bg-violet-600 disabled:opacity-40 transition-colors flex-shrink-0"
                    >
                      {loadingBrief ? <span className="loading loading-spinner loading-xs" /> : '✨ Sugerir'}
                    </button>
                    <button
                      onClick={() => { setShowBriefPanel(false); setBriefText(''); }}
                      className="text-gray-300 hover:text-gray-500 transition-colors flex-shrink-0"
                    >
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                      </svg>
                    </button>
                  </div>
                )}

                {/* Linha de ações abaixo do textarea */}
                <div className="flex items-center gap-1">
                  {/* Respostas rápidas */}
                  <button
                    onClick={() => setShowQR(true)}
                    title="Respostas rápidas"
                    className="flex items-center justify-center w-10 h-10 rounded-xl text-gray-400 hover:bg-gray-100 hover:text-blue-600 transition-colors flex-shrink-0"
                  >
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                    </svg>
                  </button>

                  {/* Anexar arquivo */}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    title="Enviar arquivo / documento"
                    className="flex items-center justify-center w-10 h-10 rounded-xl text-gray-400 hover:bg-gray-100 hover:text-blue-600 transition-colors flex-shrink-0"
                  >
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
                    </svg>
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    className="hidden"
                    accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png,.gif,.webp,.mp4,.mp3"
                    onChange={handleFileSelect}
                  />

                  {/* Galeria */}
                  <button
                    onClick={openGalleryModal}
                    title="Enviar da galeria"
                    className="flex items-center justify-center w-10 h-10 rounded-xl text-gray-400 hover:bg-gray-100 hover:text-purple-600 transition-colors flex-shrink-0"
                  >
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <rect x="3" y="3" width="18" height="18" rx="2"/>
                      <circle cx="8.5" cy="8.5" r="1.5"/>
                      <polyline points="21 15 16 10 5 21"/>
                    </svg>
                  </button>

                  {/* Enviar Template */}
                  <button
                    onClick={openTemplateModal}
                    title="Enviar template WhatsApp"
                    className="flex items-center justify-center w-10 h-10 rounded-xl text-gray-400 hover:bg-gray-100 hover:text-orange-500 transition-colors flex-shrink-0"
                  >
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                      <line x1="9" y1="10" x2="15" y2="10"/>
                      <line x1="9" y1="14" x2="13" y2="14"/>
                    </svg>
                  </button>

                  {/* Sugerir com IA (briefing manual) */}
                  <button
                    onClick={() => { setShowBriefPanel(v => !v); if (showBriefPanel) setBriefText(''); }}
                    title="Sugerir resposta com IA"
                    className={`flex items-center justify-center w-10 h-10 rounded-xl transition-colors flex-shrink-0 ${
                      showBriefPanel ? 'bg-violet-100 text-violet-600' : 'text-gray-400 hover:bg-violet-50 hover:text-violet-500'
                    }`}
                  >
                    {loadingBrief
                      ? <span className="loading loading-spinner loading-xs" />
                      : <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                          <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>
                        </svg>
                    }
                  </button>

                  {/* Spacer */}
                  <div className="flex-1" />

                  {/* Gravar áudio */}
                  {!msgText.trim() && !isRecording && (
                    <button
                      onClick={startRecording}
                      disabled={sending}
                      title="Gravar áudio"
                      className="flex items-center justify-center w-10 h-10 rounded-xl text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors flex-shrink-0"
                    >
                      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                        <line x1="12" y1="19" x2="12" y2="23"/>
                        <line x1="8" y1="23" x2="16" y2="23"/>
                      </svg>
                    </button>
                  )}

                  {/* UI de gravação ativa */}
                  {isRecording && (
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse flex-shrink-0" />
                      <span className="text-sm font-mono text-red-600 w-10">
                        {String(Math.floor(recordingSeconds / 60)).padStart(2, '0')}:{String(recordingSeconds % 60).padStart(2, '0')}
                      </span>
                      <button
                        onClick={() => stopRecording(false)}
                        title="Cancelar"
                        className="flex items-center justify-center w-8 h-8 rounded-xl text-gray-400 hover:bg-gray-100 transition-colors"
                      >
                        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                          <polyline points="3 6 5 6 21 6"/>
                          <path d="M19 6l-1 14H6L5 6"/>
                          <path d="M10 11v6M14 11v6"/>
                          <path d="M9 6V4h6v2"/>
                        </svg>
                      </button>
                      <button
                        onClick={() => stopRecording(true)}
                        title="Enviar áudio"
                        className="flex items-center justify-center w-10 h-10 rounded-xl bg-green-500 text-white hover:bg-green-600 transition-colors"
                      >
                        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                          <polyline points="20 6 9 17 4 12"/>
                        </svg>
                      </button>
                    </div>
                  )}

                  {/* Enviar texto */}
                  {!isRecording && (
                  <button
                    onClick={handleSend}
                    disabled={sending || !msgText.trim() || (!isWhatsappWindowOpen && selectedChannel === 'whatsapp')}
                    className="flex items-center gap-2 px-5 h-10 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 transition-colors flex-shrink-0 font-medium text-sm"
                    title="Enviar"
                  >
                    {sending
                      ? <span className="loading loading-spinner loading-sm" />
                      : (
                        <>
                          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <line x1="22" y1="2" x2="11" y2="13"/>
                            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                          </svg>
                          <span>Enviar</span>
                        </>
                      )
                    }
                  </button>
                  )}
                </div>
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
              <div key={label} className="bg-gray-50 rounded-lg p-3">
                <p className="text-base text-gray-400 mb-1">{label}</p>
                <p className="text-xl font-semibold text-gray-800 capitalize">{value}</p>
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

          {/* ── Contract button ── */}
          <div className="mt-5 pt-4 border-t border-gray-100">
            <p className="text-xs text-gray-400 mb-2 uppercase tracking-wide font-semibold">Contrato</p>
            <button
              onClick={() =>
                navigate('/contratos', {
                  state: {
                    openForLead: {
                      id: lead.id,
                      name: lead.full_name || '',
                      phone: lead.phone,
                    },
                  },
                })
              }
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="12" y1="18" x2="12" y2="12"/>
                <line x1="9" y1="15" x2="15" y2="15"/>
              </svg>
              Gerar Contrato
            </button>
          </div>
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
        suggestions={ragSuggestions}
        loadingSuggestion={loadingSuggestion}
        onRequestSuggest={brief => {
          const lastIn = [...messages].reverse().find(m => m.direction === 'IN');
          if (!lastIn || !lead) return;
          setLoadingSuggestion(true);
          leadsService
            .suggestResponse(lead.id, lastIn.text, selectedChannel ?? 'whatsapp', brief)
            .then(s => { if (s.length > 0) setRagSuggestions(s); })
            .finally(() => setLoadingSuggestion(false));
        }}
      />

      {/* ── Modal: salvar mensagem como resposta rápida ── */}
      {showSaveQRModal && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl overflow-hidden">
            <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100 bg-gradient-to-r from-blue-50 to-indigo-50">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-sm">Salvar como Resposta Rápida</h3>
                <p className="text-xs text-gray-500 mt-0.5">Disponível para toda a equipe</p>
              </div>
            </div>

            <div className="px-5 py-4 flex flex-col gap-3">
              {/* Preview do corpo */}
              <div className="bg-gray-50 rounded-xl px-3 py-2.5 border border-gray-100">
                <p className="text-xs text-gray-500 line-clamp-3 whitespace-pre-line">{pendingQRBody}</p>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Título <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  autoFocus
                  placeholder="Ex: Disponibilidade de filhotes"
                  value={qrTitle}
                  onChange={e => setQrTitle(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSaveQR()}
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-blue-400 transition-colors"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Atalho <span className="text-gray-400 font-normal">(opcional)</span></label>
                <input
                  type="text"
                  placeholder="Ex: disponibilidade"
                  value={qrShortcut}
                  onChange={e => setQrShortcut(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSaveQR()}
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-blue-400 transition-colors"
                />
              </div>
            </div>

            <div className="flex gap-2 px-5 pb-5">
              <button
                onClick={() => { setShowSaveQRModal(false); setSaveAsQR(false); }}
                className="flex-1 py-2.5 rounded-xl text-sm text-gray-600 bg-gray-100 hover:bg-gray-200 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleSaveQR}
                disabled={savingQR || !qrTitle.trim()}
                className="flex-1 py-2.5 rounded-xl text-sm text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 transition-colors flex items-center justify-center gap-1.5"
              >
                {savingQR
                  ? <span className="loading loading-spinner loading-xs" />
                  : 'Salvar resposta'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Toast: resposta rápida salva ── */}
      {qrSavedToast && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 bg-gray-900 text-white text-xs px-4 py-2.5 rounded-full shadow-lg flex items-center gap-2 animate-bounce-in">
          <svg className="w-3.5 h-3.5 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          Resposta rápida salva com sucesso
        </div>
      )}

      {/* ── Modal de envio de template WhatsApp ── */}
      {showTemplateModal && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">

            {/* ── TELA 1: Lista de templates ── */}
            {templateModalView === 'list' && (<>
              <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100">
                <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4 text-orange-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  </svg>
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-gray-800 text-sm">Enviar Template WhatsApp</p>
                  <p className="text-xs text-gray-500">{approvedTemplates.length} template(s) aprovado(s)</p>
                </div>
                <button onClick={() => setShowTemplateModal(false)} className="text-gray-400 hover:text-gray-600 p-1">
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
                {approvedTemplates.length === 0 ? (
                  <div className="text-center py-10">
                    <p className="text-gray-500 text-sm">Nenhum template aprovado encontrado.</p>
                    <p className="text-xs text-gray-400 mt-1">Crie e aguarde a aprovação em <strong>Templates WhatsApp</strong>.</p>
                  </div>
                ) : (
                  approvedTemplates.map(t => (
                    <button
                      key={t.id}
                      onClick={() => {
                        setSelectedTemplate(t);
                        setTemplateVars(Array.from({ length: t.variable_count }, (_, i) =>
                          i === 0 ? (lead?.full_name ?? '') : ''
                        ));
                        setTemplateMediaUrl('');
                        setTemplateError('');
                        setShowTemplateGalleryPicker(false);
                        setTemplateModalView('detail');
                      }}
                      className="w-full text-left rounded-xl border border-gray-200 hover:border-orange-300 hover:bg-orange-50/40 transition-colors overflow-hidden group"
                    >
                      {/* Miniatura do cabeçalho se tiver mídia */}
                      {(t.header_type === 'IMAGE' || t.header_type === 'VIDEO') && t.header_media_url && (
                        <div className="w-full h-28 bg-gray-100 overflow-hidden">
                          {t.header_type === 'IMAGE' ? (
                            <img src={t.header_media_url} alt="" className="w-full h-full object-cover" />
                          ) : (
                            <VideoThumbnail src={t.header_media_url} className="w-full h-full" />
                          )}
                        </div>
                      )}
                      <div className="p-3">
                        <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
                          <span className="font-mono text-sm font-bold text-gray-900">{t.name}</span>
                          <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full font-medium">✓ Aprovado</span>
                          {t.header_type && t.header_type !== 'NONE' && (
                            <span className="text-[10px] bg-purple-50 text-purple-600 px-1.5 py-0.5 rounded-full font-medium">
                              {t.header_type === 'IMAGE' ? '🖼 Imagem' : t.header_type === 'VIDEO' ? '▶ Vídeo' : t.header_type === 'DOCUMENT' ? '📄 Doc' : `T ${t.header_text}`}
                            </span>
                          )}
                          {t.variable_count > 0 && (
                            <span className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded-full font-medium">
                              {t.variable_count} var
                            </span>
                          )}
                          {t.category && (
                            <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full font-medium uppercase">{t.category}</span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600 line-clamp-2 leading-relaxed">{t.body_text}</p>
                        {t.footer_text && <p className="text-xs text-gray-400 italic mt-1 truncate">{t.footer_text}</p>}
                      </div>
                      <div className="px-3 pb-2.5 flex items-center justify-end">
                        <span className="text-xs text-orange-500 font-medium group-hover:text-orange-600">Usar este template →</span>
                      </div>
                    </button>
                  ))
                )}
              </div>

              <div className="px-5 py-3 border-t border-gray-100">
                <button onClick={() => setShowTemplateModal(false)} className="w-full py-2 rounded-xl text-sm font-medium text-gray-600 bg-white border border-gray-200 hover:bg-gray-50">
                  Cancelar
                </button>
              </div>
            </>)}

            {/* ── TELA 2: Detalhe do template selecionado ── */}
            {templateModalView === 'detail' && selectedTemplate && (<>
              {/* Header com voltar */}
              <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-orange-50">
                <button
                  onClick={() => { setTemplateModalView('list'); setSelectedTemplate(null); setTemplateError(''); }}
                  className="flex items-center justify-center w-8 h-8 rounded-lg hover:bg-orange-100 text-orange-600 transition-colors flex-shrink-0"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <polyline points="15 18 9 12 15 6"/>
                  </svg>
                </button>
                <div className="flex-1 min-w-0">
                  <p className="font-bold text-gray-800 text-sm truncate">{selectedTemplate.name}</p>
                  <p className="text-xs text-orange-600">Template selecionado</p>
                </div>
                <button onClick={() => setShowTemplateModal(false)} className="text-gray-400 hover:text-gray-600 p-1 flex-shrink-0">
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">

                {/* Preview estilo WhatsApp */}
                <div className="bg-[#e5ddd5] rounded-xl p-3">
                  <p className="text-[10px] text-gray-500 uppercase tracking-wide font-semibold mb-2">Prévia da mensagem</p>
                  <div className="bg-white rounded-xl shadow-sm overflow-hidden max-w-xs mx-auto">
                    {/* Header de mídia */}
                    {selectedTemplate.header_type === 'IMAGE' && selectedTemplate.header_media_url && (
                      <img src={selectedTemplate.header_media_url} alt="" className="w-full h-36 object-cover" />
                    )}
                    {selectedTemplate.header_type === 'VIDEO' && selectedTemplate.header_media_url && (
                      <div className="w-full h-36 overflow-hidden">
                        <VideoThumbnail src={selectedTemplate.header_media_url} className="w-full h-full" />
                      </div>
                    )}
                    {selectedTemplate.header_type === 'TEXT' && selectedTemplate.header_text && (
                      <div className="px-3 pt-3 pb-1">
                        <p className="font-bold text-gray-900 text-sm">{selectedTemplate.header_text}</p>
                      </div>
                    )}
                    {/* Body */}
                    <div className="px-3 py-2">
                      <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                        {templateVars.reduce((txt, val, i) => txt.replace(`{{${i + 1}}}`, val || `{{${i + 1}}}`), selectedTemplate.body_text)}
                      </p>
                    </div>
                    {/* Footer */}
                    {selectedTemplate.footer_text && (
                      <div className="px-3 pb-2.5">
                        <p className="text-xs text-gray-400 italic">{selectedTemplate.footer_text}</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Variáveis */}
                {selectedTemplate.variable_count > 0 && (
                  <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 space-y-3">
                    <p className="text-sm font-semibold text-blue-800">Variáveis</p>
                    {Array.from({ length: selectedTemplate.variable_count }).map((_, i) => (
                      <div key={i}>
                        <label className="block text-xs text-blue-700 mb-1 font-medium">
                          {`{{${i + 1}}}`} {i === 0 ? '— Nome' : ''}
                        </label>
                        <input
                          type="text"
                          value={templateVars[i] ?? ''}
                          onChange={e => {
                            const v = [...templateVars];
                            v[i] = e.target.value;
                            setTemplateVars(v);
                          }}
                          placeholder={i === 0 ? lead?.full_name ?? '' : `Valor ${i + 1}`}
                          className="w-full border border-blue-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white"
                        />
                      </div>
                    ))}
                  </div>
                )}

                {/* Mídia do cabeçalho */}
                {['IMAGE', 'VIDEO', 'DOCUMENT'].includes(selectedTemplate.header_type) && (
                  <div className="bg-purple-50 border border-purple-100 rounded-xl p-4 space-y-3">
                    <p className="text-sm font-semibold text-purple-800">
                      {selectedTemplate.header_type === 'IMAGE' ? '🖼 Imagem do cabeçalho' : selectedTemplate.header_type === 'VIDEO' ? '▶ Vídeo do cabeçalho' : '📄 Documento do cabeçalho'}
                      <span className="text-red-500 ml-1">*</span>
                    </p>

                    <div className="flex gap-2">
                      <input
                        ref={mediaFileInputRef}
                        type="file"
                        className="hidden"
                        accept={selectedTemplate.header_type === 'IMAGE' ? 'image/jpeg,image/png' : selectedTemplate.header_type === 'VIDEO' ? 'video/mp4' : 'application/pdf'}
                        onChange={e => { setShowTemplateGalleryPicker(false); handleMediaFileUpload(e); }}
                      />
                      <button
                        type="button"
                        onClick={() => { setShowTemplateGalleryPicker(false); mediaFileInputRef.current?.click(); }}
                        disabled={uploadingMedia}
                        className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg border-2 border-dashed border-purple-300 bg-white hover:bg-purple-50 text-purple-700 text-sm font-medium transition-colors disabled:opacity-60"
                      >
                        {uploadingMedia
                          ? <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                          : <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                        }
                        {uploadingMedia ? 'Enviando…' : 'Dispositivo'}
                      </button>
                      {selectedTemplate.header_type !== 'DOCUMENT' && (
                        <button
                          type="button"
                          onClick={() => showTemplateGalleryPicker ? setShowTemplateGalleryPicker(false) : openTemplateGalleryPicker(selectedTemplate.header_type as 'IMAGE' | 'VIDEO')}
                          className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg border-2 text-sm font-medium transition-colors ${showTemplateGalleryPicker ? 'border-purple-500 bg-purple-100 text-purple-800' : 'border-purple-300 bg-white hover:bg-purple-50 text-purple-700'}`}
                        >
                          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>
                          </svg>
                          Da galeria
                        </button>
                      )}
                    </div>

                    {/* Galeria picker */}
                    {showTemplateGalleryPicker && (
                      <div className="bg-white border border-purple-200 rounded-xl overflow-hidden">
                        {loadingTemplateGallery ? (
                          <div className="flex items-center justify-center h-28">
                            <svg className="w-5 h-5 text-purple-400 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                          </div>
                        ) : templateGalleryItems.length === 0 ? (
                          <div className="flex flex-col items-center justify-center h-24 text-center px-4">
                            <p className="text-sm text-gray-500">Nenhum item na galeria.</p>
                            <p className="text-xs text-gray-400 mt-0.5">Use "Dispositivo" ou a página Galeria.</p>
                          </div>
                        ) : (
                          <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 p-2 max-h-64 overflow-y-auto">
                            {templateGalleryItems.map(item => (
                              <button
                                key={item.id}
                                type="button"
                                onClick={() => { setTemplateMediaUrl(item.file_url); setShowTemplateGalleryPicker(false); }}
                                className={`flex flex-col rounded-lg overflow-hidden border-2 transition-all bg-gray-50 group ${
                                  templateMediaUrl === item.file_url
                                    ? 'border-purple-500'
                                    : 'border-transparent hover:border-purple-400'
                                }`}
                                title={item.name}
                              >
                                <div className="relative w-full aspect-video overflow-hidden">
                                  {item.media_type === 'IMAGE'
                                    ? <img src={item.file_url} alt={item.name} className="w-full h-full object-cover" />
                                    : <VideoThumbnail src={item.file_url} className="w-full h-full" />
                                  }
                                  <div className="absolute inset-0 bg-purple-600/0 group-hover:bg-purple-600/20 transition-colors" />

                                  {/* Play preview — only on videos, stops propagation so it doesn't select */}
                                  {item.media_type === 'VIDEO' && (
                                    <button
                                      type="button"
                                      onClick={e => { e.stopPropagation(); setTemplateVideoPreview(item); }}
                                      className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                                      title="Pré-visualizar vídeo"
                                    >
                                      <div className="w-9 h-9 rounded-full bg-black/60 flex items-center justify-center shadow-lg">
                                        <svg className="w-4 h-4 text-white ml-0.5" viewBox="0 0 24 24" fill="currentColor">
                                          <path d="M8 5v14l11-7z"/>
                                        </svg>
                                      </div>
                                    </button>
                                  )}
                                </div>
                                <div className="px-1.5 py-1">
                                  <p className="text-[11px] font-medium text-gray-700 truncate">{item.name}</p>
                                  {item.description && (
                                    <p className="text-[10px] text-gray-400 truncate">{item.description}</p>
                                  )}
                                </div>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Mídia selecionada */}
                    {templateMediaUrl && (
                      <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                        <svg className="w-4 h-4 text-green-600 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><polyline points="20 6 9 17 4 12"/></svg>
                        <span className="text-xs text-green-700 truncate flex-1">{templateMediaUrl.split('/').pop()}</span>
                        <button type="button" onClick={() => setTemplateMediaUrl('')} className="text-green-500 hover:text-green-700 flex-shrink-0">
                          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {templateError && (
                <div className="mx-4 mb-1 px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700 flex items-start gap-2">
                  <svg className="w-4 h-4 mt-0.5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  {templateError}
                </div>
              )}

              <div className="flex gap-3 px-4 py-3 border-t border-gray-100">
                <button
                  onClick={() => { setTemplateModalView('list'); setSelectedTemplate(null); setTemplateError(''); }}
                  className="flex items-center gap-1 px-4 py-2 rounded-xl text-sm font-medium text-gray-600 bg-white border border-gray-200 hover:bg-gray-50"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><polyline points="15 18 9 12 15 6"/></svg>
                  Voltar
                </button>
                <button
                  onClick={handleSendTemplate}
                  disabled={sendingTemplate}
                  className="flex-1 py-2 rounded-xl text-sm font-semibold text-white bg-orange-500 hover:bg-orange-600 disabled:opacity-50 transition-colors"
                >
                  {sendingTemplate
                    ? <svg className="w-4 h-4 animate-spin mx-auto" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                    : 'Enviar Template'}
                </button>
              </div>
            </>)}

            {/* ── Mini video preview inside template modal ── */}
            {templateVideoPreview && (
              <div
                className="absolute inset-0 z-10 flex items-center justify-center bg-black/70 backdrop-blur-sm rounded-2xl"
                onClick={() => setTemplateVideoPreview(null)}
              >
                <div
                  className="relative w-full mx-4 bg-black rounded-2xl overflow-hidden shadow-2xl"
                  onClick={e => e.stopPropagation()}
                >
                  {/* Header */}
                  <div className="flex items-center justify-between px-4 py-2.5 bg-gray-900">
                    <p className="text-white text-sm font-medium truncate max-w-xs">{templateVideoPreview.name}</p>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {/* Select button */}
                      <button
                        type="button"
                        onClick={() => {
                          setTemplateMediaUrl(templateVideoPreview.file_url);
                          setShowTemplateGalleryPicker(false);
                          setTemplateVideoPreview(null);
                        }}
                        className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                          templateMediaUrl === templateVideoPreview.file_url
                            ? 'bg-purple-600 text-white hover:bg-purple-700'
                            : 'bg-white/10 text-white hover:bg-white/20'
                        }`}
                      >
                        {templateMediaUrl === templateVideoPreview.file_url ? (
                          <>
                            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}><polyline points="20 6 9 17 4 12"/></svg>
                            Selecionado
                          </>
                        ) : (
                          <>
                            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
                            Usar este
                          </>
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => setTemplateVideoPreview(null)}
                        className="text-white/60 hover:text-white p-1 transition-colors"
                      >
                        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                      </button>
                    </div>
                  </div>

                  {/* Video player */}
                  <video
                    src={templateVideoPreview.file_url}
                    controls
                    autoPlay
                    className="w-full max-h-64 bg-black"
                  />

                  {/* Description */}
                  {templateVideoPreview.description && (
                    <div className="px-4 py-2.5 bg-gray-900 border-t border-white/10">
                      <p className="text-white/70 text-xs leading-relaxed">{templateVideoPreview.description}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

          </div>
        </div>
      )}

      {/* ── Modal de Galeria ───────────────────────────────────────────────── */}
      {showGalleryModal && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">

            {/* Header */}
            <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100">
              <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-purple-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <rect x="3" y="3" width="18" height="18" rx="2"/>
                  <circle cx="8.5" cy="8.5" r="1.5"/>
                  <polyline points="21 15 16 10 5 21"/>
                </svg>
              </div>
              <div className="flex-1">
                <p className="font-semibold text-gray-800 text-sm">Enviar da Galeria</p>
                <p className="text-xs text-gray-500">
                  {gallerySelections.size === 0
                    ? 'Selecione uma ou mais mídias para enviar'
                    : `${gallerySelections.size} item(s) selecionado(s)`}
                </p>
              </div>
              <input
                ref={galleryUploadInputRef}
                type="file"
                multiple
                className="hidden"
                accept="image/jpeg,image/png,image/gif,image/webp,video/mp4,video/quicktime,video/webm,application/pdf"
                onChange={handleGalleryModalUpload}
              />
              <button
                onClick={() => galleryUploadInputRef.current?.click()}
                disabled={uploadingGalleryItem}
                title="Adicionar à galeria"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-50 hover:bg-purple-100 text-purple-700 text-xs font-semibold transition-colors disabled:opacity-60 flex-shrink-0"
              >
                {uploadingGalleryItem
                  ? <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                  : <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                }
                Upload
              </button>
              <button onClick={() => setShowGalleryModal(false)} className="text-gray-400 hover:text-gray-600 p-1">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>

            {/* Filter tabs */}
            <div className="flex items-center gap-1 px-5 pt-3 pb-1 flex-shrink-0">
              {(['ALL', 'IMAGE', 'VIDEO', 'DOCUMENT'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setGalleryFilter(f)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    galleryFilter === f ? 'bg-purple-100 text-purple-700' : 'text-gray-500 hover:bg-gray-100'
                  }`}
                >
                  {f === 'ALL' ? 'Todos' : f === 'IMAGE' ? 'Imagens' : f === 'VIDEO' ? 'Vídeos' : 'PDFs'}
                </button>
              ))}
            </div>

            {/* Grid — scrollable */}
            <div className="flex-1 overflow-y-auto px-5 py-3 min-h-0">
              {loadingGallery ? (
                <div className="flex items-center justify-center h-40">
                  <svg className="w-7 h-7 text-gray-400 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                  </svg>
                </div>
              ) : galleryItems.filter(i => galleryFilter === 'ALL' || i.media_type === galleryFilter).length === 0 ? (
                <div className="flex flex-col items-center justify-center h-40 text-center">
                  <p className="text-gray-500 text-sm">Nenhum item encontrado.</p>
                  <p className="text-xs text-gray-400 mt-1">Adicione imagens ou vídeos na <strong>Galeria de Mídia</strong>.</p>
                </div>
              ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
                  {galleryItems
                    .filter(i => galleryFilter === 'ALL' || i.media_type === galleryFilter)
                    .map(item => {
                      const isSelected = gallerySelections.has(item.id);
                      return (
                        <button
                          key={item.id}
                          onClick={() => {
                            setGallerySelections(prev => {
                              const next = new Map(prev);
                              if (next.has(item.id)) {
                                next.delete(item.id);
                              } else {
                                next.set(item.id, { item, sendDesc: !!item.description });
                              }
                              return next;
                            });
                          }}
                          className={`relative rounded-xl overflow-hidden border-2 transition-all bg-white text-left ${
                            isSelected
                              ? 'border-purple-500 ring-2 ring-purple-200'
                              : 'border-gray-200 hover:border-purple-300'
                          }`}
                        >
                          <div className="aspect-square bg-gray-100 overflow-hidden relative">
                            {item.media_type === 'IMAGE'
                              ? <img src={item.file_url} alt={item.name} className="w-full h-full object-cover" />
                              : item.media_type === 'VIDEO'
                              ? <VideoThumbnail src={item.file_url} />
                              : (
                                <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-gradient-to-br from-red-50 to-red-100">
                                  <svg className="w-9 h-9 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                                    <polyline points="14 2 14 8 20 8"/>
                                    <line x1="9" y1="13" x2="15" y2="13"/>
                                    <line x1="9" y1="17" x2="15" y2="17"/>
                                  </svg>
                                  <span className="text-red-600 text-xs font-bold">PDF</span>
                                </div>
                              )
                            }
                            {/* Play preview button — only on videos */}
                            {item.media_type === 'VIDEO' && (
                              <button
                                onClick={e => { e.stopPropagation(); setGalleryVideoPreview(item); }}
                                className="absolute inset-0 flex items-center justify-center bg-black/0 hover:bg-black/30 transition-colors group/play"
                                title="Pré-visualizar vídeo"
                              >
                                <div className="w-10 h-10 rounded-full bg-black/60 flex items-center justify-center opacity-0 group-hover/play:opacity-100 transition-opacity shadow-lg">
                                  <svg className="w-5 h-5 text-white ml-0.5" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M8 5v14l11-7z"/>
                                  </svg>
                                </div>
                              </button>
                            )}
                          </div>

                          {/* Check badge */}
                          <div className={`absolute top-1.5 right-1.5 w-5 h-5 rounded-full flex items-center justify-center shadow transition-all ${
                            isSelected ? 'bg-purple-500' : 'bg-white/80 border border-gray-300'
                          }`}>
                            {isSelected && (
                              <svg className="w-3 h-3 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
                                <polyline points="20 6 9 17 4 12"/>
                              </svg>
                            )}
                          </div>

                          {/* Type badge */}
                          <div className={`absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wide ${
                            item.media_type === 'IMAGE' ? 'bg-blue-500/80 text-white'
                            : item.media_type === 'VIDEO' ? 'bg-purple-600/80 text-white'
                            : 'bg-red-500/80 text-white'
                          }`}>
                            {item.media_type === 'IMAGE' ? 'IMG' : item.media_type === 'VIDEO' ? 'VID' : 'PDF'}
                          </div>

                          <div className="px-2 pt-1.5 pb-2">
                            <p className="text-[11px] font-semibold text-gray-800 truncate leading-tight" title={item.name}>
                              {item.name}
                            </p>
                            {item.description && (
                              <p
                                className="text-[10px] text-gray-500 mt-0.5 leading-snug"
                                style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
                                title={item.description}
                              >
                                {item.description}
                              </p>
                            )}
                          </div>
                        </button>
                      );
                    })}
                </div>
              )}
            </div>

            {/* ── Selection queue — each selected item with sendDesc toggle ── */}
            {gallerySelections.size > 0 && (
              <div className="border-t border-gray-100 px-5 py-3 flex-shrink-0 max-h-60 overflow-y-auto space-y-2">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  Para enviar ({gallerySelections.size})
                </p>
                {Array.from(gallerySelections.values()).map(({ item, sendDesc }) => (
                  <div key={item.id} className="flex items-start gap-3 bg-gray-50 rounded-xl p-2.5">
                    {/* Thumb */}
                    <div className="w-12 h-12 rounded-lg overflow-hidden flex-shrink-0 bg-gray-200">
                      {item.media_type === 'IMAGE'
                        ? <img src={item.file_url} alt={item.name} className="w-full h-full object-cover" />
                        : item.media_type === 'VIDEO'
                        ? <VideoThumbnail src={item.file_url} />
                        : (
                          <div className="w-full h-full flex items-center justify-center bg-red-50">
                            <svg className="w-6 h-6 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                              <polyline points="14 2 14 8 20 8"/>
                            </svg>
                          </div>
                        )
                      }
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-gray-800 truncate">{item.name}</p>
                      {item.description ? (
                        <p className="text-xs text-gray-500 mt-0.5 leading-snug break-words">
                          {item.description}
                        </p>
                      ) : (
                        <p className="text-xs text-gray-400 italic mt-0.5">Sem descrição</p>
                      )}

                      {/* Checkbox: send description */}
                      {item.description && (
                        <label className="flex items-center gap-1.5 mt-1.5 cursor-pointer select-none w-fit">
                          <input
                            type="checkbox"
                            checked={sendDesc}
                            onChange={() => {
                              setGallerySelections(prev => {
                                const next = new Map(prev);
                                const sel = next.get(item.id);
                                if (sel) next.set(item.id, { ...sel, sendDesc: !sel.sendDesc });
                                return next;
                              });
                            }}
                            className="w-3.5 h-3.5 rounded accent-purple-600 cursor-pointer"
                          />
                          <span className="text-[11px] text-gray-600">Enviar descrição como mensagem</span>
                        </label>
                      )}
                    </div>

                    {/* Remove from selection */}
                    <button
                      onClick={() => setGallerySelections(prev => {
                        const next = new Map(prev); next.delete(item.id); return next;
                      })}
                      className="text-gray-300 hover:text-red-400 transition-colors flex-shrink-0 mt-0.5"
                    >
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Error */}
            {galleryError && (
              <div className="mx-5 mb-1 px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700 flex items-start gap-2">
                <svg className="w-4 h-4 mt-0.5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                {galleryError}
              </div>
            )}

            {/* Footer */}
            <div className="flex gap-3 px-5 py-4 border-t border-gray-100 flex-shrink-0">
              <button
                onClick={() => setShowGalleryModal(false)}
                className="flex-1 py-2 rounded-xl text-sm font-medium text-gray-600 bg-white border border-gray-200 hover:bg-gray-100"
              >
                Cancelar
              </button>
              <button
                onClick={handleSendGalleryItem}
                disabled={gallerySelections.size === 0 || sendingGallery}
                className="flex-1 py-2 rounded-xl text-sm font-semibold text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
              >
                {sendingGallery ? (
                  <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                  </svg>
                ) : (
                  <>
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <line x1="22" y1="2" x2="11" y2="13"/>
                      <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                    </svg>
                    {gallerySelections.size > 1 ? `Enviar ${gallerySelections.size} mídias` : 'Enviar'}
                  </>
                )}
              </button>
            </div>

            {/* ── Mini video preview player (inside modal, above everything) ── */}
            {galleryVideoPreview && (
              <div
                className="absolute inset-0 z-10 flex items-center justify-center bg-black/70 backdrop-blur-sm rounded-2xl"
                onClick={() => setGalleryVideoPreview(null)}
              >
                <div
                  className="relative w-full max-w-lg mx-4 bg-black rounded-2xl overflow-hidden shadow-2xl"
                  onClick={e => e.stopPropagation()}
                >
                  {/* Player header */}
                  <div className="flex items-center justify-between px-4 py-2.5 bg-gray-900">
                    <p className="text-white text-sm font-medium truncate max-w-xs">{galleryVideoPreview.name}</p>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {/* Select / deselect from preview */}
                      <button
                        onClick={() => {
                          setGallerySelections(prev => {
                            const next = new Map(prev);
                            if (next.has(galleryVideoPreview.id)) {
                              next.delete(galleryVideoPreview.id);
                            } else {
                              next.set(galleryVideoPreview.id, { item: galleryVideoPreview, sendDesc: !!galleryVideoPreview.description });
                            }
                            return next;
                          });
                          setGalleryVideoPreview(null);
                        }}
                        className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                          gallerySelections.has(galleryVideoPreview.id)
                            ? 'bg-purple-600 text-white hover:bg-purple-700'
                            : 'bg-white/10 text-white hover:bg-white/20'
                        }`}
                      >
                        {gallerySelections.has(galleryVideoPreview.id) ? (
                          <>
                            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
                              <polyline points="20 6 9 17 4 12"/>
                            </svg>
                            Selecionado
                          </>
                        ) : (
                          <>
                            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                              <circle cx="12" cy="12" r="10"/>
                              <line x1="12" y1="8" x2="12" y2="16"/>
                              <line x1="8" y1="12" x2="16" y2="12"/>
                            </svg>
                            Selecionar
                          </>
                        )}
                      </button>
                      <button
                        onClick={() => setGalleryVideoPreview(null)}
                        className="text-white/60 hover:text-white p-1 transition-colors"
                      >
                        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                      </button>
                    </div>
                  </div>

                  {/* Video */}
                  <video
                    src={galleryVideoPreview.file_url}
                    controls
                    autoPlay
                    className="w-full max-h-72 bg-black"
                  />

                  {/* Description */}
                  {galleryVideoPreview.description && (
                    <div className="px-4 py-2.5 bg-gray-900 border-t border-white/10">
                      <p className="text-white/70 text-xs leading-relaxed">{galleryVideoPreview.description}</p>
                    </div>
                  )}
                </div>
              </div>
            )}
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
  lead_classification: string;
  is_archived: string;
};

const FILTER_DEFAULTS: LeadFilter = { tier: '', status: '', is_ai_active: '', search: '', lead_classification: '', is_archived: '' };

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
  const [reclassifyingAll, setReclassifyingAll] = useState(false);
  const [reclassifyAllDone, setReclassifyAllDone] = useState(false);

  const buildParams = (f: LeadFilter, p: number) => {
    const params: Record<string, string | number | boolean> = { page: p };
    if (f.tier) params.tier = f.tier;
    if (f.status) params.status = f.status;
    if (f.is_ai_active) params.is_ai_active = f.is_ai_active === 'true';
    if (f.search) params.search = f.search;
    if (f.lead_classification) params.lead_classification = f.lead_classification;
    params.is_archived = f.is_archived === 'true';
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
        <div className="flex items-center justify-between px-3 py-3 border-b border-gray-100 bg-white flex-shrink-0">
          <div>
            <p className="font-semibold text-base text-gray-800">Leads</p>
            <p className="text-sm text-gray-400">{total} total</p>
          </div>
          <div className="flex items-center gap-1">
            {/* Classificar todos com IA */}
            <button
              onClick={async () => {
                setReclassifyingAll(true);
                setReclassifyAllDone(false);
                try {
                  await leadsService.reclassifyAll();
                  setReclassifyAllDone(true);
                  setTimeout(() => setReclassifyAllDone(false), 4000);
                } catch { /* silencia */ } finally {
                  setReclassifyingAll(false);
                }
              }}
              disabled={reclassifyingAll}
              title="Classificar todos os leads com IA"
              className={`flex items-center justify-center w-10 h-10 rounded-xl transition-colors disabled:opacity-40 ${
                reclassifyAllDone ? 'bg-violet-100 text-violet-600' : 'text-gray-400 hover:bg-violet-50 hover:text-violet-500'
              }`}
            >
              {reclassifyingAll
                ? <span className="loading loading-spinner loading-xs" />
                : reclassifyAllDone
                  ? <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><polyline points="20 6 9 17 4 12"/></svg>
                  : <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>
              }
            </button>

            <button
              onClick={() => setShowFilters(v => !v)}
              className={`flex items-center justify-center w-10 h-10 rounded-xl transition-colors ${
                hasActiveFilters ? 'bg-blue-100 text-blue-600' : 'text-gray-400 hover:bg-gray-100'
              }`}
              title="Filtros"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
              </svg>
            </button>
          </div>
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
              className="w-full pl-8 pr-3 py-2 text-base border border-gray-200 rounded-lg outline-none focus:border-blue-400 bg-gray-50"
              value={filters.search}
              onChange={e => applyFilter('search', e.target.value)}
            />
          </div>
        </div>

        {/* Quick classification filter buttons */}
        <div className="px-3 py-2 border-b border-gray-100 flex items-center gap-1.5 flex-shrink-0 overflow-x-auto">
          {([
            { key: '',            label: 'Todos',     icon: null, activeClass: 'bg-gray-800 text-white',  defaultClass: 'bg-gray-100 text-gray-500 hover:bg-gray-200' },
            { key: 'DANGER_LEAD', label: 'Danger',    icon: '⚠️', activeClass: 'bg-red-900 text-white',   defaultClass: 'bg-red-50 text-red-900 hover:bg-red-100 font-semibold' },
            { key: 'HOT_LEAD',    label: 'Hot',       icon: '🔥', activeClass: 'bg-red-500 text-white',   defaultClass: 'bg-red-50 text-red-600 hover:bg-red-100' },
            { key: 'WARM_LEAD',   label: 'Warm',      icon: '🟡', activeClass: 'bg-amber-500 text-white', defaultClass: 'bg-amber-50 text-amber-600 hover:bg-amber-100' },
            { key: 'COLD_LEAD',   label: 'Cold',      icon: '❄️', activeClass: 'bg-blue-500 text-white',  defaultClass: 'bg-blue-50 text-blue-600 hover:bg-blue-100' },
            { key: 'ARCHIVED',    label: 'Arquivado', icon: '📁', activeClass: 'bg-gray-500 text-white',  defaultClass: 'bg-gray-100 text-gray-500 hover:bg-gray-200' },
          ] as const).map(({ key, label, icon, activeClass, defaultClass }) => {
            const isArchived = key === 'ARCHIVED';
            const isActive = isArchived
              ? filters.is_archived === 'true'
              : filters.lead_classification === key && filters.is_archived !== 'true';
            return (
              <button
                key={key}
                onClick={() => {
                  if (isArchived) {
                    const next = { ...filters, lead_classification: '', is_archived: filters.is_archived === 'true' ? '' : 'true' };
                    setFilters(next);
                    load(next, 1);
                  } else {
                    const next = { ...filters, lead_classification: filters.lead_classification === key ? '' : key, is_archived: '' };
                    setFilters(next);
                    load(next, 1);
                  }
                }}
                className={`flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-semibold flex-shrink-0 transition-colors ${isActive ? activeClass : defaultClass}`}
              >
                {icon && <span>{icon}</span>}
                {label}
              </button>
            );
          })}
        </div>

        {/* Filter dropdowns (collapsible) */}
        {showFilters && (
          <div className="px-3 py-2 border-b border-gray-100 bg-gray-50 flex flex-wrap gap-2 flex-shrink-0">
            <select
              className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 bg-white outline-none flex-1 min-w-[80px]"
              value={filters.tier}
              onChange={e => applyFilter('tier', e.target.value)}
            >
              <option value="">Tier</option>
              <option value="A">A</option>
              <option value="B">B</option>
              <option value="C">C</option>
            </select>
            <select
              className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 bg-white outline-none flex-1 min-w-[90px]"
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
              className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 bg-white outline-none flex-1 min-w-[80px]"
              value={filters.is_ai_active}
              onChange={e => applyFilter('is_ai_active', e.target.value)}
            >
              <option value="">IA</option>
              <option value="true">Ativa</option>
              <option value="false">Humano</option>
            </select>
            {hasActiveFilters && (
              <button onClick={clearFilters} className="text-sm text-red-500 hover:underline">Limpar</button>
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
                .sort((a, b) =>
                  new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
                )
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
                  className="w-full py-3 text-sm text-blue-600 hover:bg-gray-50 border-t"
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
            <p className="text-base font-medium">Selecione um lead</p>
            <p className="text-sm mt-1">Escolha uma conversa na lista ao lado</p>
          </div>
        )}
      </div>
    </div>
  );
}
