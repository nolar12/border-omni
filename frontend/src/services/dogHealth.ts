import api from './api';
import type { DogHealthRecord, HealthRecordType } from '../types';

export interface HealthRecordPayload {
  dog: number;
  record_type: HealthRecordType;
  description: string;
  date: string;
  next_date?: string | null;
  vet?: string;
  notes?: string;
}

export const dogHealthService = {
  async list(dogId: number): Promise<DogHealthRecord[]> {
    const { data } = await api.get<DogHealthRecord[]>('/dog-health/', { params: { dog: dogId } });
    return data;
  },

  async create(payload: HealthRecordPayload): Promise<DogHealthRecord> {
    const { data } = await api.post<DogHealthRecord>('/dog-health/', payload);
    return data;
  },

  async update(id: number, payload: Partial<HealthRecordPayload>): Promise<DogHealthRecord> {
    const { data } = await api.patch<DogHealthRecord>(`/dog-health/${id}/`, payload);
    return data;
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/dog-health/${id}/`);
  },
};
