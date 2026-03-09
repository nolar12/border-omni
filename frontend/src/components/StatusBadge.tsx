import type { LeadStatus } from '../types';

interface Props { status: LeadStatus; }

const MAP: Record<LeadStatus, { label: string; cls: string }> = {
  NEW:        { label: 'Novo',         cls: 'bg-slate-100 text-slate-500' },
  QUALIFYING: { label: 'Qualificando', cls: 'bg-blue-100 text-blue-600' },
  QUALIFIED:  { label: 'Qualificado',  cls: 'bg-emerald-100 text-emerald-600' },
  HANDOFF:    { label: 'Handoff',      cls: 'bg-amber-100 text-amber-600' },
  CLOSED:     { label: 'Fechado',      cls: 'bg-gray-100 text-gray-400' },
};

export default function StatusBadge({ status }: Props) {
  const { label, cls } = MAP[status] ?? MAP.NEW;
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}
