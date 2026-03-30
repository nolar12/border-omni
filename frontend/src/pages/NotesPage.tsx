import { useState, useEffect, useRef } from 'react';
import { notesService, type NotePayload } from '../services/notes';
import type { GenericNote, NoteColor } from '../types';

// ─── Color helpers ────────────────────────────────────────────────────────────

const COLOR_OPTIONS: { value: NoteColor; label: string; bg: string; border: string; dot: string }[] = [
  { value: 'default', label: 'Padrão',   bg: 'bg-white',        border: 'border-slate-200', dot: 'bg-slate-400' },
  { value: 'yellow',  label: 'Amarelo',  bg: 'bg-yellow-50',    border: 'border-yellow-300', dot: 'bg-yellow-400' },
  { value: 'green',   label: 'Verde',    bg: 'bg-emerald-50',   border: 'border-emerald-300', dot: 'bg-emerald-400' },
  { value: 'blue',    label: 'Azul',     bg: 'bg-blue-50',      border: 'border-blue-300', dot: 'bg-blue-400' },
  { value: 'pink',    label: 'Rosa',     bg: 'bg-pink-50',      border: 'border-pink-300', dot: 'bg-pink-400' },
  { value: 'purple',  label: 'Roxo',     bg: 'bg-purple-50',    border: 'border-purple-300', dot: 'bg-purple-400' },
];

function colorStyle(color: NoteColor) {
  return COLOR_OPTIONS.find(c => c.value === color) ?? COLOR_OPTIONS[0];
}

// ─── Subcomponents ────────────────────────────────────────────────────────────

function ColorPicker({
  value,
  onChange,
}: {
  value: NoteColor;
  onChange: (c: NoteColor) => void;
}) {
  return (
    <div className="flex items-center gap-1.5">
      {COLOR_OPTIONS.map(c => (
        <button
          key={c.value}
          type="button"
          title={c.label}
          onClick={() => onChange(c.value)}
          className={`w-6 h-6 rounded-full border-2 transition-transform ${c.dot} ${
            value === c.value ? 'border-slate-700 scale-110' : 'border-transparent hover:scale-105'
          }`}
        />
      ))}
    </div>
  );
}

interface NoteCardProps {
  note: GenericNote;
  onEdit: (note: GenericNote) => void;
  onDelete: (id: number) => void;
  onTogglePin: (id: number) => void;
}

function NoteCard({ note, onEdit, onDelete, onTogglePin }: NoteCardProps) {
  const style = colorStyle(note.color);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen]);

  const fmtDate = (iso: string) =>
    new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' });

  return (
    <div
      className={`relative flex flex-col rounded-xl border shadow-sm hover:shadow-md transition-shadow p-4 gap-2 ${style.bg} ${style.border}`}
    >
      {/* Pin indicator */}
      {note.is_pinned && (
        <div className="absolute top-2 right-10">
          <svg className="w-4 h-4 text-amber-500" viewBox="0 0 24 24" fill="currentColor">
            <path d="M16 4v6l2 4H6l2-4V4h8zm-4 16a2 2 0 0 0 2-2h-4a2 2 0 0 0 2 2zm0-18H8v1h8V2z"/>
          </svg>
        </div>
      )}

      {/* Menu */}
      <div className="absolute top-2 right-2" ref={menuRef}>
        <button
          onClick={() => setMenuOpen(o => !o)}
          className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-700 hover:bg-black/5 transition-colors"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
            <circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/>
          </svg>
        </button>
        {menuOpen && (
          <div className="absolute right-0 top-8 bg-white border border-slate-200 rounded-xl shadow-lg z-10 py-1 min-w-[160px]">
            <button
              onClick={() => { onEdit(note); setMenuOpen(false); }}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
              Editar
            </button>
            <button
              onClick={() => { onTogglePin(note.id); setMenuOpen(false); }}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
                <line x1="12" y1="17" x2="12" y2="22"/>
                <path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V17z"/>
              </svg>
              {note.is_pinned ? 'Desafixar' : 'Fixar'}
            </button>
            <div className="border-t border-slate-100 my-1" />
            <button
              onClick={() => { onDelete(note.id); setMenuOpen(false); }}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                <path d="M10 11v6M14 11v6"/>
                <path d="M9 6V4h6v2"/>
              </svg>
              Excluir
            </button>
          </div>
        )}
      </div>

      {/* Content */}
      <h3 className="font-semibold text-slate-800 text-sm leading-snug pr-8 line-clamp-2">
        {note.title}
      </h3>
      {note.content && (
        <p className="text-slate-600 text-sm leading-relaxed line-clamp-4 whitespace-pre-wrap">
          {note.content}
        </p>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-auto pt-2 border-t border-black/5">
        <span className="text-xs text-slate-400">{note.author_name}</span>
        <span className="text-xs text-slate-400">{fmtDate(note.updated_at)}</span>
      </div>
    </div>
  );
}

// ─── Modal ────────────────────────────────────────────────────────────────────

interface ModalProps {
  initial?: GenericNote | null;
  onSave: (payload: NotePayload) => Promise<void>;
  onClose: () => void;
  saving: boolean;
}

function NoteModal({ initial, onSave, onClose, saving }: ModalProps) {
  const [title,   setTitle]   = useState(initial?.title   ?? '');
  const [content, setContent] = useState(initial?.content ?? '');
  const [color,   setColor]   = useState<NoteColor>(initial?.color ?? 'default');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    await onSave({ title: title.trim(), content: content.trim(), color });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="font-semibold text-slate-800 text-base">
            {initial ? 'Editar nota' : 'Nova nota'}
          </h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-4">
          {/* Title */}
          <div>
            <label className="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1.5">
              Título *
            </label>
            <input
              autoFocus
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Título da nota..."
              className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              required
            />
          </div>

          {/* Content */}
          <div>
            <label className="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1.5">
              Conteúdo
            </label>
            <textarea
              value={content}
              onChange={e => setContent(e.target.value)}
              placeholder="Escreva sua nota aqui..."
              rows={5}
              className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition resize-none"
            />
          </div>

          {/* Color */}
          <div>
            <label className="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1.5">
              Cor
            </label>
            <ColorPicker value={color} onChange={setColor} />
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving || !title.trim()}
              className="px-5 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl transition-colors"
            >
              {saving ? 'Salvando...' : initial ? 'Salvar alterações' : 'Criar nota'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Delete confirmation ──────────────────────────────────────────────────────

function DeleteDialog({
  onConfirm,
  onCancel,
  loading,
}: {
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6 flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5 text-red-600">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
              <path d="M10 11v6M14 11v6"/>
              <path d="M9 6V4h6v2"/>
            </svg>
          </div>
          <div>
            <h3 className="font-semibold text-slate-800">Excluir nota</h3>
            <p className="text-sm text-slate-500">Esta ação não pode ser desfeita.</p>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded-xl transition-colors"
          >
            {loading ? 'Excluindo...' : 'Excluir'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function NotesPage() {
  const [notes,       setNotes]       = useState<GenericNote[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [search,      setSearch]      = useState('');
  const [filterColor, setFilterColor] = useState<NoteColor | 'all'>('all');
  const [filterPin,   setFilterPin]   = useState(false);

  const [modalOpen,   setModalOpen]   = useState(false);
  const [editing,     setEditing]     = useState<GenericNote | null>(null);
  const [saving,      setSaving]      = useState(false);

  const [deleteId,    setDeleteId]    = useState<number | null>(null);
  const [deleting,    setDeleting]    = useState(false);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      const data = await notesService.list();
      setNotes(data);
    } finally {
      setLoading(false);
    }
  }

  const filtered = notes.filter(n => {
    if (filterPin && !n.is_pinned) return false;
    if (filterColor !== 'all' && n.color !== filterColor) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      if (!n.title.toLowerCase().includes(q) && !n.content.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const pinned   = filtered.filter(n => n.is_pinned);
  const unpinned = filtered.filter(n => !n.is_pinned);

  async function handleSave(payload: NotePayload) {
    setSaving(true);
    try {
      if (editing) {
        const updated = await notesService.update(editing.id, payload);
        setNotes(prev => prev.map(n => n.id === updated.id ? updated : n));
      } else {
        const created = await notesService.create(payload);
        setNotes(prev => [created, ...prev]);
      }
      setModalOpen(false);
      setEditing(null);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (deleteId == null) return;
    setDeleting(true);
    try {
      await notesService.remove(deleteId);
      setNotes(prev => prev.filter(n => n.id !== deleteId));
      setDeleteId(null);
    } finally {
      setDeleting(false);
    }
  }

  async function handleTogglePin(id: number) {
    const updated = await notesService.togglePin(id);
    setNotes(prev => {
      const next = prev.map(n => n.id === updated.id ? updated : n);
      return [...next].sort((a, b) => {
        if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
        return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
      });
    });
  }

  function openCreate() {
    setEditing(null);
    setModalOpen(true);
  }

  function openEdit(note: GenericNote) {
    setEditing(note);
    setModalOpen(true);
  }

  return (
    <div className="flex flex-col h-full min-h-0 bg-slate-50">
      {/* ── Header ── */}
      <div className="flex-shrink-0 px-6 py-5 bg-white border-b border-slate-100 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-800">Notas</h1>
            <p className="text-sm text-slate-500 mt-0.5">
              {notes.length} {notes.length === 1 ? 'nota' : 'notas'}
            </p>
          </div>
          <button
            onClick={openCreate}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-xl shadow-sm transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="w-4 h-4">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            Nova nota
          </button>
        </div>

        {/* Filters row */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative flex-1 min-w-[180px]">
            <svg
              viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
              className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none"
            >
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Buscar notas..."
              className="w-full pl-9 pr-3 py-2 text-sm rounded-xl border border-slate-200 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            />
          </div>

          {/* Color filter */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setFilterColor('all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                filterColor === 'all'
                  ? 'bg-slate-800 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              Todas
            </button>
            {COLOR_OPTIONS.slice(1).map(c => (
              <button
                key={c.value}
                onClick={() => setFilterColor(filterColor === c.value ? 'all' : c.value)}
                title={c.label}
                className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all border-2 ${c.dot} ${
                  filterColor === c.value ? 'border-slate-700 scale-110' : 'border-transparent hover:scale-105'
                }`}
              />
            ))}
          </div>

          {/* Pin filter */}
          <button
            onClick={() => setFilterPin(p => !p)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filterPin ? 'bg-amber-100 text-amber-700 border border-amber-300' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-3.5 h-3.5">
              <line x1="12" y1="17" x2="12" y2="22"/>
              <path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V17z"/>
            </svg>
            Fixadas
          </button>
        </div>
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mb-4">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-8 h-8 text-slate-400">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10 9 9 9 8 9"/>
              </svg>
            </div>
            <p className="text-slate-600 font-medium">
              {search || filterColor !== 'all' || filterPin ? 'Nenhuma nota encontrada' : 'Sem notas ainda'}
            </p>
            <p className="text-slate-400 text-sm mt-1">
              {search || filterColor !== 'all' || filterPin
                ? 'Tente ajustar os filtros.'
                : 'Clique em "Nova nota" para começar.'}
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {pinned.length > 0 && (
              <section>
                <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-3.5 h-3.5">
                    <line x1="12" y1="17" x2="12" y2="22"/>
                    <path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V17z"/>
                  </svg>
                  Fixadas
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {pinned.map(note => (
                    <NoteCard
                      key={note.id}
                      note={note}
                      onEdit={openEdit}
                      onDelete={id => setDeleteId(id)}
                      onTogglePin={handleTogglePin}
                    />
                  ))}
                </div>
              </section>
            )}

            {unpinned.length > 0 && (
              <section>
                {pinned.length > 0 && (
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                    Outras notas
                  </h2>
                )}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {unpinned.map(note => (
                    <NoteCard
                      key={note.id}
                      note={note}
                      onEdit={openEdit}
                      onDelete={id => setDeleteId(id)}
                      onTogglePin={handleTogglePin}
                    />
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </div>

      {/* ── Modals ── */}
      {modalOpen && (
        <NoteModal
          initial={editing}
          onSave={handleSave}
          onClose={() => { setModalOpen(false); setEditing(null); }}
          saving={saving}
        />
      )}

      {deleteId != null && (
        <DeleteDialog
          onConfirm={handleDelete}
          onCancel={() => setDeleteId(null)}
          loading={deleting}
        />
      )}
    </div>
  );
}
