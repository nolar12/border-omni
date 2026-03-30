import React, { useState, useCallback } from 'react';
import Cropper from 'react-easy-crop';
import type { Area } from 'react-easy-crop';

// ─── Canvas utilities ─────────────────────────────────────────────────────────

function createImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => {
      // Retry without crossOrigin (same-origin fallback)
      const img2 = new Image();
      img2.onload = () => resolve(img2);
      img2.onerror = reject;
      img2.src = url;
    };
    img.src = url;
  });
}

async function getCroppedFile(
  imageSrc: string,
  pixelCrop: Area,
  rotation = 0,
  flipH = false,
  fileName = 'editada.jpg',
): Promise<File> {
  const image = await createImage(imageSrc);
  const safeArea = 2 * ((Math.max(image.width, image.height) / 2) * Math.sqrt(2));

  // Canvas 1: apply rotation to the full safe area
  const c1 = document.createElement('canvas');
  c1.width = safeArea;
  c1.height = safeArea;
  const ctx1 = c1.getContext('2d')!;
  ctx1.translate(safeArea / 2, safeArea / 2);
  ctx1.rotate((rotation * Math.PI) / 180);
  ctx1.translate(-image.width / 2, -image.height / 2);
  ctx1.drawImage(image, 0, 0);

  const offsetX = safeArea / 2 - image.width / 2;
  const offsetY = safeArea / 2 - image.height / 2;
  const cropData = ctx1.getImageData(
    Math.round(offsetX + pixelCrop.x),
    Math.round(offsetY + pixelCrop.y),
    Math.round(pixelCrop.width),
    Math.round(pixelCrop.height),
  );

  // Canvas 2: put the raw crop pixels
  const c2 = document.createElement('canvas');
  c2.width = Math.round(pixelCrop.width);
  c2.height = Math.round(pixelCrop.height);
  c2.getContext('2d')!.putImageData(cropData, 0, 0);

  // Canvas 3 (only when flipH): apply horizontal mirror via drawImage
  const finalCanvas = flipH ? (() => {
    const c3 = document.createElement('canvas');
    c3.width = c2.width;
    c3.height = c2.height;
    const ctx3 = c3.getContext('2d')!;
    ctx3.translate(c2.width, 0);
    ctx3.scale(-1, 1);
    ctx3.drawImage(c2, 0, 0);
    return c3;
  })() : c2;

  return new Promise((resolve, reject) => {
    finalCanvas.toBlob(
      blob => {
        if (!blob) return reject(new Error('Canvas is empty'));
        resolve(new File([blob], fileName.replace(/\.[^.]+$/, '.jpg'), { type: 'image/jpeg' }));
      },
      'image/jpeg',
      0.92,
    );
  });
}

// ─── Component ────────────────────────────────────────────────────────────────

export interface ImageCropEditorProps {
  src: string;
  fileName?: string;
  onComplete: (file: File) => void;
  onCancel: () => void;
  /** z-index class for the overlay, default "z-[200]" */
  zClass?: string;
  /** Label for the cancel/skip button, default "Cancelar" */
  cancelLabel?: string;
}

const ImageCropEditor: React.FC<ImageCropEditorProps> = ({
  src,
  fileName = 'editada.jpg',
  onComplete,
  onCancel,
  zClass = 'z-[200]',
  cancelLabel = 'Cancelar',
}) => {
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [flipH, setFlipH] = useState(false);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<Area | null>(null);
  const [processing, setProcessing] = useState(false);

  const onCropComplete = useCallback((_: Area, pixels: Area) => {
    setCroppedAreaPixels(pixels);
  }, []);

  const handleConfirm = async () => {
    if (!croppedAreaPixels) return;
    setProcessing(true);
    try {
      const file = await getCroppedFile(src, croppedAreaPixels, rotation, flipH, fileName);
      onComplete(file);
    } catch (err) {
      console.error('Erro ao processar imagem:', err);
    } finally {
      setProcessing(false);
    }
  };

  const rotate = (delta: number) => setRotation(r => (r + delta + 360) % 360);

  return (
    <div className={`fixed inset-0 ${zClass} flex flex-col bg-black`}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 bg-zinc-900 shrink-0">
        <span className="text-white font-semibold text-sm">Editar imagem</span>
        <button
          onClick={onCancel}
          className="text-white/60 hover:text-white transition-colors p-1"
          title="Cancelar"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {/* Crop area */}
      <div className="relative flex-1">
        <Cropper
          image={src}
          crop={crop}
          zoom={zoom}
          rotation={rotation}
          onCropChange={setCrop}
          onZoomChange={setZoom}
          onCropComplete={onCropComplete}
          style={{
            containerStyle: { background: '#0f0f0f' },
            mediaStyle: flipH ? { transform: `rotate(${rotation}deg) scaleX(-1)` } : undefined,
          }}
          showGrid
        />
      </div>

      {/* Controls */}
      <div className="shrink-0 bg-zinc-900 px-5 py-4 space-y-4">
        {/* Zoom slider */}
        <div className="flex items-center gap-3">
          <svg className="w-4 h-4 text-slate-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            <line x1="11" y1="8" x2="11" y2="14" /><line x1="8" y1="11" x2="14" y2="11" />
          </svg>
          <input
            type="range"
            min={1}
            max={3}
            step={0.05}
            value={zoom}
            onChange={e => setZoom(Number(e.target.value))}
            className="flex-1 h-1.5 rounded-full accent-blue-500 cursor-pointer"
          />
          <svg className="w-4 h-4 text-slate-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </div>

        {/* Transform buttons */}
        <div className="flex items-center justify-center gap-3">
          {/* Rotate -90 */}
          <button
            onClick={() => rotate(-90)}
            className="flex flex-col items-center gap-1 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors text-xs"
            title="Girar -90°"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38" />
            </svg>
            <span>-90°</span>
          </button>

          {/* Rotate +90 */}
          <button
            onClick={() => rotate(90)}
            className="flex flex-col items-center gap-1 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors text-xs"
            title="Girar +90°"
          >
            <svg className="w-5 h-5 scale-x-[-1]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38" />
            </svg>
            <span>+90°</span>
          </button>

          {/* Flip horizontal */}
          <button
            onClick={() => setFlipH(f => !f)}
            className={`flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-colors text-xs ${
              flipH
                ? 'bg-blue-600 hover:bg-blue-500 text-white'
                : 'bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white'
            }`}
            title="Espelhar horizontal"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3" />
              <path d="M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3" />
              <line x1="12" y1="3" x2="12" y2="21" strokeDasharray="3 2" />
            </svg>
            <span>Espelhar</span>
          </button>

          {/* Reset */}
          <button
            onClick={() => { setCrop({ x: 0, y: 0 }); setZoom(1); setRotation(0); setFlipH(false); }}
            className="flex flex-col items-center gap-1 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors text-xs"
            title="Resetar"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
              <path d="M3 3v5h5" />
            </svg>
            <span>Resetar</span>
          </button>
        </div>

        {/* Action buttons */}
        <div className="flex gap-3 pt-1">
          <button
            onClick={onCancel}
            className="flex-1 py-2.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={handleConfirm}
            disabled={processing}
            className="flex-1 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold transition-colors"
          >
            {processing ? 'Processando…' : 'Confirmar'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ImageCropEditor;
