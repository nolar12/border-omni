import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { dogsService } from '../services/dogs';
import type { Dog } from '../types';

const SHARE_CACHE = 'share-target-v1';

interface SharedFile {
  blob: Blob;
  name: string;
  preview: string;
}

async function readSharedFiles(): Promise<SharedFile[]> {
  if (!('caches' in window)) return [];
  try {
    const cache = await caches.open(SHARE_CACHE);
    const meta = await cache.match('/share-meta');
    if (!meta) return [];
    const { count } = await meta.json();
    const files: SharedFile[] = [];
    for (let i = 0; i < count; i++) {
      const resp = await cache.match(`/share-file-${i}`);
      if (!resp) continue;
      const blob = await resp.blob();
      const name = decodeURIComponent(resp.headers.get('X-File-Name') ?? `foto-${i + 1}.jpg`);
      files.push({ blob, name, preview: URL.createObjectURL(blob) });
    }
    // Clear cache after reading
    const keys = await cache.keys();
    await Promise.all(keys.map(k => cache.delete(k)));
    return files;
  } catch {
    return [];
  }
}

export default function ShareTargetPage() {
  const navigate = useNavigate();
  const [files, setFiles] = useState<SharedFile[]>([]);
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [selectedDogId, setSelectedDogId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  const [searchDog, setSearchDog] = useState('');

  useEffect(() => {
    readSharedFiles().then(setFiles);
    dogsService.list().then(setDogs).catch(() => {});
  }, []);

  const allDogs: Dog[] = dogs;

  const filtered = allDogs.filter(d =>
    d.name.toLowerCase().includes(searchDog.toLowerCase()) ||
    (d.breed ?? '').toLowerCase().includes(searchDog.toLowerCase())
  );

  const handleUpload = async () => {
    if (!selectedDogId || files.length === 0) return;
    setUploading(true);
    setError('');
    try {
      for (const f of files) {
        const file = new File([f.blob], f.name, { type: f.blob.type });
        await dogsService.addMedia(selectedDogId, file);
      }
      setDone(true);
    } catch {
      setError('Erro ao enviar fotos. Verifique sua conexão e tente novamente.');
    } finally {
      setUploading(false);
    }
  };

  if (done) {
    const dog = allDogs.find(d => d.id === selectedDogId);
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
        <div className="bg-slate-800 rounded-2xl p-8 max-w-sm w-full text-center shadow-2xl">
          <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          </div>
          <h2 className="text-white text-xl font-bold mb-2">Fotos enviadas!</h2>
          <p className="text-slate-400 text-sm mb-6">
            {files.length} foto{files.length > 1 ? 's' : ''} adicionada{files.length > 1 ? 's' : ''} para <strong className="text-white">{dog?.name}</strong>.
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => navigate('/canil/caes')}
              className="flex-1 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-colors"
            >
              Ver Cães
            </button>
            <button
              onClick={() => navigate('/canil/ninhadas')}
              className="flex-1 px-4 py-2.5 rounded-xl bg-slate-700 hover:bg-slate-600 text-white text-sm font-semibold transition-colors"
            >
              Ninhadas
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 pt-6 pb-4 border-b border-slate-700">
        <button onClick={() => navigate(-1)} className="text-slate-400 hover:text-white">
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
        <div>
          <h1 className="text-white font-bold text-lg leading-tight">Vincular fotos</h1>
          <p className="text-slate-400 text-xs">{files.length} foto{files.length > 1 ? 's' : ''} recebida{files.length > 1 ? 's' : ''}</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">

        {/* Preview */}
        {files.length > 0 && (
          <div>
            <p className="text-slate-400 text-xs font-medium mb-2 uppercase tracking-wide">Fotos recebidas</p>
            <div className="grid grid-cols-3 gap-2">
              {files.map((f, i) => (
                <div key={i} className="aspect-square rounded-xl overflow-hidden bg-slate-700">
                  <img src={f.preview} alt="" className="w-full h-full object-cover" />
                </div>
              ))}
            </div>
          </div>
        )}

        {files.length === 0 && (
          <div className="text-center py-10">
            <p className="text-slate-500 text-sm">Nenhuma foto recebida.</p>
            <p className="text-slate-600 text-xs mt-1">Use o botão "Compartilhar" em qualquer app e selecione Border Omni.</p>
          </div>
        )}

        {/* Dog selector */}
        {files.length > 0 && (
          <div>
            <p className="text-slate-400 text-xs font-medium mb-2 uppercase tracking-wide">Escolha o cão</p>
            <input
              type="text"
              value={searchDog}
              onChange={e => setSearchDog(e.target.value)}
              placeholder="Buscar por nome ou raça…"
              className="w-full bg-slate-700 text-white rounded-xl px-4 py-2.5 text-sm border border-slate-600 focus:border-blue-500 outline-none mb-3"
            />
            <div className="space-y-2">
              {filtered.length === 0 && (
                <p className="text-slate-500 text-sm text-center py-4">Nenhum cão encontrado.</p>
              )}
              {filtered.map(dog => (
                <button
                  key={dog.id}
                  onClick={() => setSelectedDogId(dog.id === selectedDogId ? null : dog.id)}
                  className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-colors text-left ${
                    selectedDogId === dog.id
                      ? 'border-blue-500 bg-blue-900/20'
                      : 'border-slate-700 bg-slate-800 hover:border-slate-500'
                  }`}
                >
                  <div className="w-10 h-10 rounded-lg overflow-hidden bg-slate-600 flex-shrink-0">
                    {dog.cover_photo ? (
                      <img src={dog.cover_photo} alt={dog.name} className="w-full h-full object-cover" />
                    ) : (
                      <div className={`w-full h-full flex items-center justify-center font-bold ${dog.sex === 'M' ? 'bg-blue-700' : 'bg-pink-700'}`}>
                        {dog.sex === 'M' ? '♂' : '♀'}
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-sm font-semibold truncate">{dog.name}</p>
                    <p className="text-slate-400 text-xs truncate">{dog.breed} · {dog.sex === 'M' ? 'Macho' : 'Fêmea'}</p>
                  </div>
                  {selectedDogId === dog.id && (
                    <svg className="w-5 h-5 text-blue-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {error && <p className="text-red-400 text-sm text-center">{error}</p>}
      </div>

      {/* Footer action */}
      {files.length > 0 && (
        <div className="px-4 pb-6 pt-3 border-t border-slate-700">
          <button
            onClick={handleUpload}
            disabled={!selectedDogId || uploading}
            className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white font-bold text-sm transition-colors"
          >
            {uploading ? 'Enviando…' : `Vincular ${files.length} foto${files.length > 1 ? 's' : ''} ao cão selecionado`}
          </button>
        </div>
      )}
    </div>
  );
}
