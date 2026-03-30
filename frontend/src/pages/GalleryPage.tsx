import { useEffect, useRef, useState, useCallback } from 'react';
import { galleryService, type GalleryMedia } from '../services/gallery';
import VideoThumbnail from '../components/VideoThumbnail';

type Filter = 'ALL' | 'IMAGE' | 'VIDEO' | 'DOCUMENT';

interface PendingUpload {
  file: File;
  previewUrl: string;
  name: string;
  description: string;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' });
}

export default function GalleryPage() {
  const [items, setItems] = useState<GalleryMedia[]>([]);
  const [filter, setFilter] = useState<Filter>('ALL');
  const [loading, setLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [preview, setPreview] = useState<GalleryMedia | null>(null);
  const [toast, setToast] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounter = useRef(0);

  // Upload modal state
  const [uploadQueue, setUploadQueue] = useState<PendingUpload[]>([]);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  // Edit description state (in preview modal)
  const [editingDesc, setEditingDesc] = useState(false);
  const [descDraft, setDescDraft] = useState('');
  const [savingDesc, setSavingDesc] = useState(false);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(''), 3000);
  }

  async function loadItems() {
    setLoading(true);
    try {
      const data = await galleryService.list();
      setItems(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadItems(); }, []);

  // ─── Drag & Drop ──────────────────────────────────────────────────────────

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    dragCounter.current += 1;
    if (dragCounter.current === 1) setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    dragCounter.current -= 1;
    if (dragCounter.current === 0) setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    dragCounter.current = 0;
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files).filter(f =>
      f.type.startsWith('image/') || f.type.startsWith('video/') || f.type === 'application/pdf'
    );
    if (files.length) openUploadModal(files);
  }, []);

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length) openUploadModal(files);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function openUploadModal(files: File[]) {
    const queue: PendingUpload[] = files.map(f => ({
      file: f,
      // Create object URL for both images and videos (revoked on modal close)
      previewUrl: URL.createObjectURL(f),
      name: f.name.replace(/\.[^.]+$/, ''),
      description: '',
    }));
    setUploadQueue(queue);
    setUploadError('');
    setShowUploadModal(true);
  }

  function closeUploadModal() {
    uploadQueue.forEach(p => { if (p.previewUrl) URL.revokeObjectURL(p.previewUrl); });
    setUploadQueue([]);
    setShowUploadModal(false);
    setUploadError('');
  }

  async function handleConfirmUpload() {
    setUploading(true);
    setUploadError('');
    let uploaded = 0;
    for (const pending of uploadQueue) {
      try {
        const item = await galleryService.upload(pending.file, pending.name || pending.file.name, pending.description);
        setItems(prev => [item, ...prev]);
        uploaded++;
      } catch (err: unknown) {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setUploadError(detail ?? `Erro ao enviar ${pending.file.name}.`);
        setUploading(false);
        return;
      }
    }
    setUploading(false);
    closeUploadModal();
    showToast(`${uploaded} arquivo(s) adicionado(s) à galeria.`);
  }

  // ─── Delete ───────────────────────────────────────────────────────────────

  async function handleDelete(id: number) {
    try {
      await galleryService.remove(id);
      setItems(prev => prev.filter(i => i.id !== id));
      setDeleteConfirm(null);
      if (preview?.id === id) setPreview(null);
      showToast('Item removido da galeria.');
    } catch {
      showToast('Erro ao remover item.');
    }
  }

  // ─── Edit description ─────────────────────────────────────────────────────

  function startEditDesc() {
    if (!preview) return;
    setDescDraft(preview.description ?? '');
    setEditingDesc(true);
  }

  async function saveDesc() {
    if (!preview) return;
    setSavingDesc(true);
    try {
      const updated = await galleryService.update(preview.id, { description: descDraft });
      setItems(prev => prev.map(i => i.id === updated.id ? updated : i));
      setPreview(updated);
      setEditingDesc(false);
      showToast('Descrição salva.');
    } catch {
      showToast('Erro ao salvar descrição.');
    } finally {
      setSavingDesc(false);
    }
  }

  const displayed = filter === 'ALL' ? items : items.filter(i => i.media_type === filter);
  const imageCount = items.filter(i => i.media_type === 'IMAGE').length;
  const videoCount = items.filter(i => i.media_type === 'VIDEO').length;
  const docCount = items.filter(i => i.media_type === 'DOCUMENT').length;

  return (
    <div
      className="flex flex-col h-full bg-gray-50 relative"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Drag overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-40 flex flex-col items-center justify-center bg-blue-600/10 border-4 border-dashed border-blue-500 rounded-xl pointer-events-none">
          <svg className="w-16 h-16 text-blue-500 mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          <p className="text-blue-600 font-bold text-xl">Solte para adicionar à galeria</p>
          <p className="text-blue-500 text-sm mt-1">Imagens e vídeos aceitos</p>
        </div>
      )}

      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Galeria de Mídia</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {items.length} arquivo(s) — {imageCount} imagem(ns) · {videoCount} vídeo(s) · {docCount} PDF(s)
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Filter tabs */}
            <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              {(['ALL', 'IMAGE', 'VIDEO', 'DOCUMENT'] as Filter[]).map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    filter === f
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {f === 'ALL' ? 'Todos' : f === 'IMAGE' ? 'Imagens' : f === 'VIDEO' ? 'Vídeos' : 'PDFs'}
                </button>
              ))}
            </div>

            {/* Upload button */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              accept="image/jpeg,image/png,image/gif,image/webp,video/mp4,video/quicktime,video/webm,application/pdf"
              onChange={handleFileSelect}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold transition-colors shadow-sm"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
              Adicionar mídia
            </button>
          </div>
        </div>

        {/* Drag hint */}
        <p className="text-xs text-gray-400 mt-2 flex items-center gap-1">
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          Você também pode arrastar arquivos diretamente para esta página
        </p>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <svg className="w-8 h-8 text-gray-400 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
            </svg>
          </div>
        ) : displayed.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <div className="w-20 h-20 rounded-2xl bg-gray-100 flex items-center justify-center mb-4 border-2 border-dashed border-gray-300">
              <svg className="w-9 h-9 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <circle cx="8.5" cy="8.5" r="1.5"/>
                <polyline points="21 15 16 10 5 21"/>
              </svg>
            </div>
            <p className="text-gray-600 font-medium">Nenhuma mídia encontrada</p>
            <p className="text-gray-400 text-sm mt-1">
              Arraste arquivos aqui ou clique em "Adicionar mídia".
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {displayed.map(item => (
              <div
                key={item.id}
                className="group relative bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => { setPreview(item); setEditingDesc(false); }}
              >
                {/* Thumbnail */}
                <div className="aspect-square bg-gray-100 overflow-hidden">
                  {item.media_type === 'IMAGE' ? (
                    <img src={item.file_url} alt={item.name} className="w-full h-full object-cover" />
                  ) : item.media_type === 'VIDEO' ? (
                    <VideoThumbnail src={item.file_url} />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-gradient-to-br from-red-50 to-red-100">
                      <svg className="w-10 h-10 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="9" y1="13" x2="15" y2="13"/>
                        <line x1="9" y1="17" x2="15" y2="17"/>
                        <line x1="9" y1="9" x2="11" y2="9"/>
                      </svg>
                      <span className="text-red-600 text-xs font-bold uppercase tracking-wider">PDF</span>
                    </div>
                  )}
                </div>

                {/* Info */}
                <div className="p-2 pb-2.5">
                  <p className="text-xs font-medium text-gray-800 truncate leading-tight" title={item.name}>{item.name}</p>
                  {item.description && (
                    <p
                      className="text-xs text-gray-500 mt-1 leading-snug"
                      style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
                      title={item.description}
                    >
                      {item.description}
                    </p>
                  )}
                  <p className="text-[10px] text-gray-400 mt-1">{formatBytes(item.size_bytes)}</p>
                </div>

                {/* Delete button */}
                <button
                  onClick={e => { e.stopPropagation(); setDeleteConfirm(item.id); }}
                  className="absolute top-2 right-2 w-7 h-7 rounded-full bg-red-500 text-white opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center shadow-md hover:bg-red-600"
                  title="Remover"
                >
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>

                {/* Type badge */}
                <div className={`absolute top-2 left-2 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide ${
                  item.media_type === 'IMAGE' ? 'bg-blue-500/80 text-white'
                  : item.media_type === 'VIDEO' ? 'bg-purple-600/80 text-white'
                  : 'bg-red-500/80 text-white'
                }`}>
                  {item.media_type === 'IMAGE' ? 'IMG' : item.media_type === 'VIDEO' ? 'VID' : 'PDF'}
                </div>

                {/* Description indicator */}
                {item.description && (
                  <div className="absolute bottom-10 right-2 w-5 h-5 rounded-full bg-green-500/80 flex items-center justify-center" title="Tem descrição">
                    <svg className="w-3 h-3 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                      <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="16" y2="18"/>
                      <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ─── Upload Modal ────────────────────────────────────────────────────── */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <div>
                <p className="font-semibold text-gray-900">Adicionar mídia</p>
                <p className="text-xs text-gray-500 mt-0.5">{uploadQueue.length} arquivo(s) selecionado(s)</p>
              </div>
              <button onClick={closeUploadModal} className="text-gray-400 hover:text-gray-600 p-1">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>

            {/* Files list */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
              {uploadQueue.map((pending, idx) => (
                <div key={idx} className="flex gap-3">
                  {/* Preview thumbnail */}
                  <div className="w-16 h-16 rounded-xl bg-gray-100 overflow-hidden flex-shrink-0 border border-gray-200">
                    {pending.file.type.startsWith('image/') ? (
                      <img src={pending.previewUrl} alt="" className="w-full h-full object-cover" />
                    ) : pending.file.type === 'application/pdf' ? (
                      <div className="w-full h-full flex flex-col items-center justify-center gap-1 bg-red-50">
                        <svg className="w-7 h-7 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                          <polyline points="14 2 14 8 20 8"/>
                        </svg>
                        <span className="text-red-500 text-[9px] font-bold">PDF</span>
                      </div>
                    ) : (
                      <VideoThumbnail src={pending.previewUrl} />
                    )}
                  </div>

                  {/* Fields */}
                  <div className="flex-1 space-y-2">
                    <input
                      type="text"
                      placeholder="Nome do arquivo"
                      value={pending.name}
                      onChange={e => setUploadQueue(q => q.map((p, i) => i === idx ? { ...p, name: e.target.value } : p))}
                      className="w-full text-sm border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-blue-400 transition-colors"
                    />
                    <textarea
                      placeholder="Descrição / legenda para o chat (opcional)"
                      value={pending.description}
                      rows={2}
                      onChange={e => setUploadQueue(q => q.map((p, i) => i === idx ? { ...p, description: e.target.value } : p))}
                      className="w-full text-sm border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-blue-400 transition-colors resize-none"
                    />
                  </div>

                  {/* Remove from queue */}
                  <button
                    onClick={() => {
                      if (pending.previewUrl) URL.revokeObjectURL(pending.previewUrl);
                      const next = uploadQueue.filter((_, i) => i !== idx);
                      if (next.length === 0) { closeUploadModal(); return; }
                      setUploadQueue(next);
                    }}
                    className="text-gray-300 hover:text-red-500 transition-colors self-start pt-1"
                  >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                  </button>
                </div>
              ))}

              {uploadError && (
                <div className="px-4 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                  {uploadError}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex gap-3 px-6 py-4 border-t border-gray-100">
              <button
                onClick={closeUploadModal}
                className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleConfirmUpload}
                disabled={uploading}
                className="flex-1 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {uploading ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                    </svg>
                    Enviando…
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                      <polyline points="17 8 12 3 7 8"/>
                      <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                    Enviar {uploadQueue.length > 1 ? `${uploadQueue.length} arquivos` : 'arquivo'}
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Preview Modal ───────────────────────────────────────────────────── */}
      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={() => { setPreview(null); setEditingDesc(false); }}
        >
          <div
            className="relative max-w-3xl w-full bg-white rounded-2xl overflow-hidden shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
              <div>
                <p className="font-semibold text-gray-900 text-sm truncate max-w-xs">{preview.name}</p>
                <p className="text-xs text-gray-400">{formatBytes(preview.size_bytes)} · {formatDate(preview.created_at)}</p>
              </div>
              <button
                onClick={() => { setPreview(null); setEditingDesc(false); }}
                className="text-gray-400 hover:text-gray-600 p-1"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>

            {/* Media */}
            <div className={`flex items-center justify-center ${preview.media_type === 'DOCUMENT' ? 'bg-gray-50' : 'bg-black'}`}
              style={{ maxHeight: preview.media_type === 'DOCUMENT' ? '60vh' : '50vh' }}>
              {preview.media_type === 'IMAGE' ? (
                <img src={preview.file_url} alt={preview.name} className="max-h-[50vh] max-w-full object-contain" />
              ) : preview.media_type === 'VIDEO' ? (
                <video src={preview.file_url} controls autoPlay className="max-h-[50vh] max-w-full" />
              ) : (
                <iframe
                  src={preview.file_url}
                  title={preview.name}
                  className="w-full"
                  style={{ height: '60vh', border: 'none' }}
                />
              )}
            </div>

            {/* Description section */}
            <div className="px-5 py-3 border-t border-gray-100">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Descrição / Caption
                </span>
                {!editingDesc && (
                  <button
                    onClick={startEditDesc}
                    className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                    Editar
                  </button>
                )}
              </div>

              {editingDesc ? (
                <div className="space-y-2">
                  <textarea
                    rows={3}
                    value={descDraft}
                    autoFocus
                    onChange={e => setDescDraft(e.target.value)}
                    placeholder="Escreva uma legenda que será pré-preenchida no chat ao usar esta mídia..."
                    className="w-full text-sm border border-blue-300 rounded-lg px-3 py-2 outline-none focus:border-blue-500 transition-colors resize-none"
                  />
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => setEditingDesc(false)}
                      className="px-3 py-1.5 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
                    >
                      Cancelar
                    </button>
                    <button
                      onClick={saveDesc}
                      disabled={savingDesc}
                      className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium disabled:opacity-60"
                    >
                      {savingDesc ? 'Salvando…' : 'Salvar'}
                    </button>
                  </div>
                </div>
              ) : (
                <p className={`text-sm ${preview.description ? 'text-gray-700' : 'text-gray-400 italic'}`}>
                  {preview.description || 'Sem descrição. Clique em "Editar" para adicionar uma legenda.'}
                </p>
              )}
            </div>

            {/* Footer actions */}
            <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100">
              <a
                href={preview.file_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-blue-600 hover:underline flex items-center gap-1"
                onClick={e => e.stopPropagation()}
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                  <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
                Abrir URL
              </a>
              <button
                onClick={() => { setDeleteConfirm(preview.id); setPreview(null); setEditingDesc(false); }}
                className="text-sm text-red-500 hover:text-red-700 flex items-center gap-1"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                  <path d="M10 11v6M14 11v6"/>
                </svg>
                Remover
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Delete Confirmation Modal ───────────────────────────────────────── */}
      {deleteConfirm !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-full text-center">
            <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-red-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
              </svg>
            </div>
            <p className="font-semibold text-gray-900 mb-1">Remover da galeria?</p>
            <p className="text-sm text-gray-500 mb-6">O arquivo será excluído permanentemente.</p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                className="flex-1 py-2.5 rounded-xl bg-red-500 hover:bg-red-600 text-white text-sm font-semibold"
              >
                Remover
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-5 py-3 bg-gray-900 text-white text-sm rounded-xl shadow-xl">
          {toast}
        </div>
      )}
    </div>
  );
}
