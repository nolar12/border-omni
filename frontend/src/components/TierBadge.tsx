import type { Tier } from '../types';

interface Props { tier: Tier | null | undefined; size?: 'sm' | 'md'; }

const MAP: Record<Tier, string> = {
  A: 'bg-emerald-100 text-emerald-700',
  B: 'bg-amber-100 text-amber-700',
  C: 'bg-red-100 text-red-700',
};

export default function TierBadge({ tier, size = 'sm' }: Props) {
  if (!tier) return <span className="text-gray-300 text-sm">—</span>;
  const sz = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-2.5 py-1';
  return (
    <span className={`inline-flex items-center font-bold rounded-md ${MAP[tier]} ${sz}`}>
      {tier}
    </span>
  );
}
