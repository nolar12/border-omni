import { useState, useEffect, useCallback } from 'react';
import DateInput from '../components/DateInput';
import { useLocation } from 'react-router-dom';
import { contractsService, type ContractCreatePayload } from '../services/contracts';
import { dogsService } from '../services/dogs';
import type { SaleContract, ContractStatus, Dog } from '../types';

// ─── Status badge ─────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<ContractStatus, string> = {
  draft: 'bg-gray-700 text-gray-200',
  sent: 'bg-blue-700 text-blue-100',
  buyer_filled: 'bg-yellow-600 text-yellow-100',
  approved: 'bg-indigo-600 text-indigo-100',
  signed: 'bg-green-700 text-green-100',
};

function StatusBadge({ status, label }: { status: ContractStatus; label: string }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${STATUS_COLORS[status]}`}>
      {label}
    </span>
  );
}

// ─── Confirmation modal ───────────────────────────────────────────────────────

function ConfirmModal({
  message,
  onConfirm,
  onCancel,
}: {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-slate-800 rounded-xl shadow-2xl p-6 w-full max-w-sm text-white">
        <p className="text-base mb-6">{message}</p>
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel} className="px-4 py-2 rounded-lg bg-slate-600 hover:bg-slate-500 text-sm">
            Cancelar
          </button>
          <button onClick={onConfirm} className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-semibold">
            Confirmar
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Create / Edit drawer ─────────────────────────────────────────────────────

interface PrefilledLead {
  id: number;
  name: string;
  phone: string;
}

interface DrawerProps {
  initial?: SaleContract | null;
  prefilledLead?: PrefilledLead | null;
  prefilledDog?: Dog | null;
  onClose: () => void;
  onSaved: (c: SaleContract) => void;
}

function ContractDrawer({ initial, prefilledLead, prefilledDog, onClose, onSaved }: DrawerProps) {
  const [availableDogs, setAvailableDogs] = useState<Dog[]>([]);
  const [selectedDog, setSelectedDog] = useState<Dog | null>(prefilledDog ?? null);

  useEffect(() => {
    dogsService.listAvailable().then(setAvailableDogs).catch(() => {});
  }, []);

  const applyDog = (dog: Dog | null) => {
    setSelectedDog(dog);
    if (dog) {
      setForm(f => ({
        ...f,
        dog: dog.id,
        puppy_sex: dog.sex,
        puppy_color: dog.color || f.puppy_color,
        puppy_microchip: dog.microchip || f.puppy_microchip,
        puppy_birth_date: dog.birth_date || f.puppy_birth_date,
        puppy_father: dog.father_name || f.puppy_father,
        puppy_mother: dog.mother_name || f.puppy_mother,
      }));
    } else {
      setForm(f => ({ ...f, dog: null }));
    }
  };

  const [form, setForm] = useState<ContractCreatePayload>(() => ({
    lead: initial?.lead ?? prefilledLead?.id ?? null,
    dog: initial?.dog ?? prefilledDog?.id ?? null,
    puppy_sex: initial?.puppy_sex ?? prefilledDog?.sex ?? 'M',
    puppy_color: initial?.puppy_color ?? prefilledDog?.color ?? '',
    puppy_microchip: initial?.puppy_microchip ?? prefilledDog?.microchip ?? '',
    puppy_father: initial?.puppy_father ?? prefilledDog?.father_name ?? '',
    puppy_mother: initial?.puppy_mother ?? prefilledDog?.mother_name ?? '',
    puppy_birth_date: initial?.puppy_birth_date ?? prefilledDog?.birth_date ?? null,
  }));
  const [leadInput, setLeadInput] = useState(() => {
    if (initial) return `${initial.lead_name || ''} — ${initial.lead_phone || ''}`.trim();
    if (prefilledLead) return `${prefilledLead.name || prefilledLead.phone}${prefilledLead.name ? ` — ${prefilledLead.phone}` : ''}`;
    return '';
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const price = form.puppy_sex === 'M' ? 5000 : 6000;
  const deposit = price * 0.3;

  function fmtBRL(v: number) {
    return v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.puppy_color.trim()) { setError('Informe a cor do filhote.'); return; }
    setSaving(true);
    setError('');
    try {
      let saved: SaleContract;
      if (initial) {
        saved = await contractsService.update(initial.id, form);
      } else {
        saved = await contractsService.create(form);
      }
      onSaved(saved);
    } catch {
      setError('Erro ao salvar. Verifique os dados e tente novamente.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full max-w-md bg-slate-800 h-full overflow-y-auto shadow-2xl flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <h2 className="text-white font-bold text-lg">
            {initial ? 'Editar Contrato' : 'Novo Contrato'}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 p-5 space-y-4">
          {/* Lead */}
          <div>
            <label className="text-slate-300 text-sm font-medium block mb-1">Lead</label>
            {prefilledLead ? (
              <div className="flex items-center gap-2 bg-blue-900/40 border border-blue-500/40 rounded-lg px-3 py-2">
                <svg className="w-4 h-4 text-blue-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm font-medium truncate">{prefilledLead.name || prefilledLead.phone}</p>
                  {prefilledLead.name && <p className="text-blue-300 text-xs">{prefilledLead.phone}</p>}
                </div>
                <span className="text-blue-400 text-xs">vinculado</span>
              </div>
            ) : (
              <>
                <input
                  type="text"
                  placeholder="Nome ou telefone do lead..."
                  value={leadInput}
                  onChange={e => setLeadInput(e.target.value)}
                  className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 focus:outline-none"
                />
                <p className="text-slate-500 text-xs mt-1">Deixe em branco se ainda não há lead vinculado.</p>
              </>
            )}
          </div>

          {/* Cão */}
          <div>
            <label className="text-slate-300 text-sm font-medium block mb-1">Cão (produto)</label>
            {selectedDog ? (
              <div className="flex items-center gap-2 bg-emerald-900/40 border border-emerald-500/40 rounded-lg px-3 py-2">
                {selectedDog.cover_photo ? (
                  <img src={selectedDog.cover_photo} alt={selectedDog.name} className="w-8 h-8 rounded-full object-cover flex-shrink-0" />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center flex-shrink-0 text-xs font-bold text-white">
                    {selectedDog.sex}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm font-semibold truncate">{selectedDog.name}</p>
                  <p className="text-emerald-300 text-xs">{selectedDog.breed} · {selectedDog.sex_display}</p>
                </div>
                <button type="button" onClick={() => applyDog(null)} className="text-slate-400 hover:text-white text-xs">
                  trocar
                </button>
              </div>
            ) : (
              <select
                value=""
                onChange={e => {
                  const dog = availableDogs.find(d => d.id === Number(e.target.value));
                  if (dog) applyDog(dog);
                }}
                className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 focus:outline-none"
              >
                <option value="">— Selecionar cão disponível —</option>
                {availableDogs.map(d => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.sex_display}{d.price ? ` · R$ ${parseFloat(d.price).toLocaleString('pt-BR')}` : ''})
                  </option>
                ))}
              </select>
            )}
            <p className="text-slate-500 text-xs mt-1">Selecionar um cão preenche automaticamente os campos abaixo.</p>
          </div>

          {/* Sexo */}
          <div>
            <label className="text-slate-300 text-sm font-medium block mb-1">Sexo do filhote *</label>
            <div className="flex gap-3">
              {(['M', 'F'] as const).map(s => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setForm(f => ({ ...f, puppy_sex: s }))}
                  className={`flex-1 py-2 rounded-lg text-sm font-semibold border transition-colors ${
                    form.puppy_sex === s
                      ? 'bg-blue-600 border-blue-500 text-white'
                      : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  {s === 'M' ? '♂ Macho' : '♀ Fêmea'}
                </button>
              ))}
            </div>
          </div>

          {/* Preço preview */}
          <div className="bg-slate-700/50 rounded-lg p-3 flex gap-4">
            <div className="flex-1 text-center">
              <p className="text-slate-400 text-xs">Valor total</p>
              <p className="text-green-400 font-bold text-base">{fmtBRL(price)}</p>
            </div>
            <div className="w-px bg-slate-600" />
            <div className="flex-1 text-center">
              <p className="text-slate-400 text-xs">Reserva (30%)</p>
              <p className="text-yellow-400 font-bold text-base">{fmtBRL(deposit)}</p>
            </div>
          </div>

          {/* Cor */}
          <div>
            <label className="text-slate-300 text-sm font-medium block mb-1">Cor *</label>
            <input
              required
              type="text"
              placeholder="Ex: Preto e branco"
              value={form.puppy_color}
              onChange={e => setForm(f => ({ ...f, puppy_color: e.target.value }))}
              className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Microchip */}
          <div>
            <label className="text-slate-300 text-sm font-medium block mb-1">Microchip</label>
            <input
              type="text"
              placeholder="Número do microchip"
              value={form.puppy_microchip}
              onChange={e => setForm(f => ({ ...f, puppy_microchip: e.target.value }))}
              className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Pai / Mãe */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-slate-300 text-sm font-medium block mb-1">Pai</label>
              <input
                type="text"
                placeholder="Nome do pai"
                value={form.puppy_father}
                onChange={e => setForm(f => ({ ...f, puppy_father: e.target.value }))}
                className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-slate-300 text-sm font-medium block mb-1">Mãe</label>
              <input
                type="text"
                placeholder="Nome da mãe"
                value={form.puppy_mother}
                onChange={e => setForm(f => ({ ...f, puppy_mother: e.target.value }))}
                className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Data de nascimento */}
          <div>
            <label className="text-slate-300 text-sm font-medium block mb-1">Data de nascimento</label>
            <DateInput
              value={form.puppy_birth_date ?? ''}
              onChange={v => setForm(f => ({ ...f, puppy_birth_date: v || null }))}
              className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}
        </form>

        <div className="p-5 border-t border-white/10 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-lg bg-slate-600 hover:bg-slate-500 text-white text-sm"
          >
            Cancelar
          </button>
          <button
            onClick={handleSubmit as unknown as React.MouseEventHandler}
            disabled={saving}
            className="flex-1 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold"
          >
            {saving ? 'Salvando...' : initial ? 'Salvar alterações' : 'Criar contrato'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── WhatsApp message modal ───────────────────────────────────────────────────

function WhatsappModal({
  contractId,
  onClose,
}: {
  contractId: number;
  onClose: () => void;
}) {
  const [msg, setMsg] = useState('');
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);

  async function send() {
    setSending(true);
    try {
      await contractsService.sendWhatsapp(contractId, msg);
      setDone(true);
      setTimeout(onClose, 1500);
    } catch {
      setSending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-slate-800 rounded-xl shadow-2xl p-6 w-full max-w-md text-white">
        <h3 className="font-bold text-lg mb-3">Enviar mensagem no WhatsApp</h3>
        {done ? (
          <p className="text-green-400 text-center py-4">Mensagem enviada com sucesso!</p>
        ) : (
          <>
            <textarea
              rows={4}
              placeholder="Mensagem personalizada (deixe vazio para usar mensagem padrão com o link do contrato)"
              value={msg}
              onChange={e => setMsg(e.target.value)}
              className="w-full bg-slate-700 text-white rounded-lg px-3 py-2 text-sm border border-slate-600 focus:border-blue-500 focus:outline-none resize-none mb-4"
            />
            <div className="flex gap-3">
              <button onClick={onClose} className="flex-1 py-2 rounded-lg bg-slate-600 hover:bg-slate-500 text-sm">
                Cancelar
              </button>
              <button
                onClick={send}
                disabled={sending}
                className="flex-1 py-2 rounded-lg bg-green-600 hover:bg-green-500 disabled:opacity-50 text-sm font-semibold"
              >
                {sending ? 'Enviando...' : 'Enviar'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Contract card ────────────────────────────────────────────────────────────

function ContractCard({
  contract,
  onEdit,
  onRefresh,
}: {
  contract: SaleContract;
  onEdit: (c: SaleContract) => void;
  onRefresh: () => void;
}) {
  const [loading, setLoading] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ action: string; label: string } | null>(null);
  const [showWa, setShowWa] = useState(false);

  async function doAction(action: string) {
    setLoading(action);
    try {
      if (action === 'send') await contractsService.send(contract.id);
      if (action === 'approve') await contractsService.approve(contract.id);
      if (action === 'delete') await contractsService.remove(contract.id);
      if (action === 'pdf') {
        const blob = await contractsService.generatePdf(contract.id);
        const url = URL.createObjectURL(blob);
        window.open(url, '_blank');
        return;
      }
      if (action === 'preview') {
        window.open(`/api/contracts/${contract.id}/preview_html/`, '_blank');
        return;
      }
      onRefresh();
    } catch {
      // silent
    } finally {
      setLoading(null);
      setConfirm(null);
    }
  }

  const fmtDate = (s: string | null) =>
    s ? new Date(s).toLocaleDateString('pt-BR') : '—';

  const sexIcon = contract.puppy_sex === 'M' ? '♂' : '♀';

  return (
    <>
      {confirm && (
        <ConfirmModal
          message={`Confirma a ação: ${confirm.label}?`}
          onConfirm={() => doAction(confirm.action)}
          onCancel={() => setConfirm(null)}
        />
      )}
      {showWa && (
        <WhatsappModal contractId={contract.id} onClose={() => { setShowWa(false); onRefresh(); }} />
      )}

      <div className="bg-slate-800 rounded-xl border border-white/10 p-5 hover:border-blue-500/30 transition-colors">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-white font-semibold text-sm truncate">
                {contract.buyer_name || 'Comprador não informado'}
              </span>
              <StatusBadge status={contract.status} label={contract.status_display} />
            </div>
            {contract.dog_name && (
              <p className="text-emerald-400 text-xs mt-0.5">Cão: {contract.dog_name}</p>
            )}
            {contract.lead_name && (
              <p className="text-slate-400 text-xs mt-0.5">Lead: {contract.lead_name}</p>
            )}
          </div>
          <span className="text-slate-500 text-xs whitespace-nowrap">#{contract.id}</span>
        </div>

        {/* Puppy info */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm mb-3">
          <div>
            <span className="text-slate-500">Sexo </span>
            <span className="text-white font-medium">{sexIcon} {contract.puppy_sex_display}</span>
          </div>
          <div>
            <span className="text-slate-500">Cor </span>
            <span className="text-white font-medium">{contract.puppy_color || '—'}</span>
          </div>
          {contract.puppy_microchip && (
            <div className="col-span-2">
              <span className="text-slate-500">Microchip </span>
              <span className="text-white font-mono text-xs">{contract.puppy_microchip}</span>
            </div>
          )}
          <div>
            <span className="text-slate-500">Valor </span>
            <span className="text-green-400 font-semibold">
              R$ {Number(contract.price || 0).toLocaleString('pt-BR')}
            </span>
          </div>
          <div>
            <span className="text-slate-500">Reserva </span>
            <span className="text-yellow-400 font-semibold">
              R$ {Number(contract.deposit_amount || 0).toLocaleString('pt-BR')}
            </span>
          </div>
        </div>

        {/* Dates */}
        <p className="text-slate-500 text-xs mb-4">
          Criado {fmtDate(contract.created_at)}
          {contract.buyer_filled_at && ` · Preenchido ${fmtDate(contract.buyer_filled_at)}`}
          {contract.signed_at && ` · Assinado ${fmtDate(contract.signed_at)}`}
        </p>

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => onEdit(contract)}
            className="btn-sm bg-slate-600 hover:bg-slate-500"
          >
            Editar
          </button>

          {contract.status === 'draft' && (
            <button
              onClick={() => setConfirm({ action: 'send', label: 'Enviar contrato ao comprador via WhatsApp' })}
              disabled={!!loading}
              className="btn-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50"
            >
              {loading === 'send' ? '...' : 'Enviar ao comprador'}
            </button>
          )}

          {contract.status === 'buyer_filled' && (
            <button
              onClick={() => setConfirm({ action: 'approve', label: 'Aprovar contrato e notificar comprador para assinar' })}
              disabled={!!loading}
              className="btn-sm bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50"
            >
              {loading === 'approve' ? '...' : 'Aprovar'}
            </button>
          )}

          <button
            onClick={() => setShowWa(true)}
            className="btn-sm bg-green-700 hover:bg-green-600"
          >
            WhatsApp
          </button>

          <button
            onClick={() => doAction('pdf')}
            disabled={!!loading}
            className="btn-sm bg-slate-600 hover:bg-slate-500 disabled:opacity-50"
          >
            {loading === 'pdf' ? '...' : 'PDF'}
          </button>

          <button
            onClick={() => doAction('preview')}
            className="btn-sm bg-slate-600 hover:bg-slate-500"
          >
            Preview
          </button>

          {contract.pdf_url && (
            <a
              href={contract.pdf_url}
              target="_blank"
              rel="noreferrer"
              className="btn-sm bg-slate-600 hover:bg-slate-500 inline-flex items-center"
            >
              Baixar PDF
            </a>
          )}

          <button
            onClick={() => setConfirm({ action: 'delete', label: 'Excluir este contrato permanentemente' })}
            className="btn-sm bg-red-800 hover:bg-red-700 ml-auto"
          >
            Excluir
          </button>
        </div>
      </div>
    </>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function ContractsPage() {
  const location = useLocation();
  const locationState = location.state as { openForLead?: PrefilledLead; dog?: Dog } | null;
  const incomingLead = locationState?.openForLead ?? null;
  const incomingDog = locationState?.dog ?? null;

  const [contracts, setContracts] = useState<SaleContract[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDrawer, setShowDrawer] = useState(() => !!(incomingLead || incomingDog));
  const [editing, setEditing] = useState<SaleContract | null>(null);
  const [prefilledLead, setPrefilledLead] = useState<PrefilledLead | null>(incomingLead);
  const [prefilledDog, setPrefilledDog] = useState<Dog | null>(incomingDog);
  const [filterStatus, setFilterStatus] = useState<ContractStatus | ''>('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await contractsService.list();
      setContracts(res.results);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function handleSaved(c: SaleContract) {
    setContracts(prev => {
      const idx = prev.findIndex(x => x.id === c.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = c;
        return next;
      }
      return [c, ...prev];
    });
    setShowDrawer(false);
    setEditing(null);
  }

  const filtered = filterStatus
    ? contracts.filter(c => c.status === filterStatus)
    : contracts;

  const STATUS_OPTIONS: { value: ContractStatus | ''; label: string }[] = [
    { value: '', label: 'Todos' },
    { value: 'draft', label: 'Rascunho' },
    { value: 'sent', label: 'Enviado' },
    { value: 'buyer_filled', label: 'Preenchido' },
    { value: 'approved', label: 'Aprovado' },
    { value: 'signed', label: 'Assinado' },
  ];

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-white text-2xl font-bold">Contratos</h1>
          <p className="text-slate-400 text-sm mt-1">
            Contratos de compra e venda de filhotes Border Collie
          </p>
        </div>
        <button
          onClick={() => { setEditing(null); setPrefilledLead(null); setPrefilledDog(null); setShowDrawer(true); }}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-semibold"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Novo Contrato
        </button>
      </div>

      {/* Filter */}
      <div className="flex gap-2 flex-wrap mb-4">
        {STATUS_OPTIONS.map(opt => (
          <button
            key={opt.value}
            onClick={() => setFilterStatus(opt.value)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
              filterStatus === opt.value
                ? 'bg-blue-600 border-blue-500 text-white'
                : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'
            }`}
          >
            {opt.label}
          </button>
        ))}
        {contracts.length > 0 && (
          <span className="text-slate-500 text-xs self-center ml-auto">
            {filtered.length} contrato{filtered.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <svg className="w-12 h-12 mx-auto mb-3 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          <p className="text-lg font-medium">Nenhum contrato encontrado</p>
          <p className="text-sm mt-1">Crie o primeiro contrato clicando em "Novo Contrato".</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(c => (
            <ContractCard
              key={c.id}
              contract={c}
              onEdit={contract => { setEditing(contract); setShowDrawer(true); }}
              onRefresh={load}
            />
          ))}
        </div>
      )}

      {/* Drawer */}
      {showDrawer && (
        <ContractDrawer
          initial={editing}
          prefilledLead={editing ? null : prefilledLead}
          prefilledDog={editing ? null : prefilledDog}
          onClose={() => { setShowDrawer(false); setEditing(null); setPrefilledLead(null); setPrefilledDog(null); }}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}
