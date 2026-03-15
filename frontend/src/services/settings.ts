import api from './api';
import type { OrgSettings, InitialMessageMedia } from '../types';

export const settingsService = {
  async getSettings(): Promise<OrgSettings> {
    const { data } = await api.get<OrgSettings>('/agent-config/');
    return data;
  },

  async updateSettings(payload: Partial<OrgSettings>): Promise<OrgSettings> {
    const { data } = await api.put<OrgSettings>('/agent-config/', payload);
    return data;
  },

  async getMedia(): Promise<InitialMessageMedia[]> {
    const { data } = await api.get<InitialMessageMedia[]>('/initial-media/');
    return data;
  },

  async uploadMedia(file: File): Promise<InitialMessageMedia> {
    const form = new FormData();
    form.append('file', file);
    const { data } = await api.post<InitialMessageMedia>('/initial-media/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  async deleteMedia(id: number): Promise<void> {
    await api.delete(`/initial-media/${id}/`);
  },
};
