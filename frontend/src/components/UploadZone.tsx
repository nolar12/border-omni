import React, { useRef, useState } from 'react';

interface UploadZoneProps {
  onFiles: (files: File[]) => void;
  className?: string;
  compact?: boolean;
}

const UploadZone: React.FC<UploadZoneProps> = ({ onFiles, className = '', compact = false }) => {
  const [dragOver, setDragOver] = useState(false);
  const galleryRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);

  const handleFiles = (raw: FileList | null) => {
    if (!raw) return;
    const images = Array.from(raw).filter(f => f.type.startsWith('image/'));
    if (images.length > 0) onFiles(images);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
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
          accept="image/*"
          className="hidden"
          onChange={e => { handleFiles(e.target.files); e.target.value = ''; }}
        />
        <svg
          className={`${compact ? 'w-7 h-7' : 'w-9 h-9'} ${dragOver ? 'text-blue-400' : 'text-slate-500'}`}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}
        >
          <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2"/>
          <polyline points="16 8 12 4 8 8"/>
          <line x1="12" y1="4" x2="12" y2="16"/>
        </svg>
        <span className={`font-medium ${compact ? 'text-xs' : 'text-sm'} ${dragOver ? 'text-blue-300' : 'text-slate-400'}`}>
          {dragOver ? 'Solte as fotos aqui' : 'Arraste ou clique para selecionar'}
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
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={e => { handleFiles(e.target.files); e.target.value = ''; }}
        />
        <svg className={compact ? 'w-4 h-4' : 'w-5 h-5'} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
          <circle cx="12" cy="13" r="4"/>
        </svg>
        Abrir câmera
      </button>
    </div>
  );
};

export default UploadZone;
