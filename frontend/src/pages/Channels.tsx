import { useEffect, useState } from 'react';
import { channelsService } from '../services/channels';
import type { ChannelProvider } from '../types';

const EMPTY: Partial<ChannelProvider> = {
  provider: 'whatsapp', app_id: '', phone_number_id: '', business_account_id: '',
  webhook_verify_token: '', webhook_url: '', is_active: true, is_simulated: false,
};

export default function Channels() {
  const [channels, setChannels] = useState<ChannelProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<ChannelProvider | null>(null);
  const [form, setForm] = useState<Partial<ChannelProvider>>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  function load() { channelsService.getAll().then(setChannels).finally(() => setLoading(false)); }
  useEffect(() => { load(); }, []);

  function openCreate() { setEditing(null); setForm(EMPTY); setError(''); setShowForm(true); }
  function openEdit(ch: ChannelProvider) { setEditing(ch); setForm(ch); setError(''); setShowForm(true); }

  async function handleSave() {
    setSaving(true); setError('');
    try {
      editing ? await channelsService.update(editing.id, form) : await channelsService.create(form);
      setShowForm(false); load();
    } catch (err: unknown) {
      const e = err as { response?: { data?: Record<string, string[]> } };
      setError(e?.response?.data ? Object.values(e.response.data).flat().join(' ') : 'Erro ao salvar.');
    } finally { setSaving(false); }
  }

  async function handleDelete(id: number) {
    if (!confirm('Excluir canal?')) return;
    await channelsService.delete(id); load();
  }

  const STATUS_CLS: Record<string, string> = { verified: 'bg-emerald-100 text-emerald-700', pending: 'bg-amber-100 text-amber-700', failed: 'bg-red-100 text-red-700' };

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">Canais de comunicação configurados</p>
        <button onClick={openCreate} className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-2 rounded-xl transition-colors">
          + Novo Canal
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><span className="loading loading-spinner loading-lg text-primary" /></div>
      ) : channels.length === 0 ? (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center text-gray-400">
          <p className="text-4xl mb-3">📱</p>
          <p className="font-medium text-gray-600">Nenhum canal configurado</p>
          <p className="text-xs mt-1">Adicione WhatsApp ou Instagram</p>
          <button onClick={openCreate} className="bg-blue-600 text-white text-xs font-semibold px-3 py-2 rounded-xl mt-4">+ Adicionar</button>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {channels.map(ch => (
            <div key={ch.id} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
              <div className="flex items-start gap-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0 ${ch.provider === 'whatsapp' ? 'bg-green-100' : 'bg-pink-100'}`}>
                  {ch.provider === 'whatsapp' ? '📱' : '📸'}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-800 capitalize text-sm">{ch.provider}</p>
                  <p className="text-xs text-gray-400 truncate">{ch.phone_number_id || ch.instagram_account_id || 'Não configurado'}</p>
                </div>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${STATUS_CLS[ch.verification_status] ?? 'bg-gray-100 text-gray-500'}`}>
                  {ch.verification_status}
                </span>
              </div>
              {ch.webhook_url && <p className="text-xs text-gray-400 mt-2 truncate">↗ {ch.webhook_url}</p>}
              <div className="flex gap-2 mt-3 border-t pt-2.5">
                <button onClick={() => openEdit(ch)} className="text-xs text-blue-600 hover:underline">Editar</button>
                <button onClick={() => handleDelete(ch.id)} className="text-xs text-red-500 hover:underline">Excluir</button>
                {ch.is_simulated && <span className="text-xs text-gray-400 ml-auto">Simulado</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/30 p-4">
          <div className="bg-white rounded-2xl w-full max-w-md shadow-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-800">{editing ? 'Editar Canal' : 'Novo Canal'}</h3>
              <button onClick={() => setShowForm(false)} className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-gray-100 text-gray-400">✕</button>
            </div>
            {error && <div className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2 mb-3">{error}</div>}
            <div className="space-y-3 max-h-[60vh] overflow-y-auto">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Provedor</label>
                <select className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none"
                  value={form.provider} onChange={e => setForm(p => ({ ...p, provider: e.target.value as 'whatsapp' | 'instagram' }))}>
                  <option value="whatsapp">WhatsApp</option>
                  <option value="instagram">Instagram</option>
                </select>
              </div>
              {[['App ID', 'app_id'], ['Phone Number ID', 'phone_number_id'], ['Business Account ID', 'business_account_id'],
                ['Instagram Account ID', 'instagram_account_id'], ['Webhook Verify Token', 'webhook_verify_token'], ['Webhook URL', 'webhook_url']
              ].map(([label, field]) => (
                <div key={field}>
                  <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
                  <input type="text" className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:border-blue-400"
                    value={(form as Record<string, string>)[field] ?? ''} onChange={e => setForm(p => ({ ...p, [field]: e.target.value }))} />
                </div>
              ))}
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-600">
                  <input type="checkbox" className="toggle toggle-sm toggle-primary" checked={form.is_active ?? true}
                    onChange={e => setForm(p => ({ ...p, is_active: e.target.checked }))} /> Ativo
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-600">
                  <input type="checkbox" className="toggle toggle-sm" checked={form.is_simulated ?? false}
                    onChange={e => setForm(p => ({ ...p, is_simulated: e.target.checked }))} /> Simulado
                </label>
              </div>
            </div>
            <div className="flex gap-2 mt-4 pt-3 border-t">
              <button onClick={() => setShowForm(false)} className="flex-1 border border-gray-200 text-gray-600 text-sm font-medium rounded-xl py-2">Cancelar</button>
              <button onClick={handleSave} disabled={saving}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-medium rounded-xl py-2 flex items-center justify-center">
                {saving ? <span className="loading loading-spinner loading-xs" /> : 'Salvar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
