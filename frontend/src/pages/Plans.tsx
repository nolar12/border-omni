import { useEffect, useState } from 'react';
import { plansService } from '../services/plans';
import type { Plan, Subscription } from '../types';

export default function Plans() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState('');

  useEffect(() => {
    Promise.all([plansService.getPlans(), plansService.getSubscription().catch(() => null)])
      .then(([p, s]) => { setPlans(p); setSubscription(s); }).finally(() => setLoading(false));
  }, []);

  async function handleUpgrade(planName: string) {
    setUpgrading(planName);
    try { setSubscription(await plansService.upgrade(planName)); } finally { setUpgrading(''); }
  }

  const ICONS: Record<string, string> = { free: '🆓', pro: '⚡', enterprise: '🏢' };
  const HIGHLIGHT: Record<string, string> = { free: '', pro: 'ring-2 ring-blue-400', enterprise: '' };
  const currentPlan = subscription?.plan?.name;

  function fmt(v: number) { return v === -1 ? 'Ilimitado' : String(v); }

  if (loading) return <div className="flex justify-center py-12"><span className="loading loading-spinner loading-lg text-primary" /></div>;

  return (
    <div className="max-w-3xl space-y-6">
      {subscription && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 flex items-center gap-4">
          <div>
            <p className="text-xs text-gray-400">Plano atual</p>
            <p className="text-lg font-bold text-gray-800 capitalize">{ICONS[currentPlan ?? 'free']} {currentPlan}</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              subscription.status === 'active' ? 'bg-emerald-100 text-emerald-700' :
              subscription.status === 'trial' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
              {subscription.status}
            </span>
            {subscription.trial_ends_at && (
              <span className="text-xs text-gray-400">
                Trial até {new Date(subscription.trial_ends_at).toLocaleDateString('pt-BR')}
              </span>
            )}
          </div>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {plans.map(plan => {
          const isCurrent = plan.name === currentPlan;
          return (
            <div key={plan.id} className={`bg-white rounded-2xl shadow-sm border-2 p-5 ${isCurrent ? 'border-blue-400' : 'border-gray-100'} ${HIGHLIGHT[plan.name]}`}>
              <div className="text-2xl mb-2">{ICONS[plan.name]}</div>
              <h3 className="text-base font-bold text-gray-800 capitalize mb-1">{plan.name}</h3>
              <p className="text-2xl font-bold text-blue-600 mb-4">
                {plan.price_monthly === 0 ? 'Grátis' : `R$ ${Number(plan.price_monthly).toFixed(0)}/mês`}
              </p>
              <ul className="space-y-1.5 text-sm text-gray-500 mb-5">
                <li>✓ {fmt(plan.max_leads)} leads</li>
                <li>✓ {fmt(plan.max_agents)} atendente{plan.max_agents !== 1 ? 's' : ''}</li>
                <li>✓ {fmt(plan.max_channels)} canal{plan.max_channels !== 1 ? 'is' : ''}</li>
                <li>✓ QualifierEngine IA</li>
                {plan.name !== 'free' && <li>✓ Human Handoff</li>}
                {plan.name === 'enterprise' && <li>✓ Suporte dedicado</li>}
              </ul>
              {isCurrent ? (
                <button className="w-full border border-gray-200 text-gray-400 text-sm font-medium rounded-xl py-2" disabled>Plano Atual</button>
              ) : (
                <button onClick={() => handleUpgrade(plan.name)} disabled={!!upgrading}
                  className={`w-full text-sm font-semibold rounded-xl py-2 transition-colors flex items-center justify-center ${
                    plan.name === 'pro' ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'border border-blue-200 text-blue-600 hover:bg-blue-50'}`}>
                  {upgrading === plan.name ? <span className="loading loading-spinner loading-xs" /> : 'Selecionar'}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
