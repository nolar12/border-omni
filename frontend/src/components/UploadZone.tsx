import React, { useRef, useState } from 'react';
import ImageCropEditor from './ImageCropEditor';
import { isHevcVideo, transcodeToH264 } from '../utils/videoTranscode';

interface UploadZoneProps {
  onFiles: (files: File[]) => void;
  className?: string;
  compact?: boolean;
  allowVideo?: boolean;
}

const UploadZone: React.FC<UploadZoneProps> = ({ onFiles, className = '', compact = false, allowVideo = false }) => {
  const [dragOver, setDragOver] = useState(false);
  const galleryRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);

  // Conversão de vídeo HEVC → H.264 em andamento
  const [converting, setConverting] = useState<{ name: string; index: number; total: number; pct: number } | null>(null);

  // Crop-editor queue
  const [queue, setQueue] = useState<File[]>([]);
  const [accumulated, setAccumulated] = useState<File[]>([]);
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [currentSrc, setCurrentSrc] = useState<string | null>(null);

  const openEditor = (file: File, rest: File[], done: File[]) => {
    setCurrentFile(file);
    setCurrentSrc(URL.createObjectURL(file));
    setQueue(rest);
    setAccumulated(done);
  };

  const advance = (done: File[]) => {
    if (queue.length === 0) {
      onFiles(done);
      setCurrentFile(null);
      setCurrentSrc(null);
      setAccumulated([]);
      setQueue([]);
    } else {
      const [next, ...rest] = queue;
      openEditor(next, rest, done);
    }
  };

  const handleCropComplete = (file: File) => {
    advance([...accumulated, file]);
  };

  // "Pular" = use original file as-is
  const handleSkip = () => {
    advance(currentFile ? [...accumulated, currentFile] : accumulated);
  };

  // Converte vídeos HEVC para H.264 (desktop não toca HEVC); se falhar, envia o original.
  const prepareVideos = async (videos: File[]): Promise<File[]> => {
    const out: File[] = [];
    for (let i = 0; i < videos.length; i++) {
      const v = videos[i];
      let result = v;
      try {
        if (await isHevcVideo(v)) {
          setConverting({ name: v.name, index: i + 1, total: videos.length, pct: 0 });
          result = await transcodeToH264(v, pct => setConverting(c => (c ? { ...c, pct } : c)));
        }
      } catch (err) {
        console.error('Falha ao converter vídeo', err);
        window.alert(`Não foi possível converter "${v.name}" para H.264. Ele será enviado como está e pode não tocar em alguns computadores.`);
      }
      out.push(result);
    }
    setConverting(null);
    return out;
  };

  const handleIncomingFiles = (raw: FileList | null) => {
    if (!raw) return;
    const all = Array.from(raw);
    const images = all.filter(f => f.type.startsWith('image/'));
    // Vídeos não passam pelo editor de recorte: vão direto para o consumidor.
    const videos = allowVideo ? all.filter(f => f.type.startsWith('video/')) : [];
    const MAX_VIDEO = 200 * 1024 * 1024;
    const tooBig = videos.filter(v => v.size > MAX_VIDEO);
    if (tooBig.length > 0) window.alert(`Vídeo grande demais (máx. 200 MB): ${tooBig.map(v => v.name).join(', ')}`);
    const okVideos = videos.filter(v => v.size <= MAX_VIDEO);
    if (okVideos.length > 0) void prepareVideos(okVideos).then(onFiles);
    if (images.length === 0) return;
    const [first, ...rest] = images;
    openEditor(first, rest, []);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleIncomingFiles(e.dataTransfer.files);
  };

  const totalInBatch = accumulated.length + (currentSrc ? 1 : 0) + queue.length;
  const currentIndex = accumulated.length + 1;

  return (
    <>
      <div className={`space-y-2 ${className}`}>
        {/* Drop zone */}
        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragEnter={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => galleryRef.current?.click()}
          className={`flex flex-col items-center justify-center gap-2 w-full rounded-xl border-2 border-dashed cursor-pointer transition-colors select-none
            ${compact ? 'py-5' : 'py-8'}
            ${dragOver ? 'border-blue-400 bg-blue-500/10' : 'border-slate-600 hover:border-blue-500 bg-slate-700/40'}`}
        >
          <input
            ref={galleryRef}
            type="file"
            multiple
            accept={allowVideo ? 'image/*,video/*' : 'image/*'}
            className="hidden"
            onChange={e => { handleIncomingFiles(e.target.files); e.target.value = ''; }}
          />
          <svg
            className={`${compact ? 'w-7 h-7' : 'w-9 h-9'} ${dragOver ? 'text-blue-400' : 'text-slate-500'}`}
            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}
          >
            <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
            <polyline points="16 8 12 4 8 8" />
            <line x1="12" y1="4" x2="12" y2="16" />
          </svg>
          <span className={`font-medium ${compact ? 'text-xs' : 'text-sm'} ${dragOver ? 'text-blue-300' : 'text-slate-400'}`}>
            {dragOver ? (allowVideo ? 'Solte as fotos e vídeos aqui' : 'Solte as fotos aqui') : 'Arraste ou clique para selecionar'}
          </span>
          {!compact && <span className="text-xs text-slate-500">Múltiplos arquivos suportados</span>}
        </div>

        {/* Camera button */}
        <button
          type="button"
          onClick={() => cameraRef.current?.click()}
          className={`w-full flex items-center justify-center gap-2 rounded-xl border border-slate-600 hover:border-blue-500 bg-slate-700/40 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors
            ${compact ? 'py-2.5 text-xs' : 'py-3 text-sm'}`}
        >
          <input
            ref={cameraRef}
            type="file"
            multiple
            accept={allowVideo ? 'image/*,video/*' : 'image/*'}
            capture="environment"
            className="hidden"
            onChange={e => { handleIncomingFiles(e.target.files); e.target.value = ''; }}
          />
          <svg className={compact ? 'w-4 h-4' : 'w-5 h-5'} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
            <circle cx="12" cy="13" r="4" />
          </svg>
          Abrir câmera
        </button>
      </div>

      {converting && (
        <div className="fixed inset-0 z-[250] flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-sm rounded-xl bg-slate-800 border border-slate-600 p-5 text-center space-y-3">
            <p className="text-white text-sm font-semibold">
              Convertendo vídeo{converting.total > 1 ? ` (${converting.index}/${converting.total})` : ''}…
            </p>
            <p className="text-slate-400 text-xs truncate">{converting.name}</p>
            <div className="h-2 rounded-full bg-slate-700 overflow-hidden">
              <div className="h-full bg-blue-500 transition-all" style={{ width: `${converting.pct}%` }} />
            </div>
            <p className="text-slate-400 text-xs">
              {converting.pct}% — pode levar alguns minutos. Não feche esta tela: o vídeo está em HEVC e precisa virar H.264 para tocar em qualquer computador.
            </p>
          </div>
        </div>
      )}

      {/* Crop editor — renders above all other modals */}
      {currentSrc && (
        <>
          {totalInBatch > 1 && (
            <div className="fixed top-[60px] right-5 z-[201] bg-black/60 text-white text-xs px-2.5 py-1 rounded-full pointer-events-none">
              {currentIndex} / {totalInBatch}
            </div>
          )}
          <ImageCropEditor
            src={currentSrc}
            fileName={currentFile?.name}
            onComplete={handleCropComplete}
            onCancel={handleSkip}
            cancelLabel="Pular"
            zClass="z-[200]"
          />
        </>
      )}
    </>
  );
};

export default UploadZone;
