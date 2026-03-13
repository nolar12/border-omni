import { useState, useEffect, useMemo } from 'react';
import type { QuickReply } from '../types';
import { quickRepliesService } from '../services/quickReplies';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (text: string) => void;
  userName?: string;
  leadName?: string;
}

export default function QuickReplyDrawer({
  isOpen,
  onClose,
  onSelect,
  userName = '',
  leadName = '',
}: Props) {
  const [replies, setReplies] = useState<QuickReply[]>([]);
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    quickRepliesService
      .getAll()
      .then(setReplies)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [isOpen]);

  // Reset filters on close
  useEffect(() => {
    if (!isOpen) {
      setSearch('');
      setActiveCategory(null);
    }
  }, [isOpen]);

  const categories = useMemo(() => {
    const seen = new Map<string, string>();
    replies.forEach(r => {
      const key = r.category_ref != null ? String(r.category_ref) : r.category;
      const label = r.category_name || r.category;
      if (key && label && !seen.has(key)) seen.set(key, label);
    });
    return Array.from(seen.entries()).map(([key, label]) => ({ key, label }));
  }, [replies]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return replies.filter(r => {
      const title = quickRepliesService.getDisplayTitle(r).toLowerCase();
      const body = quickRepliesService.getDisplayBody(r).toLowerCase();
      const matchSearch = !q || title.includes(q) || body.includes(q) || r.shortcut.toLowerCase().includes(q);
      const catKey = r.category_ref != null ? String(r.category_ref) : r.category;
      const matchCat = !activeCategory || catKey === activeCategory;
      return matchSearch && matchCat;
    });
  }, [replies, search, activeCategory]);

  // Group filtered replies by category for display
  const grouped = useMemo(() => {
    const map = new Map<string, { label: string; items: QuickReply[] }>();
    filtered.forEach(r => {
      const key = r.category_ref != null ? String(r.category_ref) : r.category;
      const label = r.category_name || r.category || 'Geral';
      if (!map.has(key)) map.set(key, { label, items: [] });
      map.get(key)!.items.push(r);
    });
    return Array.from(map.values());
  }, [filtered]);

  function handleSelect(r: QuickReply) {
    const raw = quickRepliesService.getDisplayBody(r);
    const resolved = quickRepliesService.resolveVariables(raw, {
      user_name: userName,
      lead_name: leadName,
    });
    onSelect(resolved);
    onClose();
  }

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30"
          onClick={onClose}
        />
      )}

      <div
        className={`fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-2xl shadow-2xl transition-transform duration-300 ${
          isOpen ? 'translate-y-0' : 'translate-y-full'
        }`}
        style={{ maxHeight: '70vh' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 pt-3 pb-2 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 8h10M7 12h6m-6 4h10M5 4h14a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2z" />
            </svg>
            <h3 className="font-semibold text-sm text-gray-800">Respostas Rápidas</h3>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-gray-100 text-gray-400 transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Search */}
        <div className="px-3 py-2">
          <div className="relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <circle cx="11" cy="11" r="8" /><path strokeLinecap="round" d="m21 21-4.35-4.35" />
            </svg>
            <input
              type="search"
              placeholder="Buscar por título ou texto…"
              className="w-full text-sm border border-gray-200 rounded-lg pl-8 pr-3 py-1.5 outline-none focus:border-blue-400 bg-gray-50"
              value={search}
              onChange={e => setSearch(e.target.value)}
              autoFocus={isOpen}
            />
          </div>
        </div>

        {/* Category pills */}
        {!search && categories.length > 0 && (
          <div className="flex gap-1.5 px-3 pb-2 overflow-x-auto scrollbar-hide">
            <button
              onClick={() => setActiveCategory(null)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium flex-shrink-0 transition-colors ${
                !activeCategory
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              Todas
            </button>
            {categories.map(cat => (
              <button
                key={cat.key}
                onClick={() => setActiveCategory(activeCategory === cat.key ? null : cat.key)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium flex-shrink-0 transition-colors whitespace-nowrap ${
                  activeCategory === cat.key
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>
        )}

        {/* Reply list */}
        <div className="overflow-y-auto px-3 pb-6" style={{ maxHeight: '50vh' }}>
          {loading && (
            <p className="text-center text-gray-400 text-sm py-6">Carregando…</p>
          )}

          {!loading && filtered.length === 0 && (
            <p className="text-center text-gray-400 text-sm py-6">
              {search ? 'Nenhum resultado para esta busca.' : 'Nenhuma resposta disponível.'}
            </p>
          )}

          {!loading && grouped.map(group => (
            <div key={group.label} className="mb-3">
              {/* Show category header only when not filtering by a single category */}
              {(!activeCategory || grouped.length > 1) && (
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 px-1 pb-1 pt-2">
                  {group.label}
                </p>
              )}
              {group.items.map(r => (
                <ReplyCard
                  key={r.id}
                  reply={r}
                  onClick={() => handleSelect(r)}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function ReplyCard({ reply, onClick }: { reply: QuickReply; onClick: () => void }) {
  const title = quickRepliesService.getDisplayTitle(reply);
  const body = quickRepliesService.getDisplayBody(reply);

  return (
    <button
      onClick={onClick}
      className="w-full text-left p-3 rounded-xl hover:bg-blue-50 border border-transparent hover:border-blue-100 transition-all mb-1 group"
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <span className="text-xs font-semibold text-gray-800 group-hover:text-blue-700 leading-snug">
          {title}
        </span>
        {reply.is_personal && (
          <span className="flex-shrink-0 text-[10px] font-medium text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded">
            Pessoal
          </span>
        )}
      </div>
      <p className="text-xs text-gray-500 line-clamp-2 leading-relaxed whitespace-pre-line">
        {body}
      </p>
    </button>
  );
}
