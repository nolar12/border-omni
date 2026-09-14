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
};
