import { useState, useEffect, useCallback } from 'react';
import DateInput from '../components/DateInput';
import UploadZone from '../components/UploadZone';
import { littersService, type LitterPayload } from '../services/litters';
import { litterHealthService, type LitterHealthPayload } from '../services/litterHealth';
import { dogsService, type DogPayload } from '../services/dogs';
import { dogHealthService, type HealthRecordPayload } from '../services/dogHealth';
import type { Litter, Dog, DogMedia, DogHealthRecord, LitterHealthRecord, HealthRecordType } from '../types';

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

// ─── Litter Card ──────────────────────────────────────────────────────────────

function LitterCard({
  litter,
  onEdit,
  onPuppies,
}: {
  litter: Litter;
  onEdit: () => void;
  onPuppies: () => void;
}) {
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

        <div className="mt-auto flex gap-2">
          <button
            onClick={onEdit}
            className="flex-1 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium transition-colors"
          >
            Detalhes
          </button>
          <button
            onClick={onPuppies}
            className="flex-1 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors"
          >
            Filhotes ({litter.total_count})
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Puppies Modal ─────────────────────────────────────────────────────────────

interface PuppyFormState extends Partial<DogPayload> {
  _mediaFiles?: { file: File; preview: string }[];
}

interface PuppiesModalProps {
  litter: Litter;
  onClose: () => void;
  onChanged: (litter: Litter) => void;
}

function PuppiesModal({ litter, onClose, onChanged }: PuppiesModalProps) {
  const [puppies, setPuppies] = useState<Dog[]>(litter.puppies ?? []);
  const [editingPuppy, setEditingPuppy] = useState<Dog | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<PuppyFormState>({});
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Dog | null>(null);
  const [uploadingMedia, setUploadingMedia] = useState(false);
  const [expandedPuppyId, setExpandedPuppyId] = useState<number | null>(null);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);

  // Health records for the puppy being edited/created
  const [puppyHealth, setPuppyHealth] = useState<DogHealthRecord[]>([]);
  const [healthForm, setHealthForm] = useState<Partial<HealthRecordPayload>>({ record_type: 'vaccine', date: '' });
  const [formTab, setFormTab] = useState<'data' | 'health' | 'photos'>('data');

  const openNew = () => {
    setEditingPuppy(null);
    setForm({
      sex: 'M',
      status: 'available',
      breed: 'Border Collie',
      birth_date: litter.birth_date ?? null,
      father: litter.father ?? null,
      mother: litter.mother ?? null,
      _mediaFiles: [],
    });
    setPuppyHealth([]);
    setHealthForm({ record_type: 'vaccine', date: '' });
    setFormTab('data');
    setShowForm(true);
  };

  const openEdit = (dog: Dog) => {
    setEditingPuppy(dog);
    setForm({
      name: dog.name,
      breed: dog.breed,
      sex: dog.sex,
      birth_date: dog.birth_date,
      color: dog.color,
      pedigree_number: dog.pedigree_number,
      microchip: dog.microchip,
      tattoo: dog.tattoo,
      status: dog.status,
      price: dog.price,
      notes: dog.notes,
      father: dog.father ?? litter.father ?? null,
      mother: dog.mother ?? litter.mother ?? null,
      origin_litter: litter.id,
      _mediaFiles: [],
    });
    setPuppyHealth(dog.health_records ?? []);
    setHealthForm({ record_type: 'vaccine', date: '' });
    setFormTab('data');
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditingPuppy(null);
    setForm({});
  };

  const setF = (key: keyof DogPayload, value: unknown) =>
    setForm(f => ({ ...f, [key]: value }));

  const handleSavePuppy = async () => {
    if (!form.name) return;
    setSaving(true);
    try {
      const payload: DogPayload = {
        name: form.name!,
        breed: form.breed ?? 'Border Collie',
        sex: form.sex as 'M' | 'F',
        birth_date: form.birth_date ?? litter.birth_date ?? null,
        color: form.color ?? '',
        pedigree_number: form.pedigree_number ?? '',
        microchip: form.microchip ?? '',
        tattoo: form.tattoo ?? '',
        status: form.status ?? 'available',
        price: form.price ?? null,
        notes: form.notes ?? '',
        father: form.father ?? litter.father ?? null,
        mother: form.mother ?? litter.mother ?? null,
        origin_litter: litter.id,
      };

      let saved: Dog;
      if (editingPuppy) {
        saved = await dogsService.update(editingPuppy.id, payload);
      } else {
        saved = await dogsService.create(payload);
      }

      if (form._mediaFiles && form._mediaFiles.length > 0) {
        setUploadingMedia(true);
        for (const m of form._mediaFiles) {
          await dogsService.addMedia(saved.id, m.file);
        }
        saved = await dogsService.get(saved.id);
        setUploadingMedia(false);
      }

      setPuppies(prev => {
        const idx = prev.findIndex(p => p.id === saved.id);
        if (idx >= 0) {
          const next = [...prev];
          next[idx] = saved;
          return next;
        }
        return [...prev, saved];
      });

      closeForm();

      // Notify parent with updated total count
      const updated = await littersService.get(litter.id);
      onChanged(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
      setUploadingMedia(false);
    }
  };

  const handleDeletePuppy = async () => {
    if (!deleteTarget) return;
    await dogsService.remove(deleteTarget.id);
    setPuppies(prev => prev.filter(p => p.id !== deleteTarget.id));
    setDeleteTarget(null);
    const updated = await littersService.get(litter.id);
    onChanged(updated);
  };

  const handleRemoveExistingMedia = async (mediaId: number) => {
    if (!editingPuppy) return;
    await dogsService.removeMedia(editingPuppy.id, mediaId);
    setEditingPuppy(prev => prev ? {
      ...prev,
      media: prev.media.filter(m => m.id !== mediaId),
    } : null);
  };

  const addHealthRecord = async () => {
    if (!editingPuppy || !healthForm.description || !healthForm.date) return;
    const record = await dogHealthService.create({
      dog: editingPuppy.id,
      record_type: healthForm.record_type as HealthRecordType,
      description: healthForm.description,
      date: healthForm.date,
      next_date: healthForm.next_date,
      vet: healthForm.vet,
    });
    setPuppyHealth(prev => [record, ...prev]);
    setHealthForm({ record_type: 'vaccine', date: '' });
  };

  const removeHealthRecord = async (id: number) => {
    await dogHealthService.remove(id);
    setPuppyHealth(prev => prev.filter(r => r.id !== id));
  };

  const existingMedia: DogMedia[] = editingPuppy?.media ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-slate-800 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[92vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-slate-700 flex-shrink-0">
          <div>
            <h2 className="text-white text-lg font-bold">Filhotes — {litter.name}</h2>
            <div className="flex gap-4 mt-1 text-xs text-slate-400">
              {litter.father_name && <span><span className="text-slate-500">Pai:</span> <strong className="text-white">{litter.father_name}</strong></span>}
              {litter.mother_name && <span><span className="text-slate-500">Mãe:</span> <strong className="text-white">{litter.mother_name}</strong></span>}
              {litter.birth_date && <span><span className="text-slate-500">Nasc.:</span> <strong className="text-white">{new Date(litter.birth_date).toLocaleDateString('pt-BR')}</strong></span>}
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors flex-shrink-0 ml-4">
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <div className="flex flex-1 min-h-0 overflow-hidden">

          {/* List view — only visible when form is closed */}
          {!showForm && (
          <div className="flex flex-col flex-1">
            <div className="p-4 flex-shrink-0">
              <button
                onClick={openNew}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition-colors"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
                Novo Filhote
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-2">
              {puppies.length === 0 ? (
                <div className="text-center py-10 text-slate-500">
                  <svg className="w-10 h-10 mx-auto mb-2 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1}>
                    <path d="M10 5.172C10 3.782 8.423 2.679 6.5 3c-2.823.47-4.113 6.006-4 7 .08.703 1.725 1.722 3.656 2 1.261.19 2.148-.568 2.344-1"/>
                    <path d="M14.267 5.172c0-1.39 1.577-2.493 3.5-2.172 2.823.47 4.113 6.006 4 7-.08.703-1.725 1.722-3.656 2-1.261.19-2.148-.568-2.344-1"/>
                    <path d="M4.42 11.247A13.152 13.152 0 0 0 4 14.556C4 18.728 7.582 21 12 21s8-2.272 8-6.444c0-1.061-.162-2.2-.493-3.309"/>
                  </svg>
                  <p className="text-xs">Nenhum filhote.</p>
                  <p className="text-xs mt-1">Clique em "Novo Filhote".</p>
                </div>
              ) : (
                puppies.map(puppy => {
                  const isExpanded = expandedPuppyId === puppy.id;
                  const photos = puppy.media ?? [];
                  return (
                    <div
                      key={puppy.id}
                      className={`rounded-xl overflow-hidden border transition-colors ${
                        editingPuppy?.id === puppy.id
                          ? 'border-blue-500 bg-blue-900/20'
                          : 'border-slate-700 bg-slate-700/40 hover:border-slate-500'
                      }`}
                    >
                      {/* Card header — click to expand */}
                      <div
                        className="flex items-center gap-3 p-3 cursor-pointer select-none"
                        onClick={() => setExpandedPuppyId(isExpanded ? null : puppy.id)}
                      >
                        <div className="w-16 h-16 rounded-xl overflow-hidden bg-slate-600 flex-shrink-0">
                          {puppy.cover_photo ? (
                            <img src={puppy.cover_photo} alt={puppy.name} className="w-full h-full object-cover" />
                          ) : (
                            <div className={`w-full h-full flex items-center justify-center text-white font-bold text-xl ${
                              puppy.sex === 'M' ? 'bg-blue-700' : 'bg-pink-700'
                            }`}>
                              {puppy.sex === 'M' ? '♂' : '♀'}
                            </div>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="text-white text-base font-bold truncate">{puppy.name}</p>
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold flex-shrink-0 ${puppy.sex === 'M' ? 'bg-blue-600 text-white' : 'bg-pink-500 text-white'}`}>
                              {puppy.sex === 'M' ? '♂ Macho' : '♀ Fêmea'}
                            </span>
                          </div>
                          {puppy.color && (
                            <p className="text-slate-400 text-xs mt-0.5 truncate">{puppy.color}</p>
                          )}
                          <div className="flex items-center gap-2 mt-1 flex-wrap">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${STATUS_COLORS[puppy.status] ?? ''}`}>
                              {STATUS_LABELS[puppy.status] ?? puppy.status}
                            </span>
                            {puppy.price && (
                              <span className="text-emerald-400 text-sm font-bold">
                                R$ {parseFloat(puppy.price).toLocaleString('pt-BR')}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          {photos.length > 0 && (
                            <span className="text-slate-500 text-xs">{photos.length} foto{photos.length > 1 ? 's' : ''}</span>
                          )}
                          <svg
                            className={`w-4 h-4 text-slate-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
                          >
                            <polyline points="6 9 12 15 18 9"/>
                          </svg>
                          <button
                            onClick={e => { e.stopPropagation(); openEdit(puppy); }}
                            className="text-slate-400 hover:text-blue-400 transition-colors"
                            title="Editar"
                          >
                            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                            </svg>
                          </button>
                          <button
                            onClick={e => { e.stopPropagation(); setDeleteTarget(puppy); }}
                            className="text-slate-400 hover:text-red-400 transition-colors"
                            title="Excluir"
                          >
                            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                              <polyline points="3 6 5 6 21 6"/>
                              <path d="M19 6l-1 14H6L5 6"/>
                            </svg>
                          </button>
                        </div>
                      </div>

                      {/* Expandable photos section */}
                      {isExpanded && (
                        <div className="px-3 pb-3 border-t border-slate-700/60 pt-2">
                          {photos.length === 0 ? (
                            <p className="text-slate-500 text-[10px] text-center py-3">Sem fotos cadastradas.</p>
                          ) : (
                            <div className="grid grid-cols-3 gap-1.5">
                              {photos.map(photo => (
                                <button
                                  key={photo.id}
                                  onClick={() => setLightboxUrl(photo.file_url ?? photo.file)}
                                  className="aspect-square rounded-lg overflow-hidden bg-slate-700 hover:opacity-90 transition-opacity focus:outline-none focus:ring-2 focus:ring-blue-500"
                                >
                                  <img src={photo.file_url ?? photo.file} alt="" className="w-full h-full object-cover" />
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
          )}

          {/* Form view — full width, only visible when form is open */}
          {showForm && (
            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
              {/* Form header with back button */}
              <div className="flex items-center gap-3 px-5 pt-4 pb-3 border-b border-slate-700 flex-shrink-0">
                <button onClick={closeForm} className="text-slate-400 hover:text-white transition-colors flex-shrink-0">
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <polyline points="15 18 9 12 15 6"/>
                  </svg>
                </button>
                <p className="text-white text-sm font-bold flex-1 truncate">
                  {editingPuppy ? `Editando: ${editingPuppy.name}` : 'Novo filhote'}
                </p>
              </div>

              {/* Form tabs */}
              <div className="flex gap-1 px-5 pt-3 flex-shrink-0">
                {(['data', 'health', 'photos'] as const).map(t => (
                  <button
                    key={t}
                    onClick={() => setFormTab(t)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                      formTab === t ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {t === 'data' ? 'Dados' : t === 'health' ? 'Saúde' : 'Fotos'}
                  </button>
                ))}
              </div>

              {/* Form body */}
              <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
                {formTab === 'data' && (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="col-span-2">
                      <label className="text-slate-400 text-xs font-medium block mb-1">Nome *</label>
                      <input
                        value={form.name ?? ''}
                        onChange={e => setF('name', e.target.value)}
                        className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                        placeholder="Ex: Apollo, Thor, Luna…"
                        autoFocus
                      />
                    </div>

                    <div>
                      <label className="text-slate-400 text-xs font-medium block mb-1">Sexo</label>
                      <div className="flex gap-2">
                        {(['M', 'F'] as const).map(s => (
                          <button
                            key={s}
                            type="button"
                            onClick={() => setF('sex', s)}
                            className={`flex-1 py-2 rounded-lg text-xs font-semibold border transition-colors ${
                              form.sex === s
                                ? 'bg-blue-600 border-blue-500 text-white'
                                : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'
                            }`}
                          >
                            {s === 'M' ? '♂ Macho' : '♀ Fêmea'}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="text-slate-400 text-xs font-medium block mb-1">Cor / Pelagem</label>
                      <input
                        value={form.color ?? ''}
                        onChange={e => setF('color', e.target.value)}
                        className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                        placeholder="Ex: Preto e branco"
                      />
                    </div>

                    <div>
                      <label className="text-slate-400 text-xs font-medium block mb-1">Pedigree (CBKC/FCI)</label>
                      <input
                        value={form.pedigree_number ?? ''}
                        onChange={e => setF('pedigree_number', e.target.value)}
                        className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                      />
                    </div>

                    <div>
                      <label className="text-slate-400 text-xs font-medium block mb-1">Microchip</label>
                      <input
                        value={form.microchip ?? ''}
                        onChange={e => setF('microchip', e.target.value)}
                        className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                      />
                    </div>

                    <div>
                      <label className="text-slate-400 text-xs font-medium block mb-1">Tatuagem</label>
                      <input
                        value={form.tattoo ?? ''}
                        onChange={e => setF('tattoo', e.target.value)}
                        className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                      />
                    </div>

                    <div>
                      <label className="text-slate-400 text-xs font-medium block mb-1">Status</label>
                      <select
                        value={form.status ?? 'available'}
                        onChange={e => setF('status', e.target.value)}
                        className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 outline-none"
                      >
                        <option value="available">Disponível</option>
                        <option value="reserved">Reservado</option>
                        <option value="sold">Vendido</option>
                        <option value="own">Plantel próprio</option>
                        <option value="deceased">Falecido</option>
                      </select>
                    </div>

                    <div>
                      <label className="text-slate-400 text-xs font-medium block mb-1">Preço (R$)</label>
                      <input
                        type="number"
                        step="0.01"
                        value={form.price ?? ''}
                        onChange={e => setF('price', e.target.value || null)}
                        className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                        placeholder="0,00"
                      />
                    </div>

                    <div className="col-span-2">
                      <label className="text-slate-400 text-xs font-medium block mb-1">Observações</label>
                      <textarea
                        value={form.notes ?? ''}
                        onChange={e => setF('notes', e.target.value)}
                        rows={2}
                        className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none resize-none"
                      />
                    </div>
                  </div>
                )}

                {formTab === 'health' && (
                  <>
                    {!editingPuppy ? (
                      <p className="text-slate-400 text-xs text-center py-6">
                        Salve o filhote primeiro para adicionar registros de saúde.
                      </p>
                    ) : (
                      <>
                        <div className="bg-slate-700/50 rounded-xl p-3 space-y-3">
                          <p className="text-white text-xs font-semibold">Novo registro</p>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="text-slate-400 text-xs mb-1 block">Tipo</label>
                              <select
                                value={healthForm.record_type}
                                onChange={e => setHealthForm(f => ({ ...f, record_type: e.target.value as HealthRecordType }))}
                                className="w-full bg-slate-700 text-white rounded-lg px-2 py-1.5 text-xs border border-slate-600 outline-none"
                              >
                                {Object.entries(HEALTH_TYPE_LABELS).map(([k, v]) => (
                                  <option key={k} value={k}>{v}</option>
                                ))}
                              </select>
                            </div>
                            <div>
                              <label className="text-slate-400 text-xs mb-1 block">Data *</label>
                              <DateInput
                                value={healthForm.date ?? ''}
                                onChange={v => setHealthForm(f => ({ ...f, date: v }))}
                                className="w-full bg-slate-700 text-white rounded-lg px-2 py-1.5 text-xs border border-slate-600 outline-none"
                              />
                            </div>
                            <div className="col-span-2">
                              <label className="text-slate-400 text-xs mb-1 block">Descrição *</label>
                              <input
                                value={healthForm.description ?? ''}
                                onChange={e => setHealthForm(f => ({ ...f, description: e.target.value }))}
                                className="w-full bg-slate-700 text-white rounded-lg px-2 py-1.5 text-xs border border-slate-600 outline-none"
                                placeholder="Ex: V10, Antirrábica, HD OFA…"
                              />
                            </div>
                            <div>
                              <label className="text-slate-400 text-xs mb-1 block">Próxima</label>
                              <DateInput
                                value={healthForm.next_date ?? ''}
                                onChange={v => setHealthForm(f => ({ ...f, next_date: v || undefined }))}
                                className="w-full bg-slate-700 text-white rounded-lg px-2 py-1.5 text-xs border border-slate-600 outline-none"
                              />
                            </div>
                            <div>
                              <label className="text-slate-400 text-xs mb-1 block">Veterinário</label>
                              <input
                                value={healthForm.vet ?? ''}
                                onChange={e => setHealthForm(f => ({ ...f, vet: e.target.value }))}
                                className="w-full bg-slate-700 text-white rounded-lg px-2 py-1.5 text-xs border border-slate-600 outline-none"
                              />
                            </div>
                          </div>
                          <button
                            onClick={addHealthRecord}
                            disabled={!healthForm.description || !healthForm.date}
                            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors"
                          >
                            Adicionar
                          </button>
                        </div>
                        <div>
                          {puppyHealth.length === 0 ? (
                            <p className="text-slate-500 text-xs text-center py-3">Nenhum registro.</p>
                          ) : (
                            puppyHealth.map(r => (
                              <div key={r.id} className="flex items-center gap-2 py-2 border-b border-slate-700">
                                <div className="flex-1 min-w-0">
                                  <p className="text-white text-xs font-medium truncate">{r.description}</p>
                                  <p className="text-slate-400 text-[10px]">
                                    {r.record_type_display} · {new Date(r.date).toLocaleDateString('pt-BR')}
                                    {r.next_date && ` · Próx: ${new Date(r.next_date).toLocaleDateString('pt-BR')}`}
                                  </p>
                                </div>
                                <button onClick={() => removeHealthRecord(r.id)} className="text-slate-500 hover:text-red-400">
                                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                                    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                                  </svg>
                                </button>
                              </div>
                            ))
                          )}
                        </div>
                      </>
                    )}
                  </>
                )}

                {formTab === 'photos' && (
                  <>
                    {(existingMedia.length > 0 || (form._mediaFiles ?? []).length > 0) && (
                      <div className="grid grid-cols-3 gap-2 mb-3">
                        {existingMedia.map((m: DogMedia) => (
                          <div key={m.id} className="relative aspect-square rounded-lg overflow-hidden bg-slate-700 group">
                            <img src={m.file_url ?? m.file} alt="" className="w-full h-full object-cover" />
                            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-3 transition-opacity">
                              <button
                                onClick={() => setLightboxUrl(m.file_url ?? m.file)}
                                className="p-2.5 rounded-full bg-white/20 hover:bg-white/40 transition-colors"
                                title="Visualizar"
                              >
                                <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                                </svg>
                              </button>
                              <button
                                onClick={() => handleRemoveExistingMedia(m.id)}
                                className="p-2.5 rounded-full bg-white/20 hover:bg-red-500/80 transition-colors"
                                title="Excluir"
                              >
                                <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                                  <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                                </svg>
                              </button>
                            </div>
                          </div>
                        ))}
                        {(form._mediaFiles ?? []).map((m, i) => (
                          <div key={i} className="relative aspect-square rounded-lg overflow-hidden bg-slate-700 group">
                            <img src={m.preview} alt="" className="w-full h-full object-cover" />
                            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-3 transition-opacity">
                              <button
                                onClick={() => setLightboxUrl(m.preview)}
                                className="p-2.5 rounded-full bg-white/20 hover:bg-white/40 transition-colors"
                                title="Visualizar"
                              >
                                <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                                </svg>
                              </button>
                              <button
                                onClick={() => setForm(f => ({ ...f, _mediaFiles: (f._mediaFiles ?? []).filter((_, j) => j !== i) }))}
                                className="p-2.5 rounded-full bg-white/20 hover:bg-red-500/80 transition-colors"
                                title="Excluir"
                              >
                                <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                                  <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                                </svg>
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    <UploadZone
                      compact
                      onFiles={files => setForm(f => ({ ...f, _mediaFiles: [...(f._mediaFiles ?? []), ...files.map(f2 => ({ file: f2, preview: URL.createObjectURL(f2) }))] }))}
                    />
                    {uploadingMedia && <p className="text-blue-400 text-xs text-center mt-2">Enviando fotos…</p>}
                  </>
                )}
              </div>

              {/* Form footer */}
              <div className="px-5 pb-4 pt-3 border-t border-slate-700 flex gap-2 flex-shrink-0">
                <button onClick={closeForm} className="px-3 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-xs transition-colors">
                  Cancelar
                </button>
                <button
                  onClick={handleSavePuppy}
                  disabled={saving || !form.name}
                  className="flex-1 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-xs font-semibold transition-colors"
                >
                  {saving ? 'Salvando…' : editingPuppy ? 'Salvar alterações' : 'Cadastrar filhote'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Delete confirmation */}
      {deleteTarget && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/60">
          <div className="bg-slate-800 rounded-xl shadow-2xl p-6 w-full max-w-sm text-white">
            <p className="text-base mb-6">Excluir <strong>{deleteTarget.name}</strong>? Esta ação não pode ser desfeita.</p>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setDeleteTarget(null)} className="px-4 py-2 rounded-lg bg-slate-600 hover:bg-slate-500 text-sm">
                Cancelar
              </button>
              <button onClick={handleDeletePuppy} className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-sm font-semibold">
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Lightbox */}
      {lightboxUrl && (
        <div
          className="fixed inset-0 z-70 flex items-center justify-center bg-black/90"
          onClick={() => setLightboxUrl(null)}
        >
          <button
            className="absolute top-4 right-4 text-white/70 hover:text-white transition-colors"
            onClick={() => setLightboxUrl(null)}
          >
            <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
          <img
            src={lightboxUrl}
            alt=""
            className="max-w-[90vw] max-h-[90vh] rounded-xl object-contain shadow-2xl"
            onClick={e => e.stopPropagation()}
          />
        </div>
      )}
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
  const [tab, setTab] = useState<'data' | 'health' | 'photos'>('data');
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
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);

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

  const males = allDogs.filter(d => d.sex === 'M');
  const females = allDogs.filter(d => d.sex === 'F');

  const tabs = [
    { key: 'data', label: 'Dados' },
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
                <DateInput
                  value={form.mating_date ?? ''}
                  onChange={v => set('mating_date', v || null)}
                  className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 text-xs font-medium block mb-1">Data prevista do parto</label>
                <DateInput
                  value={form.expected_birth_date ?? ''}
                  onChange={v => set('expected_birth_date', v || null)}
                  className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 text-xs font-medium block mb-1">Data de nascimento</label>
                <DateInput
                  value={form.birth_date ?? ''}
                  onChange={v => set('birth_date', v || null)}
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
                        <DateInput
                          value={healthForm.date ?? ''}
                          onChange={v => setHealthForm(f => ({ ...f, date: v }))}
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
                        <DateInput
                          value={healthForm.next_date ?? ''}
                          onChange={v => setHealthForm(f => ({ ...f, next_date: v || undefined }))}
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
              {(existingMedia.length > 0 || mediaFiles.length > 0) && (
                <div className="grid grid-cols-3 gap-3 mb-4">
                  {existingMedia.map(m => (
                    <div key={m.id} className="relative aspect-square rounded-lg overflow-hidden bg-slate-700 group">
                      <img src={m.file_url ?? m.file} alt="" className="w-full h-full object-cover" />
                      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-3 transition-opacity">
                        <button
                          onClick={() => setLightboxUrl(m.file_url ?? m.file)}
                          className="p-2.5 rounded-full bg-white/20 hover:bg-white/40 transition-colors"
                          title="Visualizar"
                        >
                          <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                          </svg>
                        </button>
                        <button
                          onClick={() => removeExistingMedia(m.id)}
                          className="p-2.5 rounded-full bg-white/20 hover:bg-red-500/80 transition-colors"
                          title="Excluir"
                        >
                          <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                  {mediaFiles.map((m, i) => (
                    <div key={i} className="relative aspect-square rounded-lg overflow-hidden bg-slate-700 group">
                      <img src={m.preview} alt="" className="w-full h-full object-cover" />
                      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-3 transition-opacity">
                        <button
                          onClick={() => setLightboxUrl(m.preview)}
                          className="p-2.5 rounded-full bg-white/20 hover:bg-white/40 transition-colors"
                          title="Visualizar"
                        >
                          <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                          </svg>
                        </button>
                        <button
                          onClick={() => setMediaFiles(prev => prev.filter((_, j) => j !== i))}
                          className="p-2.5 rounded-full bg-white/20 hover:bg-red-500/80 transition-colors"
                          title="Excluir"
                        >
                          <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <UploadZone
                onFiles={files => setMediaFiles(prev => [...prev, ...files.map(f => ({ file: f, preview: URL.createObjectURL(f) }))])}
              />
              {uploadingMedia && <p className="text-blue-400 text-xs text-center mt-2">Enviando fotos…</p>}
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

      {/* Lightbox */}
      {lightboxUrl && (
        <div
          className="fixed inset-0 z-60 flex items-center justify-center bg-black/90"
          onClick={() => setLightboxUrl(null)}
        >
          <button
            className="absolute top-4 right-4 text-white/70 hover:text-white transition-colors"
            onClick={() => setLightboxUrl(null)}
          >
            <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
          <img
            src={lightboxUrl}
            alt=""
            className="max-w-[90vw] max-h-[90vh] rounded-xl object-contain shadow-2xl"
            onClick={e => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function LittersPage() {
  const [litters, setLitters] = useState<Litter[]>([]);
  const [allDogs, setAllDogs] = useState<Dog[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalLitter, setModalLitter] = useState<Litter | null | undefined>(undefined);
  const [puppiesTarget, setPuppiesTarget] = useState<Litter | null>(null);

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

  const handleOpenPuppies = async (litter: Litter) => {
    const detail = await littersService.get(litter.id);
    setPuppiesTarget(detail);
  };

  const handlePuppiesChanged = (updated: Litter) => {
    setLitters(prev => prev.map(l => l.id === updated.id ? { ...l, total_count: updated.total_count, male_count: updated.male_count, female_count: updated.female_count } : l));
    setPuppiesTarget(updated);
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
              onPuppies={() => handleOpenPuppies(litter)}
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

      {puppiesTarget && (
        <PuppiesModal
          litter={puppiesTarget}
          onClose={() => setPuppiesTarget(null)}
          onChanged={handlePuppiesChanged}
        />
      )}
    </div>
  );
}
