type Classification = 'HOT_LEAD' | 'WARM_LEAD' | 'COLD_LEAD';

interface Props { classification: Classification | string | null | undefined; size?: 'sm' | 'md'; }

const MAP: Record<Classification, { label: string; classes: string; icon: string }> = {
  HOT_LEAD:  { label: 'Hot',  classes: 'bg-red-100 text-red-700',    icon: '🔥' },
  WARM_LEAD: { label: 'Warm', classes: 'bg-amber-100 text-amber-700', icon: '🟡' },
  COLD_LEAD: { label: 'Cold', classes: 'bg-blue-100 text-blue-600',   icon: '❄️' },
};

export default function ClassificationBadge({ classification, size = 'sm' }: Props) {
  if (!classification || !(classification in MAP)) return null;
  const { label, classes, icon } = MAP[classification as Classification];
  const sz = size === 'sm' ? 'text-xs px-1.5 py-0.5' : 'text-sm px-2.5 py-1';
  return (
    <span className={`inline-flex items-center gap-1 font-semibold rounded-md ${classes} ${sz}`}>
      <span>{icon}</span>
      {label}
    </span>
  );
}
