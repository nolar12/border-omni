import api from './api';
import type {
  ChannelProvider,
  QualityRatingEvent,
  QualitySyncResult,
  PaginatedResponse,
  MetaDiscoverResponse,
  MetaSelection,
} from '../types';

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

  /**
   * Step 1 — Exchange the FB.login() authorization code for a SUAT and return
   * the list of Meta business assets available for the given provider.
   * The SUAT belongs to the client's Business Portfolio (not a personal account).
   */
  async metaDiscover(code: string, provider: string): Promise<MetaDiscoverResponse> {
    const { data } = await api.post<MetaDiscoverResponse>('/channels/meta/discover/', {
      code,
      provider,
    });
    return data;
  },

  /**
   * Step 2 — Finalize channel setup: backend configures webhooks via API and
   * saves the ChannelProvider. Returns the saved channel.
   */
  async metaFinalize(selection: MetaSelection): Promise<ChannelProvider> {
    const { data } = await api.post<ChannelProvider>('/channels/meta/finalize/', selection);
    return data;
  },

  /** Dispara sync imediato de quality_rating para um canal específico. */
  async syncQuality(id: number): Promise<QualitySyncResult> {
    const { data } = await api.post<QualitySyncResult>(`/channels/${id}/sync_quality/`);
    return data;
  },

  /** Retorna histórico de mudanças de rating do canal. */
  async getQualityHistory(id: number): Promise<QualityRatingEvent[]> {
    const { data } = await api.get<QualityRatingEvent[]>(`/channels/${id}/quality_history/`);
    return data;
  },
};
