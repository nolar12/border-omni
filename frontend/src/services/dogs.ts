import api from './api';
import type { Dog, DogMedia } from '../types';

export interface DogPayload {
  name: string;
  breed?: string;
  sex: 'M' | 'F';
  birth_date?: string | null;
  color?: string;
  pedigree_number?: string;
  microchip?: string;
  tattoo?: string;
  father?: number | null;
  mother?: number | null;
  origin_litter?: number | null;
  status?: string;
  price?: string | null;
  notes?: string;
}

export const dogsService = {
  async list(params?: { status?: string; sex?: string; search?: string }): Promise<Dog[]> {
    const { data } = await api.get<Dog[]>('/dogs/', { params });
    return data;
  },

  async listAvailable(): Promise<Dog[]> {
    return dogsService.list({ status: 'available' });
  },

  async get(id: number): Promise<Dog> {
    const { data } = await api.get<Dog>(`/dogs/${id}/`);
    return data;
  },

  async create(payload: DogPayload): Promise<Dog> {
    const { data } = await api.post<Dog>('/dogs/', payload);
    return data;
  },

  async update(id: number, payload: Partial<DogPayload>): Promise<Dog> {
    const { data } = await api.patch<Dog>(`/dogs/${id}/`, payload);
    return data;
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/dogs/${id}/`);
  },

  async addMedia(id: number, file: File, caption?: string): Promise<DogMedia> {
    const form = new FormData();
    form.append('file', file);
    if (caption) form.append('caption', caption);
    const { data } = await api.post<DogMedia>(`/dogs/${id}/add_media/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  async removeMedia(dogId: number, mediaId: number): Promise<void> {
    await api.delete(`/dogs/${dogId}/media/${mediaId}/`);
  },
};
