import api from './api';

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
  client_request_id: string;
}

export const advertisingService = {
  async listAccounts(): Promise<AdvertisingAccount[]> {
    const { data } = await api.get<AdvertisingAccount[]>('/advertising-accounts/');
    return data;
  },

  async listCampaigns(): Promise<AdCampaign[]> {
    const { data } = await api.get<AdCampaign[]>('/ad-campaigns/');
    return data;
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
