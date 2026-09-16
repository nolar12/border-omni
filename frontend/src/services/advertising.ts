import api from './api';
import type { PaginatedResponse } from '../types';

export interface AdCampaign {
  id: number;
  advertising_account: number;
  litter: number | null;
  litter_name: string;
  provider: string;
  external_campaign_id: string;
  name: string;
  campaign_type: string;
  objective: string;
  daily_budget: string;
  total_budget: string | null;
  status: 'draft' | 'pending' | 'active' | 'paused' | 'error' | 'ended';
  region: string;
  radius_km: number | null;
  start_date: string | null;
  end_date: string | null;
  landing_url: string;
  ad_headlines: string[];
  ad_descriptions: string[];
  ad_keywords: string[];
  client_request_id: string | null;
  error_message: string;
  created_at: string;
  updated_at: string;
}

export interface AdMetric {
  id: number;
  date: string;
  impressions: number;
  clicks: number;
  cost: string;
  ctr: number;
  average_cpc: string;
  conversions: number;
  cost_per_conversion: string | null;
}

export interface AdSnapshot {
  period_days: number;
  period_from: string;
  period_to: string;
  cost: number;
  impressions: number;
  clicks: number;
  ctr: number | null;
  average_cpc: number | null;
  conversions: number;
  conversion_rate: number | null;
  total_leads: number;
  cost_per_lead: number | null;
  qualified_leads: number;
  cost_per_qualified_lead: number | null;
  negotiations: number;
  reservations: number;
  sales: number;
  cac: number | null;
}

export interface AdFunnelBreakdownRow {
  group: string;
  total_leads: number;
  qualified_leads: number;
  reservations: number;
  sales: number;
  stages: Record<string, number>;
}

export interface AdDashboard {
  snapshot: AdSnapshot;
  city_breakdown: AdFunnelBreakdownRow[];
  keyword_breakdown: AdFunnelBreakdownRow[];
}

export interface AdChatMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  actions_taken: { tool: string; arguments: Record<string, unknown>; result: Record<string, unknown> }[];
  is_proactive: boolean;
  created_at: string;
}

export interface AdvertisingAccount {
  id: number;
  provider: string;
  customer_id: string;
  login_customer_id: string;
  status: string;
  is_active: boolean;
}

export interface PromoteLitterPayload {
  litter_id?: number;
  name?: string;
  daily_budget: number;
  region?: string;
  radius_km?: number;
  start_date?: string;
  end_date?: string;
  landing_url?: string;
  ad_headlines?: string[];
  ad_descriptions?: string[];
  ad_keywords?: string[];
  audience_description?: string;
  client_request_id: string;
}

export interface GoogleAdsDiscoverResponse {
  refresh_token: string;
  accessible_customers: string[];
}

export const advertisingService = {
  async listAccounts(): Promise<AdvertisingAccount[]> {
    const { data } = await api.get<PaginatedResponse<AdvertisingAccount> | AdvertisingAccount[]>('/advertising-accounts/');
    return Array.isArray(data) ? data : data.results;
  },

  /** Passo 1: troca o code do popup do Google Identity Services pelo refresh_token + contas acessíveis. */
  async googleAdsDiscover(code: string): Promise<GoogleAdsDiscoverResponse> {
    const { data } = await api.post<GoogleAdsDiscoverResponse>('/advertising/google-ads/oauth/discover/', { code });
    return data;
  },

  /** Passo 2: usuário escolheu o customer_id — persiste a AdvertisingAccount. */
  async googleAdsFinalize(payload: { refresh_token: string; customer_id: string; login_customer_id?: string }): Promise<AdvertisingAccount> {
    const { data } = await api.post<AdvertisingAccount>('/advertising/google-ads/oauth/finalize/', payload);
    return data;
  },

  async listCampaigns(): Promise<AdCampaign[]> {
    const { data } = await api.get<PaginatedResponse<AdCampaign> | AdCampaign[]>('/ad-campaigns/');
    return Array.isArray(data) ? data : data.results;
  },

  async promoteLitter(payload: PromoteLitterPayload): Promise<AdCampaign> {
    const { data } = await api.post<AdCampaign>('/ad-campaigns/promote-litter/', payload);
    return data;
  },

  async pauseCampaign(id: number): Promise<AdCampaign> {
    const { data } = await api.post<AdCampaign>(`/ad-campaigns/${id}/pause/`);
    return data;
  },

  async resumeCampaign(id: number): Promise<AdCampaign> {
    const { data } = await api.post<AdCampaign>(`/ad-campaigns/${id}/resume/`);
    return data;
  },

  async getMetrics(id: number): Promise<AdMetric[]> {
    const { data } = await api.get<AdMetric[]>(`/ad-campaigns/${id}/metrics/`);
    return data;
  },

  async syncMetrics(id: number): Promise<{ synced: number; metrics: AdMetric[] }> {
    const { data } = await api.post<{ synced: number; metrics: AdMetric[] }>(`/ad-campaigns/${id}/sync_metrics/`);
    return data;
  },

  async getDashboard(id: number, daysBack = 30): Promise<AdDashboard> {
    const { data } = await api.get<AdDashboard>(`/ad-campaigns/${id}/dashboard/`, { params: { days_back: daysBack } });
    return data;
  },

  async getChatHistory(id: number): Promise<AdChatMessage[]> {
    const { data } = await api.get<AdChatMessage[]>(`/ad-campaigns/${id}/chat/`);
    return data;
  },

  async sendChatMessage(id: number, message: string): Promise<AdChatMessage> {
    const { data } = await api.post<AdChatMessage>(`/ad-campaigns/${id}/chat/`, { message });
    return data;
  },

  async transcribeAudio(id: number, audio: Blob): Promise<{ transcription: string }> {
    const form = new FormData();
    form.append('audio', audio, 'audio.webm');
    const { data } = await api.post<{ transcription: string }>(`/ad-campaigns/${id}/chat/transcribe/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  /** Dispara manualmente a mesma revisão periódica e autônoma (só leitura) que
   * roda sozinha semanalmente — útil para testar sem esperar o agendamento. */
  async runProactiveReview(id: number): Promise<AdChatMessage | { status: 'nothing_to_report' }> {
    const { data } = await api.post<AdChatMessage | { status: 'nothing_to_report' }>(`/ad-campaigns/${id}/chat/proactive-review/`);
    return data;
  },
};
