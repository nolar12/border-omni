import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { littersService, type LitterPayload } from '../services/litters';
import { litterHealthService, type LitterHealthPayload } from '../services/litterHealth';
import { dogsService } from '../services/dogs';
import type { Litter, Dog, LitterHealthRecord, HealthRecordType } from '../types';

const HEALTH_TYPE_LABELS: Record<HealthRecordType, string> = {
  vaccine: 'Vacina',
  deworming: 'Vermifugação',
  exam: 'Exame',
  other: 'Outro',
};

const STATUS_COLORS: Record<string, string> = {
  available: 'bg-emerald-100 text-emerald-700',
  reserved: 'bg-amber-100 text-amber-700',
  sold: 'bg-blue-100 text-blue-700',
  own: 'bg-purple-100 text-purple-700',
  deceased: 'bg-gray-200 text-gray-500',
};

const STATUS_LABELS: Record<string, string> = {
  available: 'Disponível',
  reserved: 'Reservado',
  sold: 'Vendido',
  own: 'Plantel',
  deceased: 'Falecido',
};

// ─── Puppy Mini Card ──────────────────────────────────────────────────────────

function PuppyChip({ dog, onClick }: { dog: Dog; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 rounded-lg px-3 py-2 transition-colors text-left w-full"
    >
      <div className="w-8 h-8 rounded-full bg-slate-600 overflow-hidden flex-shrink-0">
        {dog.cover_photo ? (
          <img src={dog.cover_photo} alt={dog.name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-400 text-xs font-bold">
            {dog.sex}
          </div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-white text-xs font-semibold truncate">{dog.name}</p>
        <span className={`inline-flex items-center px-1.5 py-0 rounded-full text-[10px] font-semibold ${STATUS_COLORS[dog.status] ?? ''}`}>
          {STATUS_LABELS[dog.status] ?? dog.status}
        </span>
      </div>
    </button>
  );
}

// ─── Litter Card ──────────────────────────────────────────────────────────────

function LitterCard({ litter, onEdit }: { litter: Litter; onEdit: () => void }) {
  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 hover:border-slate-500 transition-colors overflow-hidden flex flex-col">
      <div className="aspect-video bg-slate-700 relative overflow-hidden">
        {litter.cover_photo ? (
          <img src={litter.cover_photo} alt={litter.name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <svg className="w-12 h-12 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1}>
              <circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/>
              <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2Z" opacity=".3"/>
              <path d="M7 8c0-1 .5-2 1.5-2.5M17 8c0-1-.5-2-1.5-2.5"/>
              <path d="M12 17c-2 0-3-1-3-2h6c0 1-1 2-3 2Z"/>
            </svg>
          </div>
        )}
        <div className="absolute bottom-2 left-2 flex gap-1.5">
          {litter.male_count > 0 && (
            <span className="bg-blue-600/90 text-white text-xs font-bold px-2 py-0.5 rounded-full">
              {litter.male_count}M
            </span>
          )}
          {litter.female_count > 0 && (
            <span className="bg-pink-600/90 text-white text-xs font-bold px-2 py-0.5 rounded-full">
              {litter.female_count}F
            </span>
          )}
        </div>
      </div>

      <div className="p-4 flex-1 flex flex-col gap-2">
        <div>
          <h3 className="text-white font-bold text-sm truncate">{litter.name}</h3>
          {litter.cbkc_number && (
            <p className="text-slate-500 text-xs">DL/CBKC: {litter.cbkc_number}</p>
          )}
        </div>

        {(litter.father_name || litter.mother_name) && (
          <div className="text-xs text-slate-400 space-y-0.5">
            {litter.father_name && <p><span className="text-slate-500">Pai:</span> {litter.father_name}</p>}
            {litter.mother_name && <p><span className="text-slate-500">Mãe:</span> {litter.mother_name}</p>}
          </div>
        )}

        {litter.birth_date && (
          <p className="text-xs text-slate-400">
            Nascimento: {new Date(litter.birth_date).toLocaleDateString('pt-BR')}
          </p>
        )}

        <button
          onClick={onEdit}
          className="mt-auto w-full px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium transition-colors"
        >
          Ver detalhes
        </button>
      </div>
    </div>
  );
}

// ─── Litter Modal ─────────────────────────────────────────────────────────────

interface LitterModalProps {
  litter?: Litter | null;
  allDogs: Dog[];
  onClose: () => void;
  onSaved: (litter: Litter) => void;
}

function LitterModal({ litter, allDogs, onClose, onSaved }: LitterModalProps) {
  const navigate = useNavigate();
  const [tab, setTab] = useState<'data' | 'puppies' | 'health' | 'photos'>('data');
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<LitterPayload>({
    name: litter?.name ?? '',
    father: litter?.father ?? null,
    mother: litter?.mother ?? null,
    mating_date: litter?.mating_date ?? null,
    expected_birth_date: litter?.expected_birth_date ?? null,
    birth_date: litter?.birth_date ?? null,
    male_count: litter?.male_count ?? 0,
    female_count: litter?.female_count ?? 0,
    cbkc_number: litter?.cbkc_number ?? '',
    notes: litter?.notes ?? '',
  });

  const [healthRecords, setHealthRecords] = useState<LitterHealthRecord[]>(litter?.health_records ?? []);
  const [healthForm, setHealthForm] = useState<Partial<LitterHealthPayload>>({ record_type: 'vaccine', date: '' });
  const [existingMedia, setExistingMedia] = useState(litter?.media ?? []);
  const [mediaFiles, setMediaFiles] = useState<{ file: File; preview: string }[]>([]);
  const [uploadingMedia, setUploadingMedia] = useState(false);

  const set = (key: keyof LitterPayload, value: unknown) =>
    setForm(f => ({ ...f, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    try {
      let saved: Litter;
      if (litter) {
        saved = await littersService.update(litter.id, form);
      } else {
        saved = await littersService.create(form);
      }

      if (mediaFiles.length > 0) {
        setUploadingMedia(true);
        for (const m of mediaFiles) {
          await littersService.addMedia(saved.id, m.file);
        }
        saved = await littersService.get(saved.id);
        setUploadingMedia(false);
      }

      onSaved(saved);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const addHealth = async () => {
    if (!litter || !healthForm.description || !healthForm.date) return;
    const record = await litterHealthService.create({
      litter: litter.id,
      record_type: healthForm.record_type as HealthRecordType,
      description: healthForm.description,
      date: healthForm.date,
      next_date: healthForm.next_date,
      vet: healthForm.vet,
    });
    setHealthRecords(prev => [record, ...prev]);
    setHealthForm({ record_type: 'vaccine', date: '' });
  };

  const removeHealth = async (id: number) => {
    await litterHealthService.remove(id);
    setHealthRecords(prev => prev.filter(r => r.id !== id));
  };

  const removeExistingMedia = async (mediaId: number) => {
    if (!litter) return;
    await littersService.removeMedia(litter.id, mediaId);
    setExistingMedia(prev => prev.filter(m => m.id !== mediaId));
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    setMediaFiles(prev => [...prev, ...files.map(f => ({ file: f, preview: URL.createObjectURL(f) }))]);
  };

  const males = allDogs.filter(d => d.sex === 'M');
  const females = allDogs.filter(d => d.sex === 'F');
  const puppies = litter?.puppies ?? [];

  const tabs = [
    { key: 'data', label: 'Dados' },
    { key: 'puppies', label: `Filhotes (${puppies.length})` },
    { key: 'health', label: 'Saúde' },
    { key: 'photos', label: 'Fotos' },
  ] as const;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-slate-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-slate-700">
          <h2 className="text-white text-lg font-bold">
            {litter ? litter.name : 'Nova Ninhada'}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <div className="flex gap-1 px-6 pt-3 overflow-x-auto">
          {tabs.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                tab === t.key ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {tab === 'data' && (
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="text-slate-400 text-xs font-medium block mb-1">Nome da ninhada *</label>
                <input
                  value={form.name}
                  onChange={e => set('name', e.target.value)}
                  className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                  placeholder="Ex: Ninhada Alfa — Jan/2025"
                />
              </div>

              <div>
                <label className="text-slate-400 text-xs font-medium block mb-1">Pai (macho)</label>
                <select
                  value={form.father ?? ''}
                  onChange={e => set('father', e.target.value ? Number(e.target.value) : null)}
                  className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                >
                  <option value="">— Não informado —</option>
                  {males.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </div>

              <div>
                <label className="text-slate-400 text-xs font-medium block mb-1">Mãe (fêmea)</label>
                <select
                  value={form.mother ?? ''}
                  onChange={e => set('mother', e.target.value ? Number(e.target.value) : null)}
                  className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                >
                  <option value="">— Não informada —</option>
                  {females.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </div>

              <div>
                <label className="text-slate-400 text-xs font-medium block mb-1">Data do cruzamento</label>
                <input
                  type="date"
                  value={form.mating_date ?? ''}
                  onChange={e => set('mating_date', e.target.value || null)}
                  className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 text-xs font-medium block mb-1">Data prevista do parto</label>
                <input
                  type="date"
                  value={form.expected_birth_date ?? ''}
                  onChange={e => set('expected_birth_date', e.target.value || null)}
                  className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 text-xs font-medium block mb-1">Data de nascimento</label>
                <input
                  type="date"
                  value={form.birth_date ?? ''}
                  onChange={e => set('birth_date', e.target.value || null)}
                  className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 text-xs font-medium block mb-1">Nº DL/CBKC</label>
                <input
                  value={form.cbkc_number}
                  onChange={e => set('cbkc_number', e.target.value)}
                  className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 text-xs font-medium block mb-1">Machos</label>
                <input
                  type="number"
                  min={0}
                  value={form.male_count}
                  onChange={e => set('male_count', parseInt(e.target.value) || 0)}
                  className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 text-xs font-medium block mb-1">Fêmeas</label>
                <input
                  type="number"
                  min={0}
                  value={form.female_count}
                  onChange={e => set('female_count', parseInt(e.target.value) || 0)}
                  className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                />
              </div>

              <div className="col-span-2">
                <label className="text-slate-400 text-xs font-medium block mb-1">Observações</label>
                <textarea
                  value={form.notes}
                  onChange={e => set('notes', e.target.value)}
                  rows={3}
                  className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none resize-none"
                />
              </div>
            </div>
          )}

          {tab === 'puppies' && (
            <>
              {puppies.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                  <p className="text-sm">Nenhum filhote vinculado.</p>
                  <p className="text-xs mt-1">Cadastre cães na página <strong className="text-slate-400">Cães</strong> e selecione esta ninhada como origem.</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  {puppies.map(puppy => (
                    <PuppyChip
                      key={puppy.id}
                      dog={puppy}
                      onClick={() => navigate(`/canil/caes`)}
                    />
                  ))}
                </div>
              )}
            </>
          )}

          {tab === 'health' && (
            <>
              {!litter ? (
                <p className="text-slate-400 text-sm text-center py-4">Salve a ninhada primeiro para adicionar registros.</p>
              ) : (
                <>
                  <div className="bg-slate-700/50 rounded-xl p-4 space-y-3">
                    <p className="text-white text-sm font-semibold">Novo registro</p>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-slate-400 text-xs mb-1 block">Tipo</label>
                        <select
                          value={healthForm.record_type}
                          onChange={e => setHealthForm(f => ({ ...f, record_type: e.target.value as HealthRecordType }))}
                          className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 outline-none"
                        >
                          {Object.entries(HEALTH_TYPE_LABELS).map(([k, v]) => (
                            <option key={k} value={k}>{v}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-slate-400 text-xs mb-1 block">Data *</label>
                        <input
                          type="date"
                          value={healthForm.date ?? ''}
                          onChange={e => setHealthForm(f => ({ ...f, date: e.target.value }))}
                          className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 outline-none"
                        />
                      </div>
                      <div className="col-span-2">
                        <label className="text-slate-400 text-xs mb-1 block">Descrição *</label>
                        <input
                          value={healthForm.description ?? ''}
                          onChange={e => setHealthForm(f => ({ ...f, description: e.target.value }))}
                          className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 outline-none"
                          placeholder="Ex: V10 toda a ninhada, Vermifugação com Drontal..."
                        />
                      </div>
                      <div>
                        <label className="text-slate-400 text-xs mb-1 block">Próxima data</label>
                        <input
                          type="date"
                          value={healthForm.next_date ?? ''}
                          onChange={e => setHealthForm(f => ({ ...f, next_date: e.target.value || undefined }))}
                          className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 outline-none"
                        />
                      </div>
                      <div>
                        <label className="text-slate-400 text-xs mb-1 block">Veterinário</label>
                        <input
                          value={healthForm.vet ?? ''}
                          onChange={e => setHealthForm(f => ({ ...f, vet: e.target.value }))}
                          className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 outline-none"
                        />
                      </div>
                    </div>
                    <button
                      onClick={addHealth}
                      disabled={!healthForm.description || !healthForm.date}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      Adicionar
                    </button>
                  </div>

                  <div>
                    {healthRecords.length === 0 && (
                      <p className="text-slate-500 text-sm text-center py-4">Nenhum registro.</p>
                    )}
                    {healthRecords.map(r => (
                      <div key={r.id} className="flex items-center gap-3 py-2 border-b border-slate-700">
                        <div className="flex-1 min-w-0">
                          <p className="text-white text-sm font-medium truncate">{r.description}</p>
                          <p className="text-slate-400 text-xs">
                            {r.record_type_display} · {new Date(r.date).toLocaleDateString('pt-BR')}
                            {r.next_date && ` · Próxima: ${new Date(r.next_date).toLocaleDateString('pt-BR')}`}
                          </p>
                        </div>
                        <button onClick={() => removeHealth(r.id)} className="text-slate-500 hover:text-red-400 flex-shrink-0">
                          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                          </svg>
                        </button>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </>
          )}

          {tab === 'photos' && (
            <>
              <div className="grid grid-cols-3 gap-3">
                {existingMedia.map(m => (
                  <div key={m.id} className="relative aspect-square rounded-lg overflow-hidden bg-slate-700 group">
                    <img src={m.file_url ?? m.file} alt="" className="w-full h-full object-cover" />
                    <button
                      onClick={() => removeExistingMedia(m.id)}
                      className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity"
                    >
                      <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                      </svg>
                    </button>
                  </div>
                ))}
                {mediaFiles.map((m, i) => (
                  <div key={i} className="relative aspect-square rounded-lg overflow-hidden bg-slate-700 group">
                    <img src={m.preview} alt="" className="w-full h-full object-cover" />
                    <button
                      onClick={() => setMediaFiles(prev => prev.filter((_, j) => j !== i))}
                      className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity"
                    >
                      <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                      </svg>
                    </button>
                  </div>
                ))}
                <label className="aspect-square rounded-lg border-2 border-dashed border-slate-600 hover:border-blue-500 flex items-center justify-center cursor-pointer transition-colors">
                  <input type="file" multiple accept="image/*" className="hidden" onChange={handleFileSelect} />
                  <svg className="w-8 h-8 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                  </svg>
                </label>
              </div>
              {uploadingMedia && <p className="text-blue-400 text-xs text-center">Enviando fotos…</p>}
            </>
          )}
        </div>

        <div className="px-6 pb-5 pt-3 border-t border-slate-700 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-sm transition-colors">
            Cancelar
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !form.name}
            className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-sm font-semibold transition-colors"
          >
            {saving ? 'Salvando…' : 'Salvar'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function LittersPage() {
  const [litters, setLitters] = useState<Litter[]>([]);
  const [allDogs, setAllDogs] = useState<Dog[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalLitter, setModalLitter] = useState<Litter | null | undefined>(undefined);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [littersData, dogsData] = await Promise.all([
        littersService.list(),
        dogsService.list(),
      ]);
      setLitters(littersData);
      setAllDogs(dogsData);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSaved = (saved: Litter) => {
    setLitters(prev => {
      const idx = prev.findIndex(l => l.id === saved.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next;
      }
      return [saved, ...prev];
    });
    setModalLitter(undefined);
  };

  const handleEdit = async (litter: Litter) => {
    const detail = await littersService.get(litter.id);
    setModalLitter(detail);
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-white text-2xl font-bold">Ninhadas</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            {litters.length} ninhada{litters.length !== 1 ? 's' : ''} cadastrada{litters.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => setModalLitter(null)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition-colors"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Nova Ninhada
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : litters.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <svg className="w-12 h-12 mx-auto mb-3 opacity-40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1}>
            <circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/>
            <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2Z" opacity=".3"/>
          </svg>
          <p>Nenhuma ninhada cadastrada.</p>
          <button onClick={() => setModalLitter(null)} className="mt-3 text-blue-400 hover:text-blue-300 text-sm">
            Cadastrar primeira ninhada
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {litters.map(litter => (
            <LitterCard
              key={litter.id}
              litter={litter}
              onEdit={() => handleEdit(litter)}
            />
          ))}
        </div>
      )}

      {modalLitter !== undefined && (
        <LitterModal
          litter={modalLitter}
          allDogs={allDogs}
          onClose={() => setModalLitter(undefined)}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}
