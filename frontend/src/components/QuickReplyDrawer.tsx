import { useState, useEffect } from 'react';
import type { QuickReply } from '../types';
import { quickRepliesService } from '../services/quickReplies';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (text: string) => void;
  userName?: string;
  leadName?: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  GREETING: 'Saudação', PRICING: 'Preço', AVAILABILITY: 'Disponibilidade',
  SCHEDULING: 'Agendamento', INFO: 'Informações', CLOSING: 'Encerramento',
};

export default function QuickReplyDrawer({ isOpen, onClose, onSelect, userName = '', leadName = '' }: Props) {
  const [replies, setReplies] = useState<QuickReply[]>([]);
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  useEffect(() => {
    quickRepliesService.getAll().then(setReplies).catch(() => {});
  }, []);

  const filtered = replies.filter(r => {
    const matchSearch = !search || r.shortcut.includes(search) || r.text.toLowerCase().includes(search.toLowerCase());
    const matchCat = !activeCategory || r.category === activeCategory;
    return matchSearch && matchCat;
  });

  const categories = [...new Set(replies.map(r => r.category))];

  function handleSelect(r: QuickReply) {
    const text = quickRepliesService.resolveVariables(r.text, { user_name: userName, lead_name: leadName });
    onSelect(text);
    onClose();
  }

  return (
    <>
      {isOpen && <div className="fixed inset-0 z-40 bg-black/30" onClick={onClose} />}
      <div className={`fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-2xl shadow-2xl transition-transform duration-300 ${isOpen ? 'translate-y-0' : 'translate-y-full'}`}
        style={{ maxHeight: '65vh' }}>
        <div className="flex items-center justify-between px-4 pt-3 pb-2 border-b">
          <h3 className="font-semibold text-sm text-gray-800">Respostas Rápidas</h3>
          <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-gray-100 text-gray-400">✕</button>
        </div>
        <div className="px-3 py-2">
          <input type="search" placeholder="Buscar /shortcut ou texto..."
            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-blue-400 bg-gray-50"
            value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        {!search && (
          <div className="flex gap-2 px-3 pb-2 overflow-x-auto">
            <button onClick={() => setActiveCategory(null)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium flex-shrink-0 transition-colors ${!activeCategory ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}>
              Todos
            </button>
            {categories.map(cat => (
              <button key={cat} onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium flex-shrink-0 transition-colors ${activeCategory === cat ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}>
                {CATEGORY_LABELS[cat]}
              </button>
            ))}
          </div>
        )}
        <div className="overflow-y-auto px-3 pb-6" style={{ maxHeight: '40vh' }}>
          {filtered.length === 0 && <p className="text-center text-gray-400 text-sm py-6">Nenhum template</p>}
          {filtered.map(r => (
            <button key={r.id} onClick={() => handleSelect(r)}
              className="w-full text-left p-2.5 rounded-xl hover:bg-gray-50 border border-transparent hover:border-gray-100 transition-all mb-1">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-xs font-mono font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">{r.shortcut}</span>
                <span className="text-xs text-gray-400">{CATEGORY_LABELS[r.category]}</span>
              </div>
              <p className="text-xs text-gray-600 line-clamp-2">{r.text}</p>
            </button>
          ))}
        </div>
      </div>
    </>
  );
}
