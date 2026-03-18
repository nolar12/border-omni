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

type FormMode = 'none' | 'create' | 'edit';

const EMPTY_FORM = { title: '', body: '', shortcut: '' };

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

  const [formMode, setFormMode] = useState<FormMode>('none');
  const [editingReply, setEditingReply] = useState<QuickReply | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    quickRepliesService
      .getAll()
      .then(setReplies)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      setSearch('');
      setActiveCategory(null);
      setFormMode('none');
      setEditingReply(null);
      setForm(EMPTY_FORM);
      setDeletingId(null);
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

  function openCreate() {
    setEditingReply(null);
    setForm(EMPTY_FORM);
    setFormMode('create');
  }

  function openEdit(r: QuickReply) {
    setEditingReply(r);
    setForm({
      title: quickRepliesService.getDisplayTitle(r),
      body: quickRepliesService.getDisplayBody(r),
      shortcut: r.shortcut || '',
    });
    setFormMode('edit');
    setDeletingId(null);
  }

  function cancelForm() {
    setFormMode('none');
    setEditingReply(null);
    setForm(EMPTY_FORM);
  }

  async function handleSaveForm() {
    if (!form.title.trim() || !form.body.trim()) return;
    setSaving(true);
    try {
      const payload = {
        title: form.title.trim(),
        body: form.body.trim(),
        shortcut: form.shortcut.trim(),
      };
      if (formMode === 'create') {
        const created = await quickRepliesService.create(payload);
        setReplies(prev => [created, ...prev]);
      } else if (formMode === 'edit' && editingReply) {
        const updated = await quickRepliesService.update(editingReply.id, payload);
        setReplies(prev => prev.map(r => (r.id === updated.id ? updated : r)));
      }
      cancelForm();
    } catch {
      // silently ignore — user can retry
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    setDeleting(true);
    try {
      await quickRepliesService.remove(id);
      setReplies(prev => prev.filter(r => r.id !== id));
      setDeletingId(null);
    } catch {
      // silently ignore
    } finally {
      setDeleting(false);
    }
  }

  const showForm = formMode !== 'none';

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 z-40 bg-black/30" onClick={onClose} />
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
            <h3 className="font-semibold text-base text-gray-800">Respostas Rápidas</h3>
          </div>
          <div className="flex items-center gap-1">
            {!showForm && (
              <button
                onClick={openCreate}
                title="Nova resposta rápida"
                className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-blue-50 text-blue-600 transition-colors"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                  <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </button>
            )}
            <button
              onClick={showForm ? cancelForm : onClose}
              className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-gray-100 text-gray-500 transition-colors text-lg"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Form (create / edit) */}
        {showForm && (
          <div className="px-4 py-3 flex flex-col gap-2 overflow-y-auto" style={{ maxHeight: '60vh' }}>
            <p className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-1">
              {formMode === 'create' ? 'Nova resposta rápida' : 'Editar resposta'}
            </p>

            <input
              type="text"
              placeholder="Título *"
              autoFocus
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              className="text-base border border-gray-200 rounded-lg px-3 py-2.5 outline-none focus:border-blue-400 transition-colors"
            />

            <textarea
              placeholder="Corpo da mensagem *"
              rows={4}
              value={form.body}
              onChange={e => setForm(f => ({ ...f, body: e.target.value }))}
              className="text-base border border-gray-200 rounded-lg px-3 py-2.5 outline-none focus:border-blue-400 transition-colors resize-none"
            />

            <input
              type="text"
              placeholder="Atalho (opcional, ex: disponibilidade)"
              value={form.shortcut}
              onChange={e => setForm(f => ({ ...f, shortcut: e.target.value }))}
              className="text-base border border-gray-200 rounded-lg px-3 py-2.5 outline-none focus:border-blue-400 transition-colors"
            />

            <div className="flex gap-2 pt-1">
              <button
                onClick={cancelForm}
                className="flex-1 py-2 rounded-lg text-sm text-gray-600 bg-gray-100 hover:bg-gray-200 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleSaveForm}
                disabled={saving || !form.title.trim() || !form.body.trim()}
                className="flex-1 py-2 rounded-lg text-sm text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 transition-colors flex items-center justify-center gap-1.5"
              >
                {saving
                  ? <span className="loading loading-spinner loading-xs" />
                  : 'Salvar'}
              </button>
            </div>
          </div>
        )}

        {/* Search + List (hidden when form is open) */}
        {!showForm && (
          <>
            <div className="px-3 py-2">
              <div className="relative">
                <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <circle cx="11" cy="11" r="8" /><path strokeLinecap="round" d="m21 21-4.35-4.35" />
                </svg>
                <input
                  type="search"
                  placeholder="Buscar por título ou texto…"
                  className="w-full text-base border border-gray-200 rounded-lg pl-8 pr-3 py-2 outline-none focus:border-blue-400 bg-gray-50"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  autoFocus={isOpen}
                />
              </div>
            </div>

            {!search && categories.length > 0 && (
              <div className="flex gap-1.5 px-3 pb-2 overflow-x-auto scrollbar-hide">
                <button
                  onClick={() => setActiveCategory(null)}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium flex-shrink-0 transition-colors ${
                    !activeCategory ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
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

            <div className="overflow-y-auto px-3 pb-6" style={{ maxHeight: '50vh' }}>
              {loading && (
                <p className="text-center text-gray-400 text-sm py-6">Carregando…</p>
              )}

              {!loading && filtered.length === 0 && (
                <div className="text-center py-8">
                  <p className="text-gray-400 text-sm mb-3">
                    {search ? 'Nenhum resultado para esta busca.' : 'Nenhuma resposta disponível.'}
                  </p>
                  {!search && (
                    <button
                      onClick={openCreate}
                      className="text-xs text-blue-600 font-medium hover:underline"
                    >
                      + Criar primeira resposta rápida
                    </button>
                  )}
                </div>
              )}

              {!loading && grouped.map(group => (
                <div key={group.label} className="mb-3">
                  {(!activeCategory || grouped.length > 1) && (
                    <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 px-1 pb-1 pt-2">
                      {group.label}
                    </p>
                  )}
                  {group.items.map(r => (
                    <ReplyCard
                      key={r.id}
                      reply={r}
                      isConfirmingDelete={deletingId === r.id}
                      deleting={deleting && deletingId === r.id}
                      onClick={() => handleSelect(r)}
                      onEdit={() => openEdit(r)}
                      onDeleteRequest={() => setDeletingId(r.id)}
                      onDeleteCancel={() => setDeletingId(null)}
                      onDeleteConfirm={() => handleDelete(r.id)}
                    />
                  ))}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  );
}

interface CardProps {
  reply: QuickReply;
  isConfirmingDelete: boolean;
  deleting: boolean;
  onClick: () => void;
  onEdit: () => void;
  onDeleteRequest: () => void;
  onDeleteCancel: () => void;
  onDeleteConfirm: () => void;
}

function ReplyCard({
  reply,
  isConfirmingDelete,
  deleting,
  onClick,
  onEdit,
  onDeleteRequest,
  onDeleteCancel,
  onDeleteConfirm,
}: CardProps) {
  const title = quickRepliesService.getDisplayTitle(reply);
  const body = quickRepliesService.getDisplayBody(reply);

  if (isConfirmingDelete) {
    return (
      <div className="w-full p-3 rounded-xl border border-red-100 bg-red-50 mb-1 flex items-center justify-between gap-2">
        <p className="text-sm text-red-700 font-medium flex-1">Excluir "{title}"?</p>
        <div className="flex gap-1.5">
          <button
            onClick={onDeleteCancel}
            className="text-sm px-2.5 py-1 rounded-lg bg-white border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Não
          </button>
          <button
            onClick={onDeleteConfirm}
            disabled={deleting}
            className="text-sm px-2.5 py-1 rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-40 transition-colors flex items-center gap-1"
          >
            {deleting ? <span className="loading loading-spinner loading-xs" /> : 'Sim, excluir'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="group relative w-full mb-1">
      <button
        onClick={onClick}
        className="w-full text-left p-3 rounded-xl hover:bg-blue-50 border border-transparent hover:border-blue-100 transition-all pr-16"
      >
        <div className="flex items-start gap-2 mb-1">
          <span className="text-sm font-semibold text-gray-800 group-hover:text-blue-700 leading-snug flex-1">
            {title}
          </span>
          {reply.is_personal && (
            <span className="flex-shrink-0 text-xs font-medium text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded">
              Pessoal
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500 line-clamp-2 leading-relaxed whitespace-pre-line">
          {body}
        </p>
      </button>

      {/* Edit / Delete actions — visible on hover */}
      <div className="absolute right-2 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center gap-1">
        <button
          onClick={e => { e.stopPropagation(); onEdit(); }}
          title="Editar"
          className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-100 transition-colors"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
        </button>
        <button
          onClick={e => { e.stopPropagation(); onDeleteRequest(); }}
          title="Excluir"
          className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6l-1 14H6L5 6" />
            <path d="M10 11v6M14 11v6" />
            <path d="M9 6V4h6v2" />
          </svg>
        </button>
      </div>
    </div>
  );
}
