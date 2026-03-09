import api from './api';
import type { ChannelProvider, PaginatedResponse } from '../types';

export const channelsService = {
  async getAll(): Promise<ChannelProvider[]> {
    const { data } = await api.get<PaginatedResponse<ChannelProvider> | ChannelProvider[]>('/channels/');
    return Array.isArray(data) ? data : data.results;
  },

  async create(payload: Partial<ChannelProvider>): Promise<ChannelProvider> {
    const { data } = await api.post<ChannelProvider>('/channels/', payload);
    return data;
  },

  async update(id: number, payload: Partial<ChannelProvider>): Promise<ChannelProvider> {
    const { data } = await api.patch<ChannelProvider>(`/channels/${id}/`, payload);
    return data;
  },

  async delete(id: number): Promise<void> {
    await api.delete(`/channels/${id}/`);
  },
};
