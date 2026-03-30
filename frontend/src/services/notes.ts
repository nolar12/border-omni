import api from './api';
import type { GenericNote, NoteColor } from '../types';

export interface NotePayload {
  title: string;
  content?: string;
  color?: NoteColor;
  is_pinned?: boolean;
}

export const notesService = {
  async list(): Promise<GenericNote[]> {
    const { data } = await api.get<GenericNote[]>('/notes/');
    return data;
  },

  async create(payload: NotePayload): Promise<GenericNote> {
    const { data } = await api.post<GenericNote>('/notes/', payload);
    return data;
  },

  async update(id: number, payload: Partial<NotePayload>): Promise<GenericNote> {
    const { data } = await api.patch<GenericNote>(`/notes/${id}/`, payload);
    return data;
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/notes/${id}/`);
  },

  async togglePin(id: number): Promise<GenericNote> {
    const { data } = await api.post<GenericNote>(`/notes/${id}/toggle_pin/`);
    return data;
  },
};
