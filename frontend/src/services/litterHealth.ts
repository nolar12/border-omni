import api from './api';
import type { LitterHealthRecord, HealthRecordType } from '../types';

export interface LitterHealthPayload {
  litter: number;
  record_type: HealthRecordType;
  description: string;
  date: string;
  next_date?: string | null;
  vet?: string;
  notes?: string;
}

export const litterHealthService = {
  async list(litterId: number): Promise<LitterHealthRecord[]> {
    const { data } = await api.get<LitterHealthRecord[]>('/litter-health/', { params: { litter: litterId } });
    return data;
  },

  async create(payload: LitterHealthPayload): Promise<LitterHealthRecord> {
    const { data } = await api.post<LitterHealthRecord>('/litter-health/', payload);
    return data;
  },

  async update(id: number, payload: Partial<LitterHealthPayload>): Promise<LitterHealthRecord> {
    const { data } = await api.patch<LitterHealthRecord>(`/litter-health/${id}/`, payload);
    return data;
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/litter-health/${id}/`);
  },
};
