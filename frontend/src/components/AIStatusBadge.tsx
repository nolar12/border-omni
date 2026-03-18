import type { AssignedUser } from '../types';

interface Props {
  isAiActive: boolean;
  assignedTo?: AssignedUser | null;
}

export default function AIStatusBadge({ isAiActive, assignedTo }: Props) {
  if (isAiActive) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700 whitespace-nowrap">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
        IA
      </span>
    );
  }
  const name = assignedTo
    ? `${assignedTo.first_name} ${assignedTo.last_name}`.trim() || assignedTo.email
    : 'Humano';
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700">
      <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
      {name}
    </span>
  );
}
