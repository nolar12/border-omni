import { useEffect, useRef, useState } from 'react';
import { settingsService } from '../services/settings';
import type { InitialMessageMedia, OrgSettings } from '../types';

function ToggleSwitch({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (val: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
        checked ? 'bg-blue-600' : 'bg-gray-200'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      <span
        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          checked ? 'translate-x-5' : 'translate-x-0'
        }`}
      />
    </button>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<OrgSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [botEnabled, setBotEnabled] = useState(false);
  const [initialMessage, setInitialMessage] = useState('');
  const [sequenceMessage, setSequenceMessage] = useState('');
  const [linkMessage, setLinkMessage] = useState('');
  const [media, setMedia] = useState<InitialMessageMedia[]>([]);

  const [useConversationTemplate, setUseConversationTemplate] = useState(true);
  const [conversationTemplate, setConversationTemplate] = useState('');

  const [offHoursEnabled, setOffHoursEnabled] = useState(false);
  const [offHoursStart, setOffHoursStart] = useState('21:00');
  const [offHoursEnd, setOffHoursEnd] = useState('06:00');
  const [offHoursMessage, setOffHoursMessage] = useState('');
  const [offHoursTimezone, setOffHoursTimezone] = useState('America/Sao_Paulo');

  const [savingBot, setSavingBot] = useState(false);
  const [savingMsg, setSavingMsg] = useState(false);
  const [savedMsg, setSavedMsg] = useState(false);
  const [savedBot, setSavedBot] = useState(false);
  const [savingSeq, setSavingSeq] = useState(false);
  const [savedSeq, setSavedSeq] = useState(false);
  const [savingLink, setSavingLink] = useState(false);
  const [savedLink, setSavedLink] = useState(false);
  const [savingAI, setSavingAI] = useState(false);
  const [savedAI, setSavedAI] = useState(false);
  const [savingOffHours, setSavingOffHours] = useState(false);
  const [savedOffHours, setSavedOffHours] = useState(false);
  const [uploadingMedia, setUploadingMedia] = useState(false);
  const [deletingMediaId, setDeletingMediaId] = useState<number | null>(null);

  const mediaInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      settingsService.getSettings(),
      settingsService.getMedia(),
    ])
      .then(([cfg, med]) => {
        setSettings(cfg);
        setBotEnabled(cfg.bot_enabled);
        setInitialMessage(cfg.initial_message ?? '');
        setSequenceMessage(cfg.sequence_message ?? '');
        setLinkMessage(cfg.link_message ?? '');
        setUseConversationTemplate(cfg.use_conversation_template ?? true);
        setConversationTemplate(cfg.conversation_template ?? '');
        setOffHoursEnabled(cfg.off_hours_enabled ?? false);
        setOffHoursStart(cfg.off_hours_start ?? '21:00');
        setOffHoursEnd(cfg.off_hours_end ?? '06:00');
        setOffHoursMessage(cfg.off_hours_message ?? '');
        setOffHoursTimezone(cfg.off_hours_timezone ?? 'America/Sao_Paulo');
        setMedia(med);
      })
      .catch(() => setError('Não foi possível carregar as configurações.'))
      .finally(() => setLoading(false));
  }, []);

  async function handleToggleBot(val: boolean) {
    setSavingBot(true);
    setSavedBot(false);
    try {
      const updated = await settingsService.updateSettings({ bot_enabled: val });
      setSettings(updated);
      setBotEnabled(updated.bot_enabled);
      setSavedBot(true);
      setTimeout(() => setSavedBot(false), 2500);
    } finally {
      setSavingBot(false);
    }
  }

  async function handleSaveMessage() {
    setSavingMsg(true);
    setSavedMsg(false);
    try {
      const updated = await settingsService.updateSettings({ initial_message: initialMessage.trim() });
      setSettings(updated);
      setInitialMessage(updated.initial_message ?? '');
      setSavedMsg(true);
      setTimeout(() => setSavedMsg(false), 2500);
    } finally {
      setSavingMsg(false);
    }
  }

  async function handleSaveSequence() {
    setSavingSeq(true);
    setSavedSeq(false);
    try {
      const updated = await settingsService.updateSettings({ sequence_message: sequenceMessage.trim() });
      setSettings(updated);
      setSequenceMessage(updated.sequence_message ?? '');
      setSavedSeq(true);
      setTimeout(() => setSavedSeq(false), 2500);
    } finally {
      setSavingSeq(false);
    }
  }

  async function handleSaveLink() {
    setSavingLink(true);
    setSavedLink(false);
    try {
      const updated = await settingsService.updateSettings({ link_message: linkMessage.trim() });
      setSettings(updated);
      setLinkMessage(updated.link_message ?? '');
      setSavedLink(true);
      setTimeout(() => setSavedLink(false), 2500);
    } finally {
      setSavingLink(false);
    }
  }

  async function handleSaveAI() {
    setSavingAI(true);
    setSavedAI(false);
    try {
      const updated = await settingsService.updateSettings({
        use_conversation_template: useConversationTemplate,
        conversation_template: conversationTemplate,
      });
      setSettings(updated);
      setUseConversationTemplate(updated.use_conversation_template ?? true);
      setConversationTemplate(updated.conversation_template ?? '');
      setSavedAI(true);
      setTimeout(() => setSavedAI(false), 2500);
    } finally {
      setSavingAI(false);
    }
  }

  async function handleToggleOffHours(val: boolean) {
    setSavingOffHours(true);
    setSavedOffHours(false);
    try {
      const updated = await settingsService.updateSettings({ off_hours_enabled: val });
      setSettings(updated);
      setOffHoursEnabled(updated.off_hours_enabled ?? val);
      setSavedOffHours(true);
      setTimeout(() => setSavedOffHours(false), 2500);
    } finally {
      setSavingOffHours(false);
    }
  }

  async function handleSaveOffHours() {
    setSavingOffHours(true);
    setSavedOffHours(false);
    try {
      const updated = await settingsService.updateSettings({
        off_hours_enabled: offHoursEnabled,
        off_hours_start: offHoursStart || null,
        off_hours_end: offHoursEnd || null,
        off_hours_message: offHoursMessage.trim(),
        off_hours_timezone: offHoursTimezone || 'America/Sao_Paulo',
      });
      setSettings(updated);
      setOffHoursEnabled(updated.off_hours_enabled ?? false);
      setOffHoursStart(updated.off_hours_start ?? '21:00');
      setOffHoursEnd(updated.off_hours_end ?? '06:00');
      setOffHoursMessage(updated.off_hours_message ?? '');
      setOffHoursTimezone(updated.off_hours_timezone ?? 'America/Sao_Paulo');
      setSavedOffHours(true);
      setTimeout(() => setSavedOffHours(false), 2500);
    } finally {
      setSavingOffHours(false);
    }
  }

  async function handleMediaUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingMedia(true);
    try {
      const uploaded = await settingsService.uploadMedia(file);
      setMedia(prev => [...prev, uploaded]);
    } finally {
      setUploadingMedia(false);
      if (mediaInputRef.current) mediaInputRef.current.value = '';
    }
  }

  async function handleDeleteMedia(id: number) {
    setDeletingMediaId(id);
    try {
      await settingsService.deleteMedia(id);
      setMedia(prev => prev.filter(m => m.id !== id));
    } finally {
      setDeletingMediaId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="loading loading-spinner loading-md text-blue-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <p className="text-sm text-red-500">{error}</p>
        <button onClick={() => window.location.reload()} className="btn btn-ghost btn-sm">
          Tentar novamente
        </button>
      </div>
    );
  }

  const msgChanged = initialMessage !== (settings?.initial_message ?? '');
  const seqChanged = sequenceMessage !== (settings?.sequence_message ?? '');
  const linkChanged = linkMessage !== (settings?.link_message ?? '');
  const aiChanged =
    useConversationTemplate !== (settings?.use_conversation_template ?? true) ||
    conversationTemplate !== (settings?.conversation_template ?? '');

  const offHoursChanged =
    offHoursEnabled !== (settings?.off_hours_enabled ?? false) ||
    offHoursStart !== (settings?.off_hours_start ?? '21:00') ||
    offHoursEnd !== (settings?.off_hours_end ?? '06:00') ||
    offHoursMessage !== (settings?.off_hours_message ?? '') ||
    offHoursTimezone !== (settings?.off_hours_timezone ?? 'America/Sao_Paulo');

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Configurações</h1>
        <p className="text-base text-gray-400 mt-0.5">Gerencie as preferências globais da sua organização.</p>
      </div>

      {/* ── Bot automático ── */}
      <section className="rounded-2xl border border-gray-200 bg-white overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-blue-50 flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
          </div>
          <div>
            <p className="text-base font-semibold text-gray-800">Bot automático</p>
            <p className="text-sm text-gray-400">Controle global do bot de IA para novos leads.</p>
          </div>
        </div>

        <div className="px-5 py-5 flex items-center justify-between gap-6">
          <div className="flex-1">
            <p className="text-base font-medium text-gray-800">Ativar bot automático</p>
            <p className="text-sm text-gray-400 mt-1 leading-relaxed">
              Quando ativado, o bot de IA responde automaticamente a todos os novos leads assim que entram em contato.
              Você ainda pode assumir conversas individualmente a qualquer momento.
            </p>
          </div>
          <div className="flex flex-col items-center gap-1.5 flex-shrink-0">
            <ToggleSwitch checked={botEnabled} onChange={handleToggleBot} disabled={savingBot} />
            {savingBot && <span className="loading loading-spinner loading-xs text-blue-500" />}
            {savedBot && !savingBot && <span className="text-xs font-medium text-green-600">Salvo ✓</span>}
          </div>
        </div>

        <div className={`px-5 py-2.5 border-t border-gray-100 flex items-center gap-2 ${botEnabled ? 'bg-blue-50' : 'bg-amber-50'}`}>
          <span className="text-base">{botEnabled ? '🤖' : '👤'}</span>
          <p className={`text-sm font-medium ${botEnabled ? 'text-blue-700' : 'text-amber-700'}`}>
            {botEnabled
              ? 'Bot ativo — IA responde automaticamente aos novos leads'
              : 'Bot desativado — atendimento manual para novos leads'}
          </p>
        </div>
      </section>

      {/* ── Horário de atendimento ── */}
      <section className="rounded-2xl border border-gray-200 bg-white overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-orange-50 flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4 text-orange-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
          </div>
          <div>
            <p className="text-base font-semibold text-gray-800">Horário de atendimento</p>
            <p className="text-sm text-gray-400">Defina o período sem atendimento e a mensagem automática.</p>
          </div>
        </div>

        <div className="px-5 py-5 space-y-5">

          {/* Toggle: habilitar fora de horário */}
          <div className="flex items-start justify-between gap-6">
            <div className="flex-1">
              <p className="text-base font-medium text-gray-800">Ativar mensagem fora do horário</p>
              <p className="text-sm text-gray-400 mt-1 leading-relaxed">
                Quando ativado, o bot responde automaticamente com a mensagem abaixo em vez de acionar a IA
                durante o período configurado.
              </p>
            </div>
            <div className="flex flex-col items-center gap-1.5 flex-shrink-0">
              <ToggleSwitch checked={offHoursEnabled} onChange={handleToggleOffHours} disabled={savingOffHours} />
              {savingOffHours && <span className="loading loading-spinner loading-xs text-orange-500" />}
            </div>
          </div>

          {/* Período */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-gray-700">Início do período sem atendimento</label>
              <input
                type="time"
                value={offHoursStart}
                onChange={e => setOffHoursStart(e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-base outline-none focus:border-orange-400 transition-colors bg-white"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-gray-700">Fim do período sem atendimento</label>
              <input
                type="time"
                value={offHoursEnd}
                onChange={e => setOffHoursEnd(e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-base outline-none focus:border-orange-400 transition-colors bg-white"
              />
            </div>
          </div>

          {offHoursStart > offHoursEnd && offHoursStart && offHoursEnd && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-orange-50 text-orange-700 text-sm">
              <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              Período cruza a meia-noite — ex: das {offHoursStart} até as {offHoursEnd} do dia seguinte.
            </div>
          )}

          {/* Fuso horário */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700">Fuso horário</label>
            <select
              value={offHoursTimezone}
              onChange={e => setOffHoursTimezone(e.target.value)}
              className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-base outline-none focus:border-orange-400 transition-colors bg-white"
            >
              <option value="America/Sao_Paulo">America/Sao_Paulo (GMT-3)</option>
              <option value="America/Manaus">America/Manaus (GMT-4)</option>
              <option value="America/Belem">America/Belem (GMT-3)</option>
              <option value="America/Fortaleza">America/Fortaleza (GMT-3)</option>
              <option value="America/Recife">America/Recife (GMT-3)</option>
              <option value="America/Noronha">America/Noronha (GMT-2)</option>
              <option value="America/Porto_Velho">America/Porto_Velho (GMT-4)</option>
              <option value="America/Boa_Vista">America/Boa_Vista (GMT-4)</option>
              <option value="America/Cuiaba">America/Cuiaba (GMT-4)</option>
              <option value="America/Rio_Branco">America/Rio_Branco (GMT-5)</option>
              <option value="UTC">UTC</option>
            </select>
          </div>

          {/* Mensagem fora do horário */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700">Mensagem fora do horário</label>
            <textarea
              rows={4}
              placeholder={"Ex: Olá! No momento estamos fora do horário de atendimento.\nRetornaremos a partir das 9h. Deixe sua mensagem que entraremos em contato!"}
              className="w-full text-base border border-gray-200 rounded-xl px-4 py-3 outline-none focus:border-orange-400 transition-colors resize-none bg-white leading-relaxed"
              value={offHoursMessage}
              onChange={e => setOffHoursMessage(e.target.value)}
            />
            <p className="text-xs text-gray-400">
              Essa mensagem é enviada automaticamente quando o contato envia uma mensagem fora do horário configurado.
            </p>
          </div>

          {/* Status visual */}
          <div className={`flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium ${
            offHoursEnabled ? 'bg-orange-50 text-orange-700' : 'bg-gray-50 text-gray-500'
          }`}>
            <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
            {offHoursEnabled
              ? `Ativo — fora do horário (${offHoursStart || '--:--'} às ${offHoursEnd || '--:--'}) o bot responde com mensagem personalizada`
              : 'Desativado — o bot responde normalmente em qualquer horário'}
          </div>

          <div className="flex items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-1.5">
              {savedOffHours && !savingOffHours && (
                <span className="flex items-center gap-1 text-xs font-medium text-green-600">
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  Salvo com sucesso
                </span>
              )}
            </div>
            <button
              onClick={handleSaveOffHours}
              disabled={savingOffHours || !offHoursChanged}
              className="btn btn-sm min-w-[80px] bg-orange-500 hover:bg-orange-600 text-white border-0 disabled:opacity-40"
            >
              {savingOffHours ? <span className="loading loading-spinner loading-xs" /> : 'Salvar'}
            </button>
          </div>
        </div>
      </section>

      {/* ── Mensagem inicial ── */}
      <section className="rounded-2xl border border-gray-200 bg-white overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-green-50 flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4 text-green-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <div>
            <p className="text-base font-semibold text-gray-800">Mensagem inicial</p>
            <p className="text-sm text-gray-400">Texto enviado automaticamente no primeiro contato do lead.</p>
          </div>
        </div>

        <div className="px-5 py-5 space-y-4">
          <p className="text-sm text-gray-400 leading-relaxed">
            Esta mensagem é enviada automaticamente quando um lead entra em contato pela primeira vez.
            Deixe em branco para usar o comportamento padrão do sistema.
          </p>

          <textarea
            rows={4}
            placeholder={"Ex: Opa! Tudo bem? Aqui é o Marcelo 🐾\nPosso te ajudar? Você tem interesse em filhote macho ou fêmea?\n— Temos uma ninhada disponível!"}
            className="w-full text-base border border-gray-200 rounded-xl px-4 py-3 outline-none focus:border-green-400 transition-colors resize-none bg-white leading-relaxed"
            value={initialMessage}
            onChange={e => setInitialMessage(e.target.value)}
          />

          {/* ── Galeria de mídia ── */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-gray-500">Fotos / vídeos anexados</p>

            {media.length > 0 && (
              <div className="grid grid-cols-3 gap-2">
                {media.map(item => (
                  <div key={item.id} className="relative group rounded-xl overflow-hidden border border-gray-100 bg-gray-50 aspect-square">
                    {item.media_type === 'image' ? (
                      <img
                        src={item.url}
                        alt={item.original_name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex flex-col items-center justify-center gap-1">
                        <svg className="w-6 h-6 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                          <polygon points="23 7 16 12 23 17 23 7"/>
                          <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
                        </svg>
                        <p className="text-xs text-gray-400 truncate px-1 w-full text-center">{item.original_name}</p>
                      </div>
                    )}

                    {/* overlay de delete */}
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <button
                        onClick={() => handleDeleteMedia(item.id)}
                        disabled={deletingMediaId === item.id}
                        className="w-8 h-8 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center transition-colors"
                        title="Remover"
                      >
                        {deletingMediaId === item.id
                          ? <span className="loading loading-spinner loading-xs" />
                          : (
                            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                              <polyline points="3 6 5 6 21 6"/>
                              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                              <path d="M10 11v6M14 11v6"/>
                              <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                            </svg>
                          )
                        }
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Botão de upload */}
            <button
              onClick={() => mediaInputRef.current?.click()}
              disabled={uploadingMedia}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl border-2 border-dashed border-gray-200 hover:border-green-400 hover:bg-green-50 text-gray-400 hover:text-green-600 transition-colors text-sm font-medium"
            >
              {uploadingMedia ? (
                <>
                  <span className="loading loading-spinner loading-xs" />
                  Enviando...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                  Adicionar foto ou vídeo
                </>
              )}
            </button>
            <input
              ref={mediaInputRef}
              type="file"
              accept="image/*,video/*"
              className="hidden"
              onChange={handleMediaUpload}
            />
            {media.length > 0 && (
              <p className="text-xs text-gray-400 text-center">
                {media.length} arquivo{media.length !== 1 ? 's' : ''} anexado{media.length !== 1 ? 's' : ''} · passe o mouse para remover
              </p>
            )}
          </div>

          <div className="flex items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-1.5">
              {savedMsg && !savingMsg && (
                <span className="flex items-center gap-1 text-xs font-medium text-green-600">
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  Salvo com sucesso
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {initialMessage && (
                <button
                  onClick={() => setInitialMessage('')}
                  className="text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1"
                >
                  Limpar
                </button>
              )}
              <button
                onClick={handleSaveMessage}
                disabled={savingMsg || !msgChanged}
                className="btn btn-primary btn-sm min-w-[80px]"
              >
                {savingMsg ? <span className="loading loading-spinner loading-xs" /> : 'Salvar'}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── Mensagem de sequência ── */}
      <section className="rounded-2xl border border-gray-200 bg-white overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-purple-50 flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4 text-purple-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              <path d="M8 10h8M8 14h5"/>
            </svg>
          </div>
          <div>
            <p className="text-base font-semibold text-gray-800">Mensagem de sequência</p>
            <p className="text-sm text-gray-400">Segunda mensagem enviada logo após a inicial.</p>
          </div>
        </div>

        <div className="px-5 py-5 space-y-4">
          <p className="text-sm text-gray-400 leading-relaxed">
            Enviada automaticamente em seguida à mensagem inicial, para complementar ou aprofundar
            o contato com o lead. Deixe em branco para não enviar uma segunda mensagem.
          </p>

          <textarea
            rows={5}
            placeholder={"Ex: Aqui estão algumas fotos da ninhada 🐶\nSão filhotes de alto padrão, vacinados e com pedigree.\nQuer saber mais detalhes?"}
            className="w-full text-base border border-gray-200 rounded-xl px-4 py-3 outline-none focus:border-purple-400 transition-colors resize-none bg-white leading-relaxed"
            value={sequenceMessage}
            onChange={e => setSequenceMessage(e.target.value)}
          />

          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-1.5">
              {savedSeq && !savingSeq && (
                <span className="flex items-center gap-1 text-xs font-medium text-green-600">
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  Salvo com sucesso
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {sequenceMessage && (
                <button
                  onClick={() => setSequenceMessage('')}
                  className="text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1"
                >
                  Limpar
                </button>
              )}
              <button
                onClick={handleSaveSequence}
                disabled={savingSeq || !seqChanged}
                className="btn btn-sm min-w-[80px] bg-purple-600 hover:bg-purple-700 text-white border-0 disabled:opacity-40"
              >
                {savingSeq ? <span className="loading loading-spinner loading-xs" /> : 'Salvar'}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── Terceira mensagem — link ── */}
      <section className="rounded-2xl border border-gray-200 bg-white overflow-hidden shadow-sm">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100">
          <div className="w-9 h-9 rounded-xl bg-sky-50 flex items-center justify-center flex-shrink-0">
            <svg className="w-5 h-5 text-sky-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
            </svg>
          </div>
          <div>
            <p className="text-base font-semibold text-gray-800">Mensagem de link</p>
            <p className="text-sm text-gray-400">Terceira mensagem — enviada após a de sequência.</p>
          </div>
        </div>

        <div className="px-5 py-5 space-y-4">
          <p className="text-sm text-gray-400 leading-relaxed">
            Use para enviar o link do site ou qualquer mensagem final. Deixe em branco para não enviar.
          </p>

          <textarea
            rows={3}
            placeholder={"Ex: Veja todos os filhotes disponíveis agora:\n\nhttps://bordercolliesul.com.br"}
            className="w-full text-base border border-gray-200 rounded-xl px-4 py-3 outline-none focus:border-sky-400 transition-colors resize-none bg-white leading-relaxed"
            value={linkMessage}
            onChange={e => setLinkMessage(e.target.value)}
          />

          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-1.5">
              {savedLink && !savingLink && (
                <span className="flex items-center gap-1 text-xs font-medium text-green-600">
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  Salvo com sucesso
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {linkMessage && (
                <button
                  onClick={() => setLinkMessage('')}
                  className="text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1"
                >
                  Limpar
                </button>
              )}
              <button
                onClick={handleSaveLink}
                disabled={savingLink || !linkChanged}
                className="btn btn-sm min-w-[80px] bg-sky-500 hover:bg-sky-600 text-white border-0 disabled:opacity-40"
              >
                {savingLink ? <span className="loading loading-spinner loading-xs" /> : 'Salvar'}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── Comportamento das sugestões de IA ── */}
      <section className="rounded-2xl border border-gray-200 bg-white overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-violet-50 flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4 text-violet-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          </div>
          <div>
            <p className="text-base font-semibold text-gray-800">Sugestões de IA</p>
            <p className="text-sm text-gray-400">Controle como o modelo gera as 3 opções de resposta.</p>
          </div>
        </div>

        <div className="px-5 py-5 space-y-5">

          {/* Toggle: usar template de conversa */}
          <div className="flex items-start justify-between gap-6">
            <div className="flex-1">
              <p className="text-base font-medium text-gray-800">Usar template de conversa</p>
              <p className="text-sm text-gray-400 mt-1 leading-relaxed">
                Quando ativado, o template abaixo é usado para dar personalidade e contexto ao modelo.
                A base de conhecimento vetorial (Supabase) sempre tem prioridade, independente desta opção.
              </p>
              <p className="text-sm text-gray-400 mt-1 leading-relaxed">
                Quando desativado, o modelo responde exclusivamente com base nos registros vetoriais.
                Se não houver resultado na base, o template ainda entra como fallback.
              </p>
            </div>
            <div className="flex flex-col items-center gap-1.5 flex-shrink-0">
              <ToggleSwitch
                checked={useConversationTemplate}
                onChange={setUseConversationTemplate}
                disabled={savingAI}
              />
            </div>
          </div>

          {/* Status visual do modo */}
          <div className={`flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium ${
            useConversationTemplate
              ? 'bg-violet-50 text-violet-700'
              : 'bg-amber-50 text-amber-700'
          }`}>
            <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              {useConversationTemplate ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375" />
              )}
            </svg>
            {useConversationTemplate
              ? 'Modo padrão: base vetorial (prioridade) + template de conversa'
              : 'Modo RAG puro: sugestões baseadas exclusivamente na base vetorial'}
          </div>

          {/* Editor do template */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-gray-700">Template de conversa</p>
              <span className="text-xs text-gray-400">Variáveis disponíveis: {'{litters_context}'}, {'{greeting_instruction}'}, {'{profile_section}'}, {'{kb_section}'}</span>
            </div>
            <textarea
              rows={18}
              className="w-full text-xs font-mono border border-gray-200 rounded-xl px-4 py-3 outline-none focus:border-violet-400 transition-colors resize-y bg-gray-50 leading-relaxed"
              value={conversationTemplate}
              onChange={e => setConversationTemplate(e.target.value)}
              placeholder="Deixe em branco para usar o template padrão do sistema..."
              spellCheck={false}
            />
            <p className="text-xs text-gray-400">
              Deixe em branco para usar o template padrão do sistema (hard-coded). Edite aqui para personalizar por organização.
            </p>
          </div>

          <div className="flex items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-1.5">
              {savedAI && !savingAI && (
                <span className="flex items-center gap-1 text-xs font-medium text-green-600">
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  Salvo com sucesso
                </span>
              )}
            </div>
            <button
              onClick={handleSaveAI}
              disabled={savingAI || !aiChanged}
              className="btn btn-sm min-w-[80px] bg-violet-600 hover:bg-violet-700 text-white border-0 disabled:opacity-40"
            >
              {savingAI ? <span className="loading loading-spinner loading-xs" /> : 'Salvar'}
            </button>
          </div>
        </div>
      </section>

    </div>
  );
}
