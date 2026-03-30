import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import SignatureCanvas from 'react-signature-canvas';
import { contractsService } from '../services/contracts';
import type { SaleContractPublic } from '../types';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(s: string | null) {
  if (!s) return '—';
  return new Date(s).toLocaleDateString('pt-BR');
}

// ─── Contract preview ─────────────────────────────────────────────────────────

function ContractPreview({ contract }: { contract: SaleContractPublic }) {
  const sexIcon = contract.puppy_sex === 'M' ? '♂' : '♀';
  const rows = [
    ['Raça', 'Border Collie'],
    ['Cor', contract.puppy_color || '—'],
    ['Sexo', `${sexIcon} ${contract.puppy_sex_display}`],
    ['Microchip', contract.puppy_microchip || '—'],
    ['Pedigree', 'Aguardando registro CBKC'],
    ['Pai', contract.puppy_father || '—'],
    ['Mãe', contract.puppy_mother || '—'],
    ['Nascimento', fmtDate(contract.puppy_birth_date)],
  ];
  const payment = [
    ['Valor total', contract.price_display],
    ['Reserva (30%) — via Pix', contract.deposit_display],
    ['Saldo na entrega (70%)', contract.balance_display],
  ];

  return (
    <div className="text-gray-800 text-sm leading-relaxed space-y-4">
      <div className="text-center border-b pb-4">
        <h2 className="text-base font-bold uppercase tracking-wide">
          Contrato de Compra e Venda de Cão Filhote
        </h2>
        <p className="text-gray-500 text-xs mt-1">Canil Border Collie Sul · Imbituba – SC · CBKC</p>
      </div>

      <div>
        <p className="font-semibold mb-1">Vendedor</p>
        <p>MARCELLO SOUZA, criador do Canil Border Collie Sul, inscrito na CBKC, Imbituba – SC.</p>
      </div>

      <div>
        <p className="font-semibold mb-1">Comprador</p>
        <p>
          <strong>{contract.buyer_name || '—'}</strong>,
          estado civil {contract.buyer_marital_status || '—'},
          CPF: {contract.buyer_cpf || '—'},
          endereço: {contract.buyer_address || '—'},
          CEP: {contract.buyer_cep || '—'},
          e-mail: {contract.buyer_email || '—'}.
        </p>
      </div>

      <div className="border-t pt-3">
        <p className="font-semibold uppercase text-xs text-gray-500 mb-2">Dados do Filhote</p>
        <table className="w-full text-sm border-collapse">
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k} className="border-b border-gray-100">
                <td className="py-1.5 pr-3 font-medium text-gray-600 w-1/3">{k}</td>
                <td className="py-1.5">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t pt-3">
        <p className="font-semibold uppercase text-xs text-gray-500 mb-2">Pagamento</p>
        <table className="w-full text-sm border-collapse">
          <tbody>
            {payment.map(([k, v]) => (
              <tr key={k} className="border-b border-gray-100">
                <td className="py-1.5 pr-3 font-medium text-gray-600 w-1/2">{k}</td>
                <td className="py-1.5 font-semibold text-green-700">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-gray-500 mt-2">
          Pix: marcello@nolar.com.br. A reserva constitui arras confirmatórias (art. 418 CC) e não é devolvida em caso de desistência do comprador.
        </p>
      </div>

      <div className="border-t pt-3 space-y-2 text-xs text-gray-600">
        {[
          'Cláusula 3ª: Entrega a partir dos 60 dias de idade.',
          'Cláusula 4ª/5ª: Transporte e despacho por conta do comprador.',
          'Cláusula 6ª: Filhote entregue vacinado e vermifugado, com cartão de vacina, certificado de microchip e pedigree.',
          'Cláusula 7ª: Cão adquirido exclusivamente para companhia. Reprodução expressamente vedada.',
          'Cláusula 8ª: Vendedor garante padrão da raça e ausência de sinais clínicos de doenças na entrega.',
          'Cláusula 9ª: Comprador deve manter vacinação em dia, alimentar com ração premium e submeter o filhote a avaliação veterinária em 72h após o recebimento.',
          'Cláusula 10ª: Proibida revenda. Vendedor detém direito de preferência.',
          'Cláusula 11ª: Vedados maus-tratos, abandono ou qualquer prática cruel.',
          'Cláusula 13ª: Em caso de doença congênita grave comprovada, poderá haver substituição do animal.',
          'Cláusula 16ª: Contrato intransferível, irrevogável e irretratável.',
          'Cláusula 20ª: Utilização para reprodução sujeita a multa de R$ 10.000,00.',
          'Foro: Comarca de Imbituba – SC.',
        ].map((t, i) => (
          <p key={i}>{t}</p>
        ))}
      </div>
    </div>
  );
}

// ─── Step 1 — Buyer form ──────────────────────────────────────────────────────

interface BuyerFormProps {
  contract: SaleContractPublic;
  onSubmitted: (c: SaleContractPublic) => void;
}

function BuyerForm({ contract, onSubmitted }: BuyerFormProps) {
  const [form, setForm] = useState({
    buyer_name: contract.buyer_name || '',
    buyer_cpf: contract.buyer_cpf || '',
    buyer_marital_status: contract.buyer_marital_status || '',
    buyer_address: contract.buyer_address || '',
    buyer_cep: contract.buyer_cep || '',
    buyer_email: contract.buyer_email || '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  function set(field: string, value: string) {
    setForm(f => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.buyer_name.trim() || !form.buyer_cpf.trim()) {
      setError('Nome e CPF são obrigatórios.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const updated = await contractsService.fillPublic(contract.token, form);
      onSubmitted(updated);
    } catch {
      setError('Erro ao enviar. Tente novamente.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
        <strong>Olá!</strong> Preencha seus dados abaixo para confirmar o contrato de compra do seu filhote Border Collie.
        Após o envio, o vendedor irá revisar e aprovar o contrato para que você possa assinar.
      </div>

      {/* Preview do filhote */}
      <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
        <p className="text-xs font-semibold uppercase text-gray-500 mb-2">Filhote reservado</p>
        <div className="flex gap-4 flex-wrap text-sm">
          <span><span className="text-gray-500">Raça:</span> <strong>Border Collie</strong></span>
          <span>
            <span className="text-gray-500">Sexo:</span>{' '}
            <strong>{contract.puppy_sex === 'M' ? '♂ Macho' : '♀ Fêmea'}</strong>
          </span>
          <span><span className="text-gray-500">Cor:</span> <strong>{contract.puppy_color}</strong></span>
          <span><span className="text-gray-500">Valor:</span> <strong className="text-green-700">{contract.price_display}</strong></span>
          <span><span className="text-gray-500">Reserva (30%):</span> <strong className="text-orange-600">{contract.deposit_display}</strong></span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="sm:col-span-2">
          <label className="text-sm font-medium text-gray-700 block mb-1">Nome completo *</label>
          <input
            required
            type="text"
            value={form.buyer_name}
            onChange={e => set('buyer_name', e.target.value)}
            placeholder="Seu nome completo"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">CPF *</label>
          <input
            required
            type="text"
            value={form.buyer_cpf}
            onChange={e => set('buyer_cpf', e.target.value)}
            placeholder="000.000.000-00"
            maxLength={14}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">Estado civil</label>
          <select
            value={form.buyer_marital_status}
            onChange={e => set('buyer_marital_status', e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 bg-white"
          >
            <option value="">Selecione...</option>
            <option value="Solteiro(a)">Solteiro(a)</option>
            <option value="Casado(a)">Casado(a)</option>
            <option value="Divorciado(a)">Divorciado(a)</option>
            <option value="Viúvo(a)">Viúvo(a)</option>
            <option value="União estável">União estável</option>
          </select>
        </div>

        <div className="sm:col-span-2">
          <label className="text-sm font-medium text-gray-700 block mb-1">Endereço completo</label>
          <input
            type="text"
            value={form.buyer_address}
            onChange={e => set('buyer_address', e.target.value)}
            placeholder="Rua, número, bairro, cidade – estado"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">CEP</label>
          <input
            type="text"
            value={form.buyer_cep}
            onChange={e => set('buyer_cep', e.target.value)}
            placeholder="00000-000"
            maxLength={9}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">E-mail</label>
          <input
            type="email"
            value={form.buyer_email}
            onChange={e => set('buyer_email', e.target.value)}
            placeholder="seu@email.com"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <button
        type="submit"
        disabled={saving}
        className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold rounded-lg text-sm"
      >
        {saving ? 'Enviando...' : 'Confirmar dados e enviar contrato'}
      </button>
    </form>
  );
}

// ─── Step 2 — Signature ───────────────────────────────────────────────────────

interface SignatureStepProps {
  contract: SaleContractPublic;
  onSigned: (c: SaleContractPublic) => void;
}

function SignatureStep({ contract, onSigned }: SignatureStepProps) {
  const sigRef = useRef<SignatureCanvas>(null);
  const [mode, setMode] = useState<'canvas' | 'govbr'>('canvas');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(false);

  async function submitCanvas() {
    if (!sigRef.current || sigRef.current.isEmpty()) {
      setError('Por favor, assine no campo acima antes de continuar.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const imgData = sigRef.current.toDataURL('image/png');
      const updated = await contractsService.signPublic(contract.token, {
        signature_data: imgData,
        signature_type: 'canvas',
      });
      onSigned(updated);
    } catch {
      setError('Erro ao salvar assinatura. Tente novamente.');
    } finally {
      setSaving(false);
    }
  }

  async function confirmGovBr() {
    setSaving(true);
    setError('');
    try {
      const updated = await contractsService.signPublic(contract.token, {
        signature_data: 'govbr_confirmed',
        signature_type: 'govbr',
      });
      onSigned(updated);
    } catch {
      setError('Erro ao confirmar. Tente novamente.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-800">
        <strong>Contrato aprovado!</strong> Seu contrato foi revisado e aprovado pelo vendedor.
        Agora escolha como deseja assinar.
      </div>

      {/* Contract preview toggle */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <button
          type="button"
          onClick={() => setExpanded(e => !e)}
          className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 text-sm font-medium text-gray-700"
        >
          <span>Ver contrato completo</span>
          <svg
            className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`}
            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
          >
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
        {expanded && (
          <div className="p-4 max-h-96 overflow-y-auto border-t border-gray-200">
            <ContractPreview contract={contract} />
          </div>
        )}
      </div>

      {/* Signature mode tabs */}
      <div className="flex rounded-lg overflow-hidden border border-gray-200">
        <button
          type="button"
          onClick={() => setMode('canvas')}
          className={`flex-1 py-2.5 text-sm font-medium border-r border-gray-200 ${
            mode === 'canvas' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'
          }`}
        >
          Assinar aqui
        </button>
        <button
          type="button"
          onClick={() => setMode('govbr')}
          className={`flex-1 py-2.5 text-sm font-medium ${
            mode === 'govbr' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'
          }`}
        >
          Assinar no Gov.br
        </button>
      </div>

      {mode === 'canvas' ? (
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-2">
            Assine com o dedo ou mouse no campo abaixo:
          </label>
          <div className="border-2 border-dashed border-gray-300 rounded-lg overflow-hidden bg-white">
            <SignatureCanvas
              ref={sigRef}
              penColor="#1a1a2e"
              canvasProps={{
                className: 'w-full',
                style: { height: 160, touchAction: 'none' },
              }}
            />
          </div>
          <button
            type="button"
            onClick={() => sigRef.current?.clear()}
            className="text-xs text-gray-500 hover:text-gray-700 mt-1.5 underline"
          >
            Limpar assinatura
          </button>
          {error && <p className="text-red-600 text-sm mt-2">{error}</p>}
          <button
            type="button"
            onClick={submitCanvas}
            disabled={saving}
            className="w-full mt-3 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold rounded-lg text-sm"
          >
            {saving ? 'Salvando assinatura...' : 'Confirmar assinatura'}
          </button>
        </div>
      ) : (
        <div className="space-y-3 text-sm">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-blue-800 space-y-2">
            <p>
              <strong>Como assinar pelo Gov.br:</strong>
            </p>
            <ol className="list-decimal pl-4 space-y-1">
              <li>Acesse <a href="https://assinador.iti.br" target="_blank" rel="noreferrer" className="underline font-medium">assinador.iti.br</a></li>
              <li>Faça login com sua conta Gov.br</li>
              <li>Clique em "Assinar Documento" e faça upload do PDF do contrato</li>
              <li>Conclua a assinatura digital</li>
              <li>Envie o PDF assinado de volta para o vendedor</li>
            </ol>
          </div>
          <a
            href={`/api/contracts/public/${contract.token}/`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-center gap-2 w-full py-2.5 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 text-sm font-medium"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            Baixar PDF do contrato
          </a>
          {error && <p className="text-red-600 text-sm">{error}</p>}
          <button
            type="button"
            onClick={confirmGovBr}
            disabled={saving}
            className="w-full py-3 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-semibold rounded-lg text-sm"
          >
            {saving ? 'Confirmando...' : 'Confirmar que assinei no Gov.br'}
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Success screen ───────────────────────────────────────────────────────────

function SuccessScreen() {
  return (
    <div className="text-center py-10 space-y-4">
      <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto">
        <svg className="w-8 h-8 text-green-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
          <polyline points="20 6 9 17 4 12"/>
        </svg>
      </div>
      <h2 className="text-xl font-bold text-gray-800">Contrato assinado!</h2>
      <p className="text-gray-600 text-sm max-w-xs mx-auto">
        Sua assinatura foi registrada com sucesso. Em breve você receberá o contrato finalizado via WhatsApp.
      </p>
    </div>
  );
}

// ─── Waiting screen ───────────────────────────────────────────────────────────

function WaitingScreen({ status }: { status: string }) {
  const messages: Record<string, { icon: string; title: string; desc: string }> = {
    buyer_filled: {
      icon: '⏳',
      title: 'Aguardando aprovação',
      desc: 'Seus dados foram enviados! Estamos revisando o contrato. Em breve você receberá um link via WhatsApp para assinar.',
    },
  };
  const info = messages[status] ?? {
    icon: 'ℹ️',
    title: `Status: ${status}`,
    desc: 'Aguardando próximos passos.',
  };
  return (
    <div className="text-center py-10 space-y-3">
      <div className="text-5xl">{info.icon}</div>
      <h2 className="text-xl font-bold text-gray-800">{info.title}</h2>
      <p className="text-gray-600 text-sm max-w-xs mx-auto">{info.desc}</p>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function ContractPublicPage() {
  const { token } = useParams<{ token: string }>();
  const [contract, setContract] = useState<SaleContractPublic | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!token) { setNotFound(true); setLoading(false); return; }
    contractsService
      .getPublic(token)
      .then(setContract)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (notFound || !contract) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center p-8">
          <div className="text-5xl mb-4">🔍</div>
          <h2 className="text-xl font-bold text-gray-800">Contrato não encontrado</h2>
          <p className="text-gray-600 text-sm mt-2">
            O link pode estar incorreto ou o contrato ainda não foi disponibilizado.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-lg mx-auto px-4 py-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-base">B</span>
          </div>
          <div>
            <p className="font-bold text-gray-900 text-sm leading-tight">Canil Border Collie Sul</p>
            <p className="text-gray-500 text-xs">Contrato de Compra e Venda</p>
          </div>
        </div>
      </header>

      {/* Progress */}
      <div className="bg-white border-b border-gray-100">
        <div className="max-w-lg mx-auto px-4 py-3">
          <div className="flex items-center gap-2 text-xs">
            {[
              { key: 'sent', label: '1. Seus dados' },
              { key: 'buyer_filled', label: '2. Revisão' },
              { key: 'approved', label: '3. Assinatura' },
              { key: 'signed', label: '4. Concluído' },
            ].map((step, i, arr) => {
              const order = ['sent', 'buyer_filled', 'approved', 'signed'];
              const currentIdx = order.indexOf(contract.status);
              const stepIdx = order.indexOf(step.key);
              const done = stepIdx < currentIdx;
              const active = stepIdx === currentIdx;
              return (
                <div key={step.key} className="flex items-center gap-2 flex-1">
                  <div className={`flex items-center gap-1.5 ${active ? 'text-blue-600 font-semibold' : done ? 'text-green-600' : 'text-gray-400'}`}>
                    <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs flex-shrink-0 border
                      ${active ? 'border-blue-600 bg-blue-600 text-white' : done ? 'border-green-500 bg-green-500 text-white' : 'border-gray-300 bg-white text-gray-400'}`}>
                      {done ? '✓' : i + 1}
                    </span>
                    <span className="hidden sm:inline">{step.label}</span>
                  </div>
                  {i < arr.length - 1 && <div className={`flex-1 h-px ${done ? 'bg-green-400' : 'bg-gray-200'}`} />}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main content */}
      <main className="max-w-lg mx-auto px-4 py-6">
        {contract.status === 'sent' && (
          <BuyerForm contract={contract} onSubmitted={setContract} />
        )}
        {contract.status === 'buyer_filled' && (
          <WaitingScreen status={contract.status} />
        )}
        {contract.status === 'approved' && (
          <SignatureStep contract={contract} onSigned={setContract} />
        )}
        {contract.status === 'signed' && (
          <SuccessScreen />
        )}
      </main>

      <footer className="text-center text-xs text-gray-400 py-6">
        Contrato #{contract.id} · Gerado pelo sistema Border Omni
      </footer>
    </div>
  );
}
