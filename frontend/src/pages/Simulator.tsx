import { useState } from 'react';
import type { FormEvent } from 'react';
import { simulatorService } from '../services/simulator';

type SimResult = Awaited<ReturnType<typeof simulatorService.send>>;

export default function Simulator() {
  const [phone, setPhone] = useState('+5551999888777');
  const [text, setText] = useState('');
  const [orgKey, setOrgKey] = useState('2d569ffe7e3249588e550c1312fa3154');
  const [result, setResult] = useState<SimResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await simulatorService.send(phone, text, orgKey);
      setResult(data);
      setText('');
    } catch (err: unknown) {
      const e2 = err as { response?: { data?: { detail?: string } } };
      setError(e2?.response?.data?.detail ?? 'Erro ao enviar mensagem.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-lg mx-auto space-y-4">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
        <h2 className="font-semibold text-gray-800 mb-1">Simulador de Webhook</h2>
        <p className="text-xs text-gray-400 mb-4">Simule mensagens de leads para testar o fluxo da IA.</p>
        <form onSubmit={handleSend} className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">API Key</label>
            <input type="text" className="w-full border border-gray-200 rounded-xl px-3 py-2 text-xs font-mono outline-none focus:border-blue-400"
              value={orgKey} onChange={e => setOrgKey(e.target.value)} required />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Telefone</label>
            <input type="text" className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-900 bg-white outline-none focus:border-blue-400"
              value={phone} onChange={e => setPhone(e.target.value)} required />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Mensagem</label>
            <textarea rows={3} className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-900 bg-white outline-none focus:border-blue-400 resize-none"
              placeholder="oi, quero saber sobre os filhotes" value={text} onChange={e => setText(e.target.value)} required />
          </div>
          {error && <div className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</div>}
          <button type="submit" disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold rounded-xl py-2.5 text-sm transition-colors flex items-center justify-center gap-2">
            {loading ? <span className="loading loading-spinner loading-sm" /> : '⚡ Enviar'}
          </button>
        </form>
      </div>

      {result && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <h3 className="font-semibold text-gray-800 mb-3 text-sm">Resposta</h3>
          {result.replies.length > 0 ? (
            <div className="space-y-2 mb-4">
              {result.replies.map((r, i) => (
                <div key={i} className="bg-blue-50 rounded-xl p-3 text-sm text-gray-700 whitespace-pre-wrap">{r}</div>
              ))}
            </div>
          ) : (
            <div className="bg-amber-50 rounded-xl p-3 text-sm text-amber-700 mb-4">
              Lead em atendimento humano — sem resposta automática.
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            {[['Lead ID', `#${result.lead.id}`], ['Tier', result.lead.tier ?? '—'], ['Score', String(result.lead.score)],
              ['Status', result.lead.status], ['Estado IA', result.lead.conversation_state], ['IA Ativa', result.lead.is_ai_active ? 'Sim' : 'Não']
            ].map(([k, v]) => (
              <div key={k} className="bg-gray-50 rounded-lg p-2">
                <p className="text-xs text-gray-400">{k}</p>
                <p className="text-sm font-semibold text-gray-700">{v}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
