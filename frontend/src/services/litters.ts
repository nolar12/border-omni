import api from './api';
import type { Litter, LitterMedia } from '../types';

export interface LitterPayload {
  name: string;
  father?: number | null;
  mother?: number | null;
  mating_date?: string | null;
  expected_birth_date?: string | null;
  birth_date?: string | null;
  male_count?: number;
  female_count?: number;
  cbkc_number?: string;
  notes?: string;
}

export const littersService = {
  async list(): Promise<Litter[]> {
    const { data } = await api.get<Litter[]>('/litters/');
    return data;
  },

  async get(id: number): Promise<Litter> {
    const { data } = await api.get<Litter>(`/litters/${id}/`);
    return data;
  },

  async create(payload: LitterPayload): Promise<Litter> {
    const { data } = await api.post<Litter>('/litters/', payload);
    return data;
  },

  async update(id: number, payload: Partial<LitterPayload>): Promise<Litter> {
    const { data } = await api.patch<Litter>(`/litters/${id}/`, payload);
    return data;
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/litters/${id}/`);
  },

  async addMedia(id: number, file: File, caption?: string): Promise<LitterMedia> {
    const form = new FormData();
    form.append('file', file);
    if (caption) form.append('caption', caption);
    const { data } = await api.post<LitterMedia>(`/litters/${id}/add_media/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  async removeMedia(litterId: number, mediaId: number): Promise<void> {
    await api.delete(`/litters/${litterId}/media/${mediaId}/`);
  },
};
