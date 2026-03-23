import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { dogsService, type DogPayload } from '../services/dogs';
import { dogHealthService, type HealthRecordPayload } from '../services/dogHealth';
import { littersService } from '../services/litters';
import type { Dog, DogHealthRecord, Litter, DogSex, DogStatus, HealthRecordType } from '../types';

// ─── Constants ────────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<DogStatus, string> = {
  available: 'Disponível',
  reserved: 'Reservado',
  sold: 'Vendido',
  own: 'Plantel próprio',
  deceased: 'Falecido',
};

const STATUS_COLORS: Record<DogStatus, string> = {
  available: 'bg-emerald-100 text-emerald-700',
  reserved: 'bg-amber-100 text-amber-700',
  sold: 'bg-blue-100 text-blue-700',
  own: 'bg-purple-100 text-purple-700',
  deceased: 'bg-gray-200 text-gray-500',
};

const HEALTH_TYPE_LABELS: Record<HealthRecordType, string> = {
  vaccine: 'Vacina',
  deworming: 'Vermifugação',
  exam: 'Exame',
  other: 'Outro',
};

// ─── Status Badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: DogStatus }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${STATUS_COLORS[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}

// ─── Dog Card ─────────────────────────────────────────────────────────────────

function DogCard({ dog, onEdit, onContract }: { dog: Dog; onEdit: () => void; onContract: () => void }) {
  const priceStr = dog.price ? `R$ ${parseFloat(dog.price).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : null;

  return (
    <div className="bg-slate-800 rounded-xl overflow-hidden border border-slate-700 hover:border-slate-500 transition-colors flex flex-col">
      <div className="aspect-square bg-slate-700 relative overflow-hidden">
        {dog.cover_photo ? (
          <img src={dog.cover_photo} alt={dog.name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <svg className="w-16 h-16 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1}>
              <path d="M10 5.172C10 3.782 8.423 2.679 6.5 3c-2.823.47-4.113 6.006-4 7 .08.703 1.725 1.722 3.656 2 1.261.19 2.148-.568 2.344-1"/>
              <path d="M14.267 5.172c0-1.39 1.577-2.493 3.5-2.172 2.823.47 4.113 6.006 4 7-.08.703-1.725 1.722-3.656 2-1.261.19-2.148-.568-2.344-1"/>
              <path d="M8 14v.5M16 14v.5"/>
              <path d="M11.25 16.25h1.5L12 17l-.75-.75z"/>
              <path d="M4.42 11.247A13.152 13.152 0 0 0 4 14.556C4 18.728 7.582 21 12 21s8-2.272 8-6.444c0-1.061-.162-2.2-.493-3.309m-9.243-6.082A8.801 8.801 0 0 1 12 5c.78 0 1.5.108 2.161.306"/>
            </svg>
          </div>
        )}
        <div className="absolute top-2 right-2">
          <StatusBadge status={dog.status} />
        </div>
      </div>

      <div className="p-4 flex-1 flex flex-col gap-3">
        <div>
          <h3 className="text-white font-bold text-base truncate">{dog.name}</h3>
          <p className="text-slate-400 text-sm">{dog.breed} · {dog.sex_display}</p>
        </div>

        {(dog.father_name || dog.mother_name) && (
          <div className="text-xs text-slate-400 space-y-0.5">
            {dog.father_name && <p><span className="text-slate-500">Pai:</span> {dog.father_name}</p>}
            {dog.mother_name && <p><span className="text-slate-500">Mãe:</span> {dog.mother_name}</p>}
          </div>
        )}

        {dog.birth_date && (
          <p className="text-xs text-slate-400">
            Nasc.: {new Date(dog.birth_date).toLocaleDateString('pt-BR')}
          </p>
        )}

        {priceStr && (
          <p className="text-emerald-400 font-bold text-sm">{priceStr}</p>
        )}

        <div className="mt-auto flex gap-2">
          <button
            onClick={onEdit}
            className="flex-1 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium transition-colors"
          >
            Editar
          </button>
          {dog.status === 'available' && (
            <button
              onClick={onContract}
              className="flex-1 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors"
            >
              Gerar Contrato
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Health Record Row ────────────────────────────────────────────────────────

function HealthRow({ record, onDelete }: { record: DogHealthRecord; onDelete: () => void }) {
  return (
    <div className="flex items-center gap-3 py-2 border-b border-slate-700">
      <div className="flex-1 min-w-0">
        <p className="text-white text-sm font-medium truncate">{record.description}</p>
        <p className="text-slate-400 text-xs">
          {record.record_type_display} · {new Date(record.date).toLocaleDateString('pt-BR')}
          {record.next_date && ` · Próxima: ${new Date(record.next_date).toLocaleDateString('pt-BR')}`}
          {record.vet && ` · ${record.vet}`}
        </p>
      </div>
      <button onClick={onDelete} className="text-slate-500 hover:text-red-400 transition-colors flex-shrink-0">
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/>
          <path d="M9 6V4h6v2"/>
        </svg>
      </button>
    </div>
  );
}

// ─── Dog Modal ────────────────────────────────────────────────────────────────

interface DogModalProps {
  dog?: Dog | null;
  dogs: Dog[];
  litters: Litter[];
  onClose: () => void;
  onSaved: (dog: Dog) => void;
}

function DogModal({ dog, dogs, litters, onClose, onSaved }: DogModalProps) {
  const [tab, setTab] = useState<'data' | 'health' | 'photos'>('data');
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<DogPayload>({
    name: dog?.name ?? '',
    breed: dog?.breed ?? 'Border Collie',
    sex: (dog?.sex as DogSex) ?? 'M',
    birth_date: dog?.birth_date ?? null,
    color: dog?.color ?? '',
    pedigree_number: dog?.pedigree_number ?? '',
    microchip: dog?.microchip ?? '',
    tattoo: dog?.tattoo ?? '',
    father: dog?.father ?? null,
    mother: dog?.mother ?? null,
    origin_litter: dog?.origin_litter ?? null,
    status: dog?.status ?? 'available',
    price: dog?.price ?? null,
    notes: dog?.notes ?? '',
  });

  const [healthRecords, setHealthRecords] = useState<DogHealthRecord[]>(dog?.health_records ?? []);
  const [healthForm, setHealthForm] = useState<Partial<HealthRecordPayload>>({ record_type: 'vaccine', date: '' });
  const [mediaFiles, setMediaFiles] = useState<{ file: File; preview: string }[]>([]);
  const [existingMedia, setExistingMedia] = useState(dog?.media ?? []);
  const [uploadingMedia, setUploadingMedia] = useState(false);

  const set = (key: keyof DogPayload, value: unknown) =>
    setForm(f => ({ ...f, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    try {
      let saved: Dog;
      if (dog) {
        saved = await dogsService.update(dog.id, form);
      } else {
        saved = await dogsService.create(form);
      }

      if (mediaFiles.length > 0) {
        setUploadingMedia(true);
        for (const m of mediaFiles) {
          await dogsService.addMedia(saved.id, m.file);
        }
        saved = await dogsService.get(saved.id);
        setUploadingMedia(false);
      }

      onSaved(saved);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const addHealthRecord = async () => {
    if (!dog || !healthForm.description || !healthForm.date) return;
    const record = await dogHealthService.create({
      dog: dog.id,
      record_type: healthForm.record_type as HealthRecordType,
      description: healthForm.description,
      date: healthForm.date,
      next_date: healthForm.next_date,
      vet: healthForm.vet,
      notes: healthForm.notes,
    });
    setHealthRecords(prev => [record, ...prev]);
    setHealthForm({ record_type: 'vaccine', date: '' });
  };

  const removeHealthRecord = async (id: number) => {
    await dogHealthService.remove(id);
    setHealthRecords(prev => prev.filter(r => r.id !== id));
  };

  const removeExistingMedia = async (mediaId: number) => {
    if (!dog) return;
    await dogsService.removeMedia(dog.id, mediaId);
    setExistingMedia(prev => prev.filter(m => m.id !== mediaId));
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    const previews = files.map(f => ({ file: f, preview: URL.createObjectURL(f) }));
    setMediaFiles(prev => [...prev, ...previews]);
  };

  const tabs = [
    { key: 'data', label: 'Dados' },
    { key: 'health', label: 'Saúde' },
    { key: 'photos', label: 'Fotos' },
  ] as const;

  const otherDogs = dogs.filter(d => d.id !== dog?.id);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-slate-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-slate-700">
          <h2 className="text-white text-lg font-bold">
            {dog ? `Editar — ${dog.name}` : 'Novo Cachorro'}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <div className="flex gap-1 px-6 pt-3">
          {tabs.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                tab === t.key
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {tab === 'data' && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="text-slate-400 text-xs font-medium block mb-1">Nome *</label>
                  <input
                    value={form.name}
                    onChange={e => set('name', e.target.value)}
                    className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                    placeholder="Ex: Apollo"
                  />
                </div>

                <div>
                  <label className="text-slate-400 text-xs font-medium block mb-1">Raça</label>
                  <input
                    value={form.breed}
                    onChange={e => set('breed', e.target.value)}
                    className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                  />
                </div>

                <div>
                  <label className="text-slate-400 text-xs font-medium block mb-1">Sexo *</label>
                  <select
                    value={form.sex}
                    onChange={e => set('sex', e.target.value)}
                    className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                  >
                    <option value="M">Macho</option>
                    <option value="F">Fêmea</option>
                  </select>
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
                  <label className="text-slate-400 text-xs font-medium block mb-1">Cor / Pelagem</label>
                  <input
                    value={form.color}
                    onChange={e => set('color', e.target.value)}
                    className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                    placeholder="Ex: Preto e Branco"
                  />
                </div>

                <div>
                  <label className="text-slate-400 text-xs font-medium block mb-1">Pedigree (CBKC/FCI)</label>
                  <input
                    value={form.pedigree_number}
                    onChange={e => set('pedigree_number', e.target.value)}
                    className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                  />
                </div>

                <div>
                  <label className="text-slate-400 text-xs font-medium block mb-1">Microchip</label>
                  <input
                    value={form.microchip}
                    onChange={e => set('microchip', e.target.value)}
                    className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                  />
                </div>

                <div>
                  <label className="text-slate-400 text-xs font-medium block mb-1">Tatuagem</label>
                  <input
                    value={form.tattoo}
                    onChange={e => set('tattoo', e.target.value)}
                    className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                  />
                </div>

                <div>
                  <label className="text-slate-400 text-xs font-medium block mb-1">Status</label>
                  <select
                    value={form.status}
                    onChange={e => set('status', e.target.value)}
                    className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
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
                    onChange={e => set('price', e.target.value || null)}
                    className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                    placeholder="0,00"
                  />
                </div>

                <div>
                  <label className="text-slate-400 text-xs font-medium block mb-1">Pai</label>
                  <select
                    value={form.father ?? ''}
                    onChange={e => set('father', e.target.value ? Number(e.target.value) : null)}
                    className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                  >
                    <option value="">— Não informado —</option>
                    {otherDogs.filter(d => d.sex === 'M').map(d => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-slate-400 text-xs font-medium block mb-1">Mãe</label>
                  <select
                    value={form.mother ?? ''}
                    onChange={e => set('mother', e.target.value ? Number(e.target.value) : null)}
                    className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                  >
                    <option value="">— Não informada —</option>
                    {otherDogs.filter(d => d.sex === 'F').map(d => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                </div>

                <div className="col-span-2">
                  <label className="text-slate-400 text-xs font-medium block mb-1">Ninhada de origem</label>
                  <select
                    value={form.origin_litter ?? ''}
                    onChange={e => set('origin_litter', e.target.value ? Number(e.target.value) : null)}
                    className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 outline-none"
                  >
                    <option value="">— Não informada —</option>
                    {litters.map(l => (
                      <option key={l.id} value={l.id}>{l.name}</option>
                    ))}
                  </select>
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
            </>
          )}

          {tab === 'health' && (
            <>
              {!dog && (
                <p className="text-slate-400 text-sm text-center py-4">
                  Salve o cachorro primeiro para adicionar registros de saúde.
                </p>
              )}
              {dog && (
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
                          placeholder="Ex: V10, Antirrábica, HD OFA..."
                        />
                      </div>
                      <div>
                        <label className="text-slate-400 text-xs mb-1 block">Próxima data</label>
                        <input
                          type="date"
                          value={healthForm.next_date ?? ''}
                          onChange={e => setHealthForm(f => ({ ...f, next_date: e.target.value || null }))}
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
                      onClick={addHealthRecord}
                      disabled={!healthForm.description || !healthForm.date}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      Adicionar
                    </button>
                  </div>

                  <div className="space-y-0">
                    {healthRecords.length === 0 && (
                      <p className="text-slate-500 text-sm text-center py-4">Nenhum registro de saúde.</p>
                    )}
                    {healthRecords.map(r => (
                      <HealthRow key={r.id} record={r} onDelete={() => removeHealthRecord(r.id)} />
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
                        <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/>
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
                        <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/>
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
              {uploadingMedia && (
                <p className="text-blue-400 text-xs text-center">Enviando fotos…</p>
              )}
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

export default function DogsPage() {
  const navigate = useNavigate();
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [litters, setLitters] = useState<Litter[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalDog, setModalDog] = useState<Dog | null | undefined>(undefined);
  const [deleteTarget, setDeleteTarget] = useState<Dog | null>(null);

  const [filterStatus, setFilterStatus] = useState('');
  const [filterSex, setFilterSex] = useState('');
  const [search, setSearch] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dogsData, littersData] = await Promise.all([
        dogsService.list({ status: filterStatus || undefined, sex: filterSex || undefined, search: search || undefined }),
        littersService.list(),
      ]);
      setDogs(dogsData);
      setLitters(littersData);
    } finally {
      setLoading(false);
    }
  }, [filterStatus, filterSex, search]);

  useEffect(() => { load(); }, [load]);

  const handleSaved = (saved: Dog) => {
    setDogs(prev => {
      const idx = prev.findIndex(d => d.id === saved.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next;
      }
      return [saved, ...prev];
    });
    setModalDog(undefined);
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    await dogsService.remove(deleteTarget.id);
    setDogs(prev => prev.filter(d => d.id !== deleteTarget.id));
    setDeleteTarget(null);
  };

  const handleContract = (dog: Dog) => {
    navigate('/contratos', { state: { dog } });
  };

  const statusCounts = {
    available: dogs.filter(d => d.status === 'available').length,
    reserved: dogs.filter(d => d.status === 'reserved').length,
    sold: dogs.filter(d => d.status === 'sold').length,
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-white text-2xl font-bold">Cães</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            {dogs.length} cadastrado{dogs.length !== 1 ? 's' : ''} ·{' '}
            <span className="text-emerald-400">{statusCounts.available} disponíveis</span> ·{' '}
            <span className="text-amber-400">{statusCounts.reserved} reservados</span> ·{' '}
            <span className="text-blue-400">{statusCounts.sold} vendidos</span>
          </p>
        </div>
        <button
          onClick={() => setModalDog(null)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition-colors"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Novo Cachorro
        </button>
      </div>

      <div className="flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Buscar por nome…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 w-48"
        />
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500"
        >
          <option value="">Todos os status</option>
          <option value="available">Disponível</option>
          <option value="reserved">Reservado</option>
          <option value="sold">Vendido</option>
          <option value="own">Plantel próprio</option>
          <option value="deceased">Falecido</option>
        </select>
        <select
          value={filterSex}
          onChange={e => setFilterSex(e.target.value)}
          className="bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500"
        >
          <option value="">Todos os sexos</option>
          <option value="M">Machos</option>
          <option value="F">Fêmeas</option>
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : dogs.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <svg className="w-12 h-12 mx-auto mb-3 opacity-40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1}>
            <path d="M10 5.172C10 3.782 8.423 2.679 6.5 3c-2.823.47-4.113 6.006-4 7 .08.703 1.725 1.722 3.656 2 1.261.19 2.148-.568 2.344-1"/>
            <path d="M14.267 5.172c0-1.39 1.577-2.493 3.5-2.172 2.823.47 4.113 6.006 4 7-.08.703-1.725 1.722-3.656 2-1.261.19-2.148-.568-2.344-1"/>
            <path d="M8 14v.5M16 14v.5"/>
            <path d="M11.25 16.25h1.5L12 17l-.75-.75z"/>
            <path d="M4.42 11.247A13.152 13.152 0 0 0 4 14.556C4 18.728 7.582 21 12 21s8-2.272 8-6.444c0-1.061-.162-2.2-.493-3.309m-9.243-6.082A8.801 8.801 0 0 1 12 5c.78 0 1.5.108 2.161.306"/>
          </svg>
          <p>Nenhum cachorro encontrado.</p>
          <button onClick={() => setModalDog(null)} className="mt-3 text-blue-400 hover:text-blue-300 text-sm">
            Cadastrar primeiro cachorro
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {dogs.map(dog => (
            <DogCard
              key={dog.id}
              dog={dog}
              onEdit={() => setModalDog(dog)}
              onContract={() => handleContract(dog)}
            />
          ))}
        </div>
      )}

      {modalDog !== undefined && (
        <DogModal
          dog={modalDog}
          dogs={dogs}
          litters={litters}
          onClose={() => setModalDog(undefined)}
          onSaved={handleSaved}
        />
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-slate-800 rounded-xl shadow-2xl p-6 w-full max-w-sm text-white">
            <p className="text-base mb-6">Excluir <strong>{deleteTarget.name}</strong>? Esta ação não pode ser desfeita.</p>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setDeleteTarget(null)} className="px-4 py-2 rounded-lg bg-slate-600 hover:bg-slate-500 text-sm">
                Cancelar
              </button>
              <button onClick={handleDelete} className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-sm font-semibold">
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
